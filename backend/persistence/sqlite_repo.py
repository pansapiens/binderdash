from __future__ import annotations

import json
import logging
import sqlite3
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import unquote

from .protocol import (
    RESERVED_TOP_LEVEL_KEYS,
    design_dedupe_key,
    merge_design_from_storage,
    split_design_for_storage,
)

logger = logging.getLogger(__name__)


def _design_row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    """Merge a binderdash_designs SQLite row into a flat design dict for the API cache."""
    data = json.loads(row["data_json"])
    extra_raw = row["extra_data"]
    if extra_raw is None or not str(extra_raw).strip():
        extra: Dict[str, Any] = {}
    else:
        extra = json.loads(extra_raw)
    good_v: Optional[bool]
    if row["good"] is None:
        good_v = None
    else:
        good_v = bool(row["good"])
    tag_v = row["tag"]
    bc_v = row["binder_chain"]
    binder_chain_out: Optional[str] = (
        str(bc_v).strip() if bc_v is not None and str(bc_v).strip() else None
    )
    sn_v = row["short_name"]
    short_name_out: Optional[str] = (
        str(sn_v).strip() if sn_v is not None and str(sn_v).strip() else None
    )
    return merge_design_from_storage(
        row["run_id"],
        row["design_id"],
        row["project_id"],
        row["method"],
        row["source_path"] or "",
        tag_v,
        good_v,
        data,
        binder_chain=binder_chain_out,
        short_name=short_name_out,
        extra=extra,
    )


def _normalise_email(value: Any) -> Optional[str]:
    """Lowercase/strip an email, mapping blanks and non-emails to None."""
    if value is None:
        return None
    text = str(value).strip().lower()
    if not text or "@" not in text:
        return None
    return text


def _sqlite_path_from_url(database_url: str) -> Path:
    u = database_url.strip()
    if not u.lower().startswith("sqlite:"):
        raise ValueError(f"Expected sqlite URL, got: {u[:48]!r}")
    no_scheme = u.split(":", 1)[1]
    if no_scheme.startswith("////"):
        body = unquote(no_scheme[4:])
        p = Path(body) if body.startswith(("/", "\\")) else Path("/") / body
        return p.expanduser().resolve()
    if no_scheme.startswith("///"):
        body = unquote(no_scheme[3:])
        if not body:
            raise ValueError("Invalid sqlite URL: empty path")
        p = Path(body)
        if p.is_absolute():
            return p.expanduser().resolve()
        return (Path.cwd() / p).expanduser().resolve()
    raise ValueError(f"Invalid sqlite URL (expected /// or ////): {u[:48]!r}")


class SqliteDesignsRepository:
    def __init__(self, database_url: str) -> None:
        self._url = database_url.strip()
        self._path = _sqlite_path_from_url(self._url)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn: Optional[sqlite3.Connection] = None

    def is_enabled(self) -> bool:
        return True

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(
                str(self._path),
                check_same_thread=False,
            )
            self._conn.row_factory = sqlite3.Row
            # These are per-connection, so they belong here rather than in
            # init_schema. busy_timeout in particular matters now that
            # `python -m backend.cli` writes to the same file as a running
            # server: the default of 0 turns any overlap into an immediate
            # "database is locked".
            self._conn.execute("PRAGMA foreign_keys = ON")
            self._conn.execute("PRAGMA journal_mode = WAL")
            self._conn.execute("PRAGMA busy_timeout = 5000")
        return self._conn

    def init_schema(self) -> None:
        with self._lock:
            c = self._get_conn()
            c.executescript(
                """
                CREATE TABLE IF NOT EXISTS binderdash_runs (
                    run_id TEXT PRIMARY KEY,
                    run_group_key TEXT NOT NULL UNIQUE,
                    project_id TEXT NOT NULL,
                    method TEXT NOT NULL,
                    run_name TEXT NOT NULL,
                    run_path TEXT NOT NULL DEFAULT '',
                    run_json TEXT NOT NULL,
                    ingested_at TEXT
                );
                CREATE TABLE IF NOT EXISTS binderdash_designs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    design_dedupe TEXT NOT NULL,
                    design_id TEXT NOT NULL,
                    project_id TEXT NOT NULL,
                    method TEXT NOT NULL,
                    source_path TEXT NOT NULL DEFAULT '',
                    tag TEXT,
                    good INTEGER,
                    binder_chain TEXT,
                    short_name TEXT,
                    data_json TEXT NOT NULL,
                    extra_data TEXT NOT NULL DEFAULT '{}',
                    FOREIGN KEY(run_id) REFERENCES binderdash_runs(run_id) ON DELETE CASCADE,
                    UNIQUE(run_id, design_dedupe)
                );
                CREATE INDEX IF NOT EXISTS idx_designs_run_id
                    ON binderdash_designs(run_id);
                -- Legacy login audit table. Superseded by binderdash_users +
                -- binderdash_user_identities, but deliberately left in place so
                -- rolling back to an earlier release still logs people in.
                CREATE TABLE IF NOT EXISTS binderdash_auth_users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    provider TEXT NOT NULL,
                    identifier TEXT NOT NULL,
                    email TEXT,
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    last_login_at TEXT NOT NULL DEFAULT (datetime('now')),
                    UNIQUE(provider, identifier)
                );
                CREATE TABLE IF NOT EXISTS binderdash_users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT,
                    display_name TEXT,
                    picture_url TEXT,
                    is_admin INTEGER NOT NULL DEFAULT 0,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    last_login_at TEXT NOT NULL DEFAULT (datetime('now'))
                );
                -- Partial index: many users may have no email (local/pam), but a
                -- non-null email identifies exactly one user and is what cross-
                -- provider account merging keys on.
                CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email
                    ON binderdash_users(email) WHERE email IS NOT NULL;
                CREATE TABLE IF NOT EXISTS binderdash_user_identities (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    provider TEXT NOT NULL,
                    identifier TEXT NOT NULL,
                    email TEXT,
                    display_name TEXT,
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    last_login_at TEXT NOT NULL DEFAULT (datetime('now')),
                    UNIQUE(provider, identifier),
                    FOREIGN KEY(user_id) REFERENCES binderdash_users(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_user_identities_user_id
                    ON binderdash_user_identities(user_id);
                CREATE TABLE IF NOT EXISTS binderdash_api_keys (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    key_prefix TEXT NOT NULL,
                    key_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    expires_at TEXT,
                    revoked_at TEXT,
                    last_used_at TEXT,
                    FOREIGN KEY(user_id) REFERENCES binderdash_users(id) ON DELETE CASCADE
                );
                CREATE UNIQUE INDEX IF NOT EXISTS idx_api_keys_hash
                    ON binderdash_api_keys(key_hash);
                CREATE INDEX IF NOT EXISTS idx_api_keys_user_id
                    ON binderdash_api_keys(user_id);
                -- Names are unique only among live keys, so a name can be reused
                -- once the old key is revoked.
                CREATE UNIQUE INDEX IF NOT EXISTS idx_api_keys_user_name
                    ON binderdash_api_keys(user_id, name) WHERE revoked_at IS NULL;
                CREATE TABLE IF NOT EXISTS binderdash_tag_metrics_cache (
                    run_id TEXT NOT NULL,
                    design_id TEXT NOT NULL,
                    source_path TEXT NOT NULL DEFAULT '',
                    structure_filename TEXT NOT NULL,
                    binder_chain TEXT NOT NULL,
                    target_chains TEXT NOT NULL DEFAULT '',
                    distant_from TEXT NOT NULL DEFAULT '',
                    sasa_probe_radius REAL NOT NULL,
                    sasa_n_points INTEGER NOT NULL,
                    sasa_threshold REAL NOT NULL,
                    more_distant_threshold REAL NOT NULL,
                    metrics_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                    PRIMARY KEY (
                        run_id,
                        design_id,
                        source_path,
                        structure_filename,
                        binder_chain,
                        target_chains,
                        distant_from,
                        sasa_probe_radius,
                        sasa_n_points,
                        sasa_threshold,
                        more_distant_threshold
                    )
                );
                CREATE TABLE IF NOT EXISTS binderdash_structural_metrics_cache (
                    run_id TEXT NOT NULL,
                    design_id TEXT NOT NULL,
                    source_path TEXT NOT NULL DEFAULT '',
                    structure_filename TEXT NOT NULL,
                    binder_chains TEXT NOT NULL DEFAULT '',
                    target_chains TEXT NOT NULL DEFAULT '',
                    metrics_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                    PRIMARY KEY (
                        run_id,
                        design_id,
                        source_path,
                        structure_filename,
                        binder_chains,
                        target_chains
                    )
                );
                CREATE TABLE IF NOT EXISTS binderdash_saved_sets (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    source_run_ids TEXT NOT NULL,
                    filter_params TEXT NOT NULL,
                    result_summary TEXT NOT NULL DEFAULT '{}'
                );
                CREATE TABLE IF NOT EXISTS binderdash_saved_set_designs (
                    saved_set_id TEXT NOT NULL,
                    design_id TEXT NOT NULL,
                    run_id TEXT NOT NULL,
                    source_path TEXT NOT NULL DEFAULT '',
                    final_rank INTEGER,
                    quality_score REAL,
                    in_diverse_set INTEGER NOT NULL DEFAULT 0,
                    metrics_json TEXT NOT NULL DEFAULT '{}',
                    PRIMARY KEY (saved_set_id, design_id, run_id, source_path)
                );
                CREATE INDEX IF NOT EXISTS idx_saved_set_designs_saved_set_id
                    ON binderdash_saved_set_designs(saved_set_id);
                """
            )
            self._migrate_binder_chain_column(c)
            self._migrate_short_name_column(c)
            self._migrate_extra_data_column(c)
            self._migrate_run_path_column(c)
            self._migrate_ingested_at_column(c)
            self._migrate_auth_users_to_user_model(c)
            c.commit()

    def _migrate_binder_chain_column(self, c: sqlite3.Connection) -> None:
        info = c.execute("PRAGMA table_info(binderdash_designs)").fetchall()
        names = {row[1] for row in info}
        if "binder_chain" in names:
            return
        try:
            c.execute("ALTER TABLE binderdash_designs ADD COLUMN binder_chain TEXT")
        except sqlite3.OperationalError as e:
            if "duplicate column" not in str(e).lower():
                raise

    def _migrate_short_name_column(self, c: sqlite3.Connection) -> None:
        info = c.execute("PRAGMA table_info(binderdash_designs)").fetchall()
        names = {row[1] for row in info}
        if "short_name" in names:
            return
        try:
            c.execute("ALTER TABLE binderdash_designs ADD COLUMN short_name TEXT")
        except sqlite3.OperationalError as e:
            if "duplicate column" not in str(e).lower():
                raise

    def _migrate_extra_data_column(self, c: sqlite3.Connection) -> None:
        info = c.execute("PRAGMA table_info(binderdash_designs)").fetchall()
        names = {row[1] for row in info}
        if "extra_data" in names:
            return
        try:
            c.execute(
                "ALTER TABLE binderdash_designs ADD COLUMN extra_data TEXT NOT NULL DEFAULT '{}'"
            )
        except sqlite3.OperationalError as e:
            if "duplicate column" not in str(e).lower():
                raise

    def _migrate_run_path_column(self, c: sqlite3.Connection) -> None:
        info = c.execute("PRAGMA table_info(binderdash_runs)").fetchall()
        names = {row[1] for row in info}
        if "run_path" in names:
            return
        try:
            c.execute(
                "ALTER TABLE binderdash_runs ADD COLUMN run_path TEXT NOT NULL DEFAULT ''"
            )
        except sqlite3.OperationalError as e:
            if "duplicate column" not in str(e).lower():
                raise

    def _migrate_ingested_at_column(self, c: sqlite3.Connection) -> None:
        info = c.execute("PRAGMA table_info(binderdash_runs)").fetchall()
        names = {row[1] for row in info}
        if "ingested_at" in names:
            return
        try:
            c.execute("ALTER TABLE binderdash_runs ADD COLUMN ingested_at TEXT")
        except sqlite3.OperationalError as e:
            if "duplicate column" not in str(e).lower():
                raise

    def _migrate_auth_users_to_user_model(self, c: sqlite3.Connection) -> None:
        """Backfill binderdash_users/_user_identities from the legacy audit table.

        Idempotent: an identity row already existing for (provider, identifier)
        is the whole guard, so re-running init_schema is a no-op. The legacy
        table is read-only here and is never dropped.
        """
        exists = c.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='binderdash_auth_users'"
        ).fetchone()
        if not exists:
            return
        rows = c.execute(
            """
            SELECT provider, identifier, email, created_at, last_login_at
            FROM binderdash_auth_users
            ORDER BY (email IS NULL), created_at, id
            """
        ).fetchall()
        for row in rows:
            provider = (row["provider"] or "").strip()
            identifier = (row["identifier"] or "").strip()
            if not provider or not identifier:
                continue
            # Normalise exactly as upsert_login_identity does, or the next
            # login creates a second identity row for the same person.
            if provider != "google" or "@" in identifier:
                identifier = identifier.lower()
            already = c.execute(
                "SELECT 1 FROM binderdash_user_identities WHERE provider = ? AND identifier = ?",
                (provider, identifier),
            ).fetchone()
            if already:
                continue

            email = _normalise_email(row["email"])
            if email is None and provider == "google":
                # Google identities historically stored the email as identifier.
                email = _normalise_email(identifier)
            created_at = row["created_at"]
            last_login_at = row["last_login_at"]

            user_id: Optional[int] = None
            if email is not None:
                found = c.execute(
                    "SELECT id FROM binderdash_users WHERE email = ?", (email,)
                ).fetchone()
                if found is not None:
                    user_id = int(found["id"])
                    c.execute(
                        """
                        UPDATE binderdash_users
                        SET created_at = MIN(created_at, ?),
                            last_login_at = MAX(last_login_at, ?)
                        WHERE id = ?
                        """,
                        (created_at, last_login_at, user_id),
                    )
            if user_id is None:
                # No email means local/pam, which can never be merged safely.
                cur = c.execute(
                    """
                    INSERT INTO binderdash_users (email, created_at, last_login_at)
                    VALUES (?, ?, ?)
                    """,
                    (email, created_at, last_login_at),
                )
                user_id = int(cur.lastrowid or 0)

            c.execute(
                """
                INSERT INTO binderdash_user_identities
                    (user_id, provider, identifier, email, created_at, last_login_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (user_id, provider, identifier, email, created_at, last_login_at),
            )

    def get_run_by_group_key(self, run_group_key: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            cur = self._get_conn().execute(
                "SELECT run_id, run_group_key, project_id, method, run_name, run_path, "
                "run_json, ingested_at "
                "FROM binderdash_runs WHERE run_group_key = ?",
                (run_group_key,),
            )
            row = cur.fetchone()
            if row is None:
                return None
            return {
                "run_id": row["run_id"],
                "run_group_key": row["run_group_key"],
                "project_id": row["project_id"],
                "method": row["method"],
                "run_name": row["run_name"],
                "run_path": row["run_path"],
                "run_json": json.loads(row["run_json"]),
                "ingested_at": row["ingested_at"],
            }

    def upsert_run_and_replace_designs(
        self,
        run_group_key: str,
        run_id: str,
        run_dict: Dict[str, Any],
        designs: List[Dict[str, Any]],
    ) -> None:
        run_name = (run_dict.get("metadata") or {}).get("name", "unknown")
        project_id = str(run_dict.get("project_id", ""))
        method = str(run_dict.get("method", ""))
        path_raw = run_dict.get("path", "")
        if path_raw:
            try:
                run_path = str(Path(str(path_raw)).expanduser().resolve(strict=False))
            except OSError:
                run_path = str(path_raw)
        else:
            run_path = ""
        if run_path:
            try:
                run_dict["folder_mtime"] = Path(run_path).stat().st_mtime
            except OSError:
                run_dict.pop("folder_mtime", None)
        run_json_str = json.dumps(run_dict, default=str)

        with self._lock:
            conn = self._get_conn()
            preserved_rows: Dict[str, Dict[str, Any]] = {}
            cur_prev = conn.execute(
                """
                SELECT design_dedupe, extra_data, tag, good, binder_chain, short_name
                FROM binderdash_designs WHERE run_id = ?
                """,
                (run_id,),
            )
            for prev in cur_prev.fetchall():
                extra_raw = prev["extra_data"]
                if extra_raw is None or not str(extra_raw).strip():
                    extra_obj: Dict[str, Any] = {}
                else:
                    extra_obj = json.loads(extra_raw)
                preserved_rows[prev["design_dedupe"]] = {
                    "extra_data": extra_obj,
                    "tag": prev["tag"],
                    "good": prev["good"],
                    "binder_chain": prev["binder_chain"],
                    "short_name": prev["short_name"],
                }
            conn.execute("DELETE FROM binderdash_designs WHERE run_id = ?", (run_id,))
            conn.execute(
                """
                INSERT INTO binderdash_runs (
                    run_id, run_group_key, project_id, method, run_name, run_path,
                    run_json, ingested_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
                ON CONFLICT(run_id) DO UPDATE SET
                    run_group_key = excluded.run_group_key,
                    project_id = excluded.project_id,
                    method = excluded.method,
                    run_name = excluded.run_name,
                    run_path = excluded.run_path,
                    run_json = excluded.run_json,
                    ingested_at = binderdash_runs.ingested_at
                """,
                (
                    run_id,
                    run_group_key,
                    project_id,
                    method,
                    run_name,
                    run_path,
                    run_json_str,
                ),
            )
            ingested_row = conn.execute(
                "SELECT ingested_at FROM binderdash_runs WHERE run_id = ?",
                (run_id,),
            ).fetchone()
            if ingested_row and ingested_row["ingested_at"]:
                run_dict["ingested_at"] = ingested_row["ingested_at"]
            for d in designs:
                did, pid, meth, sp, tag, good, binder_chain, short_name, payload = (
                    split_design_for_storage(d)
                )
                dedupe = design_dedupe_key(did, sp or None)
                prev = preserved_rows.get(dedupe)
                if prev is not None:
                    extra_obj = dict(prev["extra_data"])
                    tag = prev["tag"]
                    g_prev = prev["good"]
                    good = None if g_prev is None else bool(g_prev)
                    bc_prev = prev["binder_chain"]
                    if bc_prev is not None and str(bc_prev).strip():
                        binder_chain = str(bc_prev).strip()
                    sn_prev = prev["short_name"]
                    if sn_prev is not None and str(sn_prev).strip():
                        short_name = str(sn_prev).strip()
                else:
                    extra_obj = {}
                good_i: Optional[int]
                if good is None:
                    good_i = None
                else:
                    good_i = 1 if good else 0
                conn.execute(
                    """
                    INSERT INTO binderdash_designs (
                        run_id, design_dedupe, design_id, project_id, method,
                        source_path, tag, good, binder_chain, short_name,
                        data_json, extra_data
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        run_id,
                        dedupe,
                        did,
                        pid,
                        meth,
                        sp,
                        tag,
                        good_i,
                        binder_chain,
                        short_name,
                        json.dumps(payload, default=str),
                        json.dumps(extra_obj, default=str),
                    ),
                )
            conn.commit()

    def list_run_records(self) -> List[Dict[str, Any]]:
        with self._lock:
            cur = self._get_conn().execute(
                "SELECT run_id, run_group_key, project_id, method, run_name, run_path, "
                "run_json, ingested_at "
                "FROM binderdash_runs ORDER BY run_name"
            )
            return [dict(r) for r in cur.fetchall()]

    def list_all_design_dicts(self) -> List[Dict[str, Any]]:
        with self._lock:
            cur = self._get_conn().execute(
                "SELECT run_id, design_id, project_id, method, source_path, tag, good, "
                "binder_chain, short_name, data_json, extra_data FROM binderdash_designs"
            )
            return [_design_row_to_dict(row) for row in cur.fetchall()]

    def list_design_dicts_for_run_ids(
        self, run_ids: List[str]
    ) -> List[Dict[str, Any]]:
        """Load design dicts for the given run_ids only (same shape as list_all_design_dicts)."""
        ids = [str(r).strip() for r in run_ids if str(r).strip()]
        if not ids:
            return []
        with self._lock:
            placeholders = ",".join("?" * len(ids))
            cur = self._get_conn().execute(
                "SELECT run_id, design_id, project_id, method, source_path, tag, good, "
                "binder_chain, short_name, data_json, extra_data FROM binderdash_designs "
                f"WHERE run_id IN ({placeholders})",
                ids,
            )
            return [_design_row_to_dict(row) for row in cur.fetchall()]

    def count_designs_by_run_id(
        self, run_ids: Optional[List[str]] = None
    ) -> Dict[str, int]:
        """Cheap ``GROUP BY`` counts so list_runs need not load design rows."""
        ids = (
            [str(r).strip() for r in run_ids if str(r).strip()]
            if run_ids is not None
            else None
        )
        with self._lock:
            if ids is not None:
                if not ids:
                    return {}
                placeholders = ",".join("?" * len(ids))
                cur = self._get_conn().execute(
                    "SELECT run_id, COUNT(*) AS n FROM binderdash_designs "
                    f"WHERE run_id IN ({placeholders}) GROUP BY run_id",
                    ids,
                )
            else:
                cur = self._get_conn().execute(
                    "SELECT run_id, COUNT(*) AS n FROM binderdash_designs GROUP BY run_id"
                )
            return {str(row["run_id"]): int(row["n"]) for row in cur.fetchall()}

    def update_design_tag(
        self,
        run_id: str,
        design_id: str,
        tag: Optional[str],
        source_path: Optional[str] = None,
    ) -> bool:
        dedupe = design_dedupe_key(design_id, source_path)
        with self._lock:
            cur = self._get_conn().execute(
                "UPDATE binderdash_designs SET tag = ? WHERE run_id = ? AND design_dedupe = ?",
                (tag, run_id, dedupe),
            )
            self._get_conn().commit()
            return cur.rowcount > 0

    def update_design_good(
        self,
        run_id: str,
        design_id: str,
        good: Optional[bool],
        source_path: Optional[str] = None,
    ) -> bool:
        dedupe = design_dedupe_key(design_id, source_path)
        good_i: Optional[int]
        if good is None:
            good_i = None
        else:
            good_i = 1 if good else 0
        with self._lock:
            cur = self._get_conn().execute(
                "UPDATE binderdash_designs SET good = ? WHERE run_id = ? AND design_dedupe = ?",
                (good_i, run_id, dedupe),
            )
            self._get_conn().commit()
            return cur.rowcount > 0

    def update_design_sequence_and_binder_chain(
        self,
        run_id: str,
        design_id: str,
        *,
        source_path: Optional[str] = None,
        sequence: Optional[str] = None,
        binder_chain: Optional[str] = None,
    ) -> bool:
        if sequence is None and binder_chain is None:
            return False
        dedupe = design_dedupe_key(design_id, source_path)
        with self._lock:
            conn = self._get_conn()
            cur = conn.execute(
                "SELECT extra_data, binder_chain FROM binderdash_designs "
                "WHERE run_id = ? AND design_dedupe = ?",
                (run_id, dedupe),
            )
            row = cur.fetchone()
            if row is None:
                return False
            extra_raw = row["extra_data"]
            if extra_raw is None or not str(extra_raw).strip():
                extra: Dict[str, Any] = {}
            else:
                extra = json.loads(extra_raw)
            if sequence is not None:
                extra["Sequence"] = sequence
            new_extra = json.dumps(extra, default=str)
            if binder_chain is not None:
                bc = binder_chain.strip() or None
                conn.execute(
                    """
                    UPDATE binderdash_designs SET extra_data = ?, binder_chain = ?
                    WHERE run_id = ? AND design_dedupe = ?
                    """,
                    (new_extra, bc, run_id, dedupe),
                )
            else:
                conn.execute(
                    """
                    UPDATE binderdash_designs SET extra_data = ?
                    WHERE run_id = ? AND design_dedupe = ?
                    """,
                    (new_extra, run_id, dedupe),
                )
            conn.commit()
            return True

    def list_data_json_keys_for_runs(self, run_ids: List[str]) -> List[str]:
        if not run_ids:
            return []
        keys: set[str] = set()
        placeholders = ",".join("?" * len(run_ids))
        with self._lock:
            cur = self._get_conn().execute(
                f"SELECT data_json FROM binderdash_designs WHERE run_id IN ({placeholders})",
                tuple(run_ids),
            )
            for row in cur.fetchall():
                data = json.loads(row["data_json"])
                keys.update(str(k) for k in data.keys())
        return sorted(keys)

    def merge_design_extra_data_bulk(
        self,
        run_id: str,
        items: List[Dict[str, Any]],
    ) -> Dict[str, int]:
        matched = 0
        updated = 0
        skipped_keys = 0
        unknown = 0
        if not items:
            return {
                "matched": 0,
                "updated": 0,
                "skipped_keys": 0,
                "unknown_design_ids": 0,
            }
        with self._lock:
            conn = self._get_conn()
            for it in items:
                design_id = str(it.get("design_id", ""))
                sp_raw = it.get("source_path")
                source_path = (
                    str(sp_raw).strip()
                    if sp_raw is not None and str(sp_raw).strip()
                    else ""
                )
                fields = it.get("fields") or {}
                if not design_id or not isinstance(fields, dict):
                    unknown += 1
                    continue
                dedupe = design_dedupe_key(design_id, source_path or None)
                cur = conn.execute(
                    """
                    SELECT data_json, extra_data FROM binderdash_designs
                    WHERE run_id = ? AND design_dedupe = ?
                    """,
                    (run_id, dedupe),
                )
                row = cur.fetchone()
                if row is None:
                    unknown += 1
                    continue
                matched += 1
                data = json.loads(row["data_json"])
                extra_raw = row["extra_data"]
                if extra_raw is None or not str(extra_raw).strip():
                    extra: Dict[str, Any] = {}
                else:
                    extra = json.loads(extra_raw)
                changed = False
                for key, value in fields.items():
                    k = str(key).strip()
                    if not k or k in RESERVED_TOP_LEVEL_KEYS:
                        skipped_keys += 1
                        continue
                    if k in data or k in extra:
                        skipped_keys += 1
                        continue
                    extra[k] = value
                    changed = True
                if changed:
                    conn.execute(
                        """
                        UPDATE binderdash_designs SET extra_data = ?
                        WHERE run_id = ? AND design_dedupe = ?
                        """,
                        (json.dumps(extra, default=str), run_id, dedupe),
                    )
                    updated += 1
            conn.commit()
        return {
            "matched": matched,
            "updated": updated,
            "skipped_keys": skipped_keys,
            "unknown_design_ids": unknown,
        }

    def update_design_short_names_bulk(
        self,
        items: List[Dict[str, Any]],
    ) -> int:
        if not items:
            return 0
        updated = 0
        with self._lock:
            conn = self._get_conn()
            for it in items:
                run_id = str(it.get("run_id", ""))
                design_id = str(it.get("design_id", ""))
                sp_raw = it.get("source_path")
                source_path = (
                    str(sp_raw).strip() if sp_raw is not None and str(sp_raw).strip() else ""
                )
                dedupe = design_dedupe_key(design_id, source_path or None)
                sn = it.get("short_name")
                if sn is None:
                    val: Optional[str] = None
                else:
                    s = str(sn).strip()
                    val = s if s else None
                cur = conn.execute(
                    """
                    UPDATE binderdash_designs SET short_name = ?
                    WHERE run_id = ? AND design_dedupe = ?
                    """,
                    (val, run_id, dedupe),
                )
                updated += cur.rowcount
            conn.commit()
        return updated

    def delete_run(self, run_id: str) -> bool:
        with self._lock:
            conn = self._get_conn()
            conn.execute(
                "DELETE FROM binderdash_tag_metrics_cache WHERE run_id = ?", (run_id,)
            )
            conn.execute(
                "DELETE FROM binderdash_structural_metrics_cache WHERE run_id = ?",
                (run_id,),
            )
            cur = conn.execute("DELETE FROM binderdash_runs WHERE run_id = ?", (run_id,))
            conn.commit()
            return cur.rowcount > 0

    # --- Users, identities, API keys -------------------------------------

    def upsert_login_identity(
        self,
        *,
        provider: str,
        identifier: str,
        email: Optional[str] = None,
        display_name: Optional[str] = None,
        picture_url: Optional[str] = None,
        is_admin: bool = False,
    ) -> Optional[Dict[str, Any]]:
        provider = (provider or "").strip()
        identifier = (identifier or "").strip()
        if not provider or not identifier:
            return None
        # Google's `sub` is case-sensitive and opaque; usernames and emails are not.
        if provider != "google" or "@" in identifier:
            identifier = identifier.lower()
        email_n = _normalise_email(email)

        with self._lock:
            conn = self._get_conn()
            for attempt in (0, 1):
                try:
                    user_id = self._link_identity(
                        conn, provider, identifier, email_n, display_name
                    )
                    conn.execute(
                        """
                        UPDATE binderdash_users
                        SET last_login_at = datetime('now'),
                            is_admin = ?,
                            display_name = COALESCE(?, display_name),
                            picture_url = COALESCE(?, picture_url),
                            email = COALESCE(email, ?)
                        WHERE id = ?
                        """,
                        (
                            1 if is_admin else 0,
                            display_name,
                            picture_url,
                            email_n,
                            user_id,
                        ),
                    )
                    conn.execute(
                        """
                        UPDATE binderdash_user_identities
                        SET last_login_at = datetime('now'),
                            email = COALESCE(?, email),
                            display_name = COALESCE(?, display_name)
                        WHERE provider = ? AND identifier = ?
                        """,
                        (email_n, display_name, provider, identifier),
                    )
                    # Dual-write the legacy audit table so rolling back to a
                    # previous release does not lose recent logins.
                    conn.execute(
                        """
                        INSERT INTO binderdash_auth_users
                            (provider, identifier, email, last_login_at)
                        VALUES (?, ?, ?, datetime('now'))
                        ON CONFLICT(provider, identifier) DO UPDATE SET
                            last_login_at = datetime('now'),
                            email = COALESCE(excluded.email, binderdash_auth_users.email)
                        """,
                        (provider, identifier, email_n),
                    )
                    conn.commit()
                    return self._get_user_row(conn, user_id)
                except sqlite3.IntegrityError:
                    # Another process created the same identity/user between our
                    # SELECT and INSERT. Roll back and re-resolve once.
                    conn.rollback()
                    if attempt:
                        logger.warning(
                            "upsert_login_identity: integrity conflict for %s:%s",
                            provider,
                            identifier,
                        )
                        return None
            return None

    def _link_identity(
        self,
        conn: sqlite3.Connection,
        provider: str,
        identifier: str,
        email_n: Optional[str],
        display_name: Optional[str],
    ) -> int:
        """Resolve (provider, identifier) to a user id, creating rows as needed."""
        row = conn.execute(
            "SELECT id, user_id FROM binderdash_user_identities"
            " WHERE provider = ? AND identifier = ?",
            (provider, identifier),
        ).fetchone()

        if row is None and provider == "google" and email_n:
            # Google identities used to be keyed by email. Re-point that row at
            # the stable `sub` rather than creating a second identity, so the
            # user keeps their API keys.
            legacy = conn.execute(
                "SELECT id, user_id FROM binderdash_user_identities"
                " WHERE provider = 'google' AND identifier = ?",
                (email_n,),
            ).fetchone()
            if legacy is not None:
                conn.execute(
                    "UPDATE binderdash_user_identities SET identifier = ? WHERE id = ?",
                    (identifier, legacy["id"]),
                )
                row = legacy

        if row is not None:
            user_id = int(row["user_id"])
            if email_n:
                user_id = self._reconcile_email(conn, user_id, email_n)
            return user_id

        if email_n:
            found = conn.execute(
                "SELECT id FROM binderdash_users WHERE email = ?", (email_n,)
            ).fetchone()
            if found is not None:
                user_id = int(found["id"])
                conn.execute(
                    "INSERT INTO binderdash_user_identities"
                    " (user_id, provider, identifier, email, display_name)"
                    " VALUES (?, ?, ?, ?, ?)",
                    (user_id, provider, identifier, email_n, display_name),
                )
                return user_id

        cur = conn.execute(
            "INSERT INTO binderdash_users (email, display_name) VALUES (?, ?)",
            (email_n, display_name),
        )
        user_id = int(cur.lastrowid or 0)
        conn.execute(
            "INSERT INTO binderdash_user_identities"
            " (user_id, provider, identifier, email, display_name)"
            " VALUES (?, ?, ?, ?, ?)",
            (user_id, provider, identifier, email_n, display_name),
        )
        return user_id

    def _reconcile_email(
        self, conn: sqlite3.Connection, user_id: int, email_n: str
    ) -> int:
        """An identity just supplied a verified email; merge users if it belongs
        to someone else's record. Returns the surviving user id."""
        current = conn.execute(
            "SELECT id, email, created_at FROM binderdash_users WHERE id = ?",
            (user_id,),
        ).fetchone()
        if current is None or current["email"] == email_n:
            return user_id
        owner = conn.execute(
            "SELECT id, created_at FROM binderdash_users WHERE email = ?", (email_n,)
        ).fetchone()
        if owner is None:
            return user_id  # caller's UPDATE ... COALESCE(email, ?) claims it
        winner, loser = int(owner["id"]), user_id
        if winner == loser:
            return winner
        # Oldest record wins, so the longest-lived key history survives.
        if (current["created_at"] or "") < (owner["created_at"] or ""):
            winner, loser = loser, winner
        conn.execute(
            "UPDATE binderdash_user_identities SET user_id = ? WHERE user_id = ?",
            (winner, loser),
        )
        conn.execute(
            "UPDATE binderdash_api_keys SET user_id = ? WHERE user_id = ?",
            (winner, loser),
        )
        conn.execute(
            """
            UPDATE binderdash_users SET
                email = COALESCE(email, ?),
                created_at = MIN(created_at, (SELECT created_at FROM binderdash_users WHERE id = ?)),
                last_login_at = MAX(last_login_at, (SELECT last_login_at FROM binderdash_users WHERE id = ?)),
                is_admin = MAX(is_admin, (SELECT is_admin FROM binderdash_users WHERE id = ?))
            WHERE id = ?
            """,
            (email_n, loser, loser, loser, winner),
        )
        conn.execute("DELETE FROM binderdash_users WHERE id = ?", (loser,))
        logger.info("Merged user %s into %s via verified email", loser, winner)
        return winner

    @staticmethod
    def _user_row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
        out = {k: row[k] for k in row.keys()}
        out["is_admin"] = bool(out.get("is_admin"))
        out["is_active"] = bool(out.get("is_active", 1))
        return out

    def _get_user_row(
        self, conn: sqlite3.Connection, user_id: int
    ) -> Optional[Dict[str, Any]]:
        row = conn.execute(
            "SELECT * FROM binderdash_users WHERE id = ?", (user_id,)
        ).fetchone()
        return self._user_row_to_dict(row) if row is not None else None

    def get_user_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        with self._lock:
            return self._get_user_row(self._get_conn(), user_id)

    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        email_n = _normalise_email(email)
        if email_n is None:
            return None
        with self._lock:
            row = self._get_conn().execute(
                "SELECT * FROM binderdash_users WHERE email = ?", (email_n,)
            ).fetchone()
            return self._user_row_to_dict(row) if row is not None else None

    def get_user_by_identity(
        self, provider: str, identifier: str
    ) -> Optional[Dict[str, Any]]:
        provider = (provider or "").strip()
        identifier = (identifier or "").strip()
        if not provider or not identifier:
            return None
        if provider != "google" or "@" in identifier:
            identifier = identifier.lower()
        with self._lock:
            row = self._get_conn().execute(
                """
                SELECT u.* FROM binderdash_users u
                JOIN binderdash_user_identities i ON i.user_id = u.id
                WHERE i.provider = ? AND i.identifier = ?
                """,
                (provider, identifier),
            ).fetchone()
            return self._user_row_to_dict(row) if row is not None else None

    def list_users(self) -> List[Dict[str, Any]]:
        with self._lock:
            rows = self._get_conn().execute(
                """
                SELECT u.*, (
                    SELECT COUNT(*) FROM binderdash_api_keys k
                    WHERE k.user_id = u.id AND k.revoked_at IS NULL
                ) AS api_key_count
                FROM binderdash_users u
                ORDER BY u.email IS NULL, u.email, u.id
                """
            ).fetchall()
            return [self._user_row_to_dict(r) for r in rows]

    def list_user_identities(self, user_id: int) -> List[Dict[str, Any]]:
        with self._lock:
            rows = self._get_conn().execute(
                "SELECT * FROM binderdash_user_identities WHERE user_id = ?"
                " ORDER BY provider, identifier",
                (user_id,),
            ).fetchall()
            return [{k: r[k] for k in r.keys()} for r in rows]

    def set_user_admin(self, user_id: int, is_admin: bool) -> bool:
        with self._lock:
            conn = self._get_conn()
            cur = conn.execute(
                "UPDATE binderdash_users SET is_admin = ? WHERE id = ?",
                (1 if is_admin else 0, user_id),
            )
            conn.commit()
            return cur.rowcount > 0

    def sync_admin_flags(self, admin_user_ids: List[int]) -> int:
        ids = [int(i) for i in admin_user_ids]
        with self._lock:
            conn = self._get_conn()
            if ids:
                placeholders = ",".join("?" * len(ids))
                cur = conn.execute(
                    f"UPDATE binderdash_users SET is_admin = CASE"
                    f" WHEN id IN ({placeholders}) THEN 1 ELSE 0 END"
                    f" WHERE is_admin != CASE WHEN id IN ({placeholders}) THEN 1 ELSE 0 END",
                    ids + ids,
                )
            else:
                cur = conn.execute(
                    "UPDATE binderdash_users SET is_admin = 0 WHERE is_admin != 0"
                )
            conn.commit()
            return cur.rowcount

    @staticmethod
    def _key_row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
        out = {k: row[k] for k in row.keys()}
        out.pop("key_hash", None)  # never leaves the repository
        if "is_admin" in out:
            out["is_admin"] = bool(out["is_admin"])
        return out

    def create_api_key(
        self,
        *,
        user_id: int,
        name: str,
        key_hash: str,
        key_prefix: str,
        expires_at: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        with self._lock:
            conn = self._get_conn()
            cur = conn.execute(
                "INSERT INTO binderdash_api_keys"
                " (user_id, name, key_prefix, key_hash, expires_at)"
                " VALUES (?, ?, ?, ?, ?)",
                (user_id, name, key_prefix, key_hash, expires_at),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM binderdash_api_keys WHERE id = ?", (cur.lastrowid,)
            ).fetchone()
            return self._key_row_to_dict(row) if row is not None else None

    def list_api_keys(self, user_id: Optional[int] = None) -> List[Dict[str, Any]]:
        with self._lock:
            conn = self._get_conn()
            if user_id is None:
                rows = conn.execute(
                    "SELECT k.*, u.email AS user_email FROM binderdash_api_keys k"
                    " JOIN binderdash_users u ON u.id = k.user_id"
                    " ORDER BY k.created_at DESC, k.id DESC"
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM binderdash_api_keys WHERE user_id = ?"
                    " ORDER BY created_at DESC, id DESC",
                    (user_id,),
                ).fetchall()
            return [self._key_row_to_dict(r) for r in rows]

    def get_api_key(self, key_id: int) -> Optional[Dict[str, Any]]:
        with self._lock:
            row = self._get_conn().execute(
                "SELECT * FROM binderdash_api_keys WHERE id = ?", (key_id,)
            ).fetchone()
            return self._key_row_to_dict(row) if row is not None else None

    def get_api_key_by_hash(self, key_hash: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            row = self._get_conn().execute(
                """
                SELECT k.id, k.user_id, k.name, k.key_prefix, k.expires_at,
                       k.revoked_at, k.last_used_at,
                       u.email AS user_email, u.display_name AS user_display_name,
                       u.is_admin, u.is_active,
                       (SELECT i.provider FROM binderdash_user_identities i
                        WHERE i.user_id = u.id
                        ORDER BY i.last_login_at DESC, i.id LIMIT 1) AS provider,
                       (SELECT i.identifier FROM binderdash_user_identities i
                        WHERE i.user_id = u.id
                        ORDER BY i.last_login_at DESC, i.id LIMIT 1) AS identifier
                FROM binderdash_api_keys k
                JOIN binderdash_users u ON u.id = k.user_id
                WHERE k.key_hash = ?
                """,
                (key_hash,),
            ).fetchone()
            if row is None:
                return None
            out = {k: row[k] for k in row.keys()}
            out["is_admin"] = bool(out["is_admin"])
            out["is_active"] = bool(out["is_active"])
            return out

    def rename_api_key(
        self, key_id: int, name: str, *, user_id: Optional[int] = None
    ) -> bool:
        with self._lock:
            conn = self._get_conn()
            if user_id is None:
                cur = conn.execute(
                    "UPDATE binderdash_api_keys SET name = ? WHERE id = ?",
                    (name, key_id),
                )
            else:
                cur = conn.execute(
                    "UPDATE binderdash_api_keys SET name = ?"
                    " WHERE id = ? AND user_id = ?",
                    (name, key_id, user_id),
                )
            conn.commit()
            return cur.rowcount > 0

    def revoke_api_key(self, key_id: int, *, user_id: Optional[int] = None) -> bool:
        with self._lock:
            conn = self._get_conn()
            if user_id is None:
                cur = conn.execute(
                    "UPDATE binderdash_api_keys SET revoked_at = datetime('now')"
                    " WHERE id = ? AND revoked_at IS NULL",
                    (key_id,),
                )
            else:
                cur = conn.execute(
                    "UPDATE binderdash_api_keys SET revoked_at = datetime('now')"
                    " WHERE id = ? AND user_id = ? AND revoked_at IS NULL",
                    (key_id, user_id),
                )
            conn.commit()
            return cur.rowcount > 0

    def touch_api_keys_last_used(self, items: List[Dict[str, Any]]) -> int:
        if not items:
            return 0
        pairs = [(it["last_used_at"], int(it["id"])) for it in items]
        with self._lock:
            conn = self._get_conn()
            cur = conn.executemany(
                "UPDATE binderdash_api_keys SET last_used_at = ? WHERE id = ?", pairs
            )
            conn.commit()
            return cur.rowcount

    def get_tag_metrics_cache(
        self,
        *,
        run_id: str,
        design_id: str,
        source_path: str,
        structure_filename: str,
        binder_chain: str,
        target_chains: str,
        distant_from: str,
        sasa_probe_radius: float,
        sasa_n_points: int,
        sasa_threshold: float,
        more_distant_threshold: float,
    ) -> Optional[Dict[str, Any]]:
        with self._lock:
            cur = self._get_conn().execute(
                """
                SELECT metrics_json FROM binderdash_tag_metrics_cache
                WHERE run_id = ? AND design_id = ? AND source_path = ?
                  AND structure_filename = ? AND binder_chain = ?
                  AND target_chains = ? AND distant_from = ?
                  AND sasa_probe_radius = ? AND sasa_n_points = ?
                  AND sasa_threshold = ? AND more_distant_threshold = ?
                """,
                (
                    run_id,
                    design_id,
                    source_path,
                    structure_filename,
                    binder_chain,
                    target_chains,
                    distant_from,
                    float(sasa_probe_radius),
                    int(sasa_n_points),
                    float(sasa_threshold),
                    float(more_distant_threshold),
                ),
            )
            row = cur.fetchone()
            if row is None:
                return None
            return json.loads(row["metrics_json"])

    def upsert_tag_metrics_cache(
        self,
        *,
        run_id: str,
        design_id: str,
        source_path: str,
        structure_filename: str,
        binder_chain: str,
        target_chains: str,
        distant_from: str,
        sasa_probe_radius: float,
        sasa_n_points: int,
        sasa_threshold: float,
        more_distant_threshold: float,
        metrics: Dict[str, Any],
    ) -> None:
        payload = json.dumps(metrics, default=str)
        with self._lock:
            self._get_conn().execute(
                """
                INSERT INTO binderdash_tag_metrics_cache (
                    run_id, design_id, source_path, structure_filename,
                    binder_chain, target_chains, distant_from,
                    sasa_probe_radius, sasa_n_points, sasa_threshold, more_distant_threshold,
                    metrics_json, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
                ON CONFLICT(
                    run_id, design_id, source_path, structure_filename,
                    binder_chain, target_chains, distant_from,
                    sasa_probe_radius, sasa_n_points, sasa_threshold, more_distant_threshold
                ) DO UPDATE SET
                    metrics_json = excluded.metrics_json,
                    updated_at = datetime('now')
                """,
                (
                    run_id,
                    design_id,
                    source_path,
                    structure_filename,
                    binder_chain,
                    target_chains,
                    distant_from,
                    float(sasa_probe_radius),
                    int(sasa_n_points),
                    float(sasa_threshold),
                    float(more_distant_threshold),
                    payload,
                ),
            )
            self._get_conn().commit()

    def get_structural_metrics_cache(
        self,
        *,
        run_id: str,
        design_id: str,
        source_path: str,
        structure_filename: str,
        binder_chains: str,
        target_chains: str,
    ) -> Optional[Dict[str, Any]]:
        with self._lock:
            cur = self._get_conn().execute(
                """
                SELECT metrics_json FROM binderdash_structural_metrics_cache
                WHERE run_id = ? AND design_id = ? AND source_path = ?
                  AND structure_filename = ? AND binder_chains = ? AND target_chains = ?
                """,
                (run_id, design_id, source_path, structure_filename, binder_chains, target_chains),
            )
            row = cur.fetchone()
            if row is None:
                return None
            return json.loads(row["metrics_json"])

    def upsert_structural_metrics_cache(
        self,
        *,
        run_id: str,
        design_id: str,
        source_path: str,
        structure_filename: str,
        binder_chains: str,
        target_chains: str,
        metrics: Dict[str, Any],
    ) -> None:
        payload = json.dumps(metrics, default=str)
        with self._lock:
            self._get_conn().execute(
                """
                INSERT INTO binderdash_structural_metrics_cache (
                    run_id, design_id, source_path, structure_filename,
                    binder_chains, target_chains, metrics_json, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
                ON CONFLICT(
                    run_id, design_id, source_path, structure_filename,
                    binder_chains, target_chains
                ) DO UPDATE SET
                    metrics_json = excluded.metrics_json,
                    updated_at = datetime('now')
                """,
                (
                    run_id,
                    design_id,
                    source_path,
                    structure_filename,
                    binder_chains,
                    target_chains,
                    payload,
                ),
            )
            self._get_conn().commit()

    def create_saved_set(
        self,
        *,
        saved_set_id: str,
        name: str,
        source_run_ids: List[str],
        filter_params: Dict[str, Any],
        result_summary: Dict[str, Any],
    ) -> None:
        with self._lock:
            self._get_conn().execute(
                """
                INSERT INTO binderdash_saved_sets (
                    id, name, source_run_ids, filter_params, result_summary
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    saved_set_id,
                    name,
                    json.dumps(source_run_ids),
                    json.dumps(filter_params, default=str),
                    json.dumps(result_summary, default=str),
                ),
            )
            self._get_conn().commit()

    def _saved_set_row_to_dict(self, row) -> Dict[str, Any]:
        return {
            "id": row["id"],
            "name": row["name"],
            "created_at": row["created_at"],
            "source_run_ids": json.loads(row["source_run_ids"]),
            "filter_params": json.loads(row["filter_params"]),
            "result_summary": json.loads(row["result_summary"]),
        }

    def list_saved_sets(self) -> List[Dict[str, Any]]:
        with self._lock:
            cur = self._get_conn().execute(
                "SELECT * FROM binderdash_saved_sets ORDER BY created_at DESC"
            )
            return [self._saved_set_row_to_dict(row) for row in cur.fetchall()]

    def get_saved_set(self, saved_set_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            cur = self._get_conn().execute(
                "SELECT * FROM binderdash_saved_sets WHERE id = ?", (saved_set_id,)
            )
            row = cur.fetchone()
            return self._saved_set_row_to_dict(row) if row is not None else None

    def delete_saved_set(self, saved_set_id: str) -> bool:
        with self._lock:
            conn = self._get_conn()
            conn.execute(
                "DELETE FROM binderdash_saved_set_designs WHERE saved_set_id = ?",
                (saved_set_id,),
            )
            cur = conn.execute(
                "DELETE FROM binderdash_saved_sets WHERE id = ?", (saved_set_id,)
            )
            conn.commit()
            return cur.rowcount > 0

    def rename_saved_set(self, saved_set_id: str, name: str) -> bool:
        with self._lock:
            cur = self._get_conn().execute(
                "UPDATE binderdash_saved_sets SET name = ? WHERE id = ?",
                (name, saved_set_id),
            )
            self._get_conn().commit()
            return cur.rowcount > 0

    def add_saved_set_designs(
        self, saved_set_id: str, designs: List[Dict[str, Any]]
    ) -> None:
        if not designs:
            return
        rows = [
            (
                saved_set_id,
                str(d["design_id"]),
                str(d["run_id"]),
                str(d.get("source_path") or ""),
                d.get("final_rank"),
                d.get("quality_score"),
                1 if d.get("in_diverse_set") else 0,
                json.dumps(d.get("metrics") or {}, default=str),
            )
            for d in designs
        ]
        with self._lock:
            self._get_conn().executemany(
                """
                INSERT INTO binderdash_saved_set_designs (
                    saved_set_id, design_id, run_id, source_path,
                    final_rank, quality_score, in_diverse_set, metrics_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(saved_set_id, design_id, run_id, source_path) DO UPDATE SET
                    final_rank = excluded.final_rank,
                    quality_score = excluded.quality_score,
                    in_diverse_set = excluded.in_diverse_set,
                    metrics_json = excluded.metrics_json
                """,
                rows,
            )
            self._get_conn().commit()

    def list_saved_set_designs(self, saved_set_id: str) -> List[Dict[str, Any]]:
        with self._lock:
            cur = self._get_conn().execute(
                """
                SELECT design_id, run_id, source_path, final_rank, quality_score,
                       in_diverse_set, metrics_json
                FROM binderdash_saved_set_designs
                WHERE saved_set_id = ?
                ORDER BY final_rank ASC
                """,
                (saved_set_id,),
            )
            return [
                {
                    "design_id": row["design_id"],
                    "run_id": row["run_id"],
                    "source_path": row["source_path"],
                    "final_rank": row["final_rank"],
                    "quality_score": row["quality_score"],
                    "in_diverse_set": bool(row["in_diverse_set"]),
                    "metrics": json.loads(row["metrics_json"]),
                }
                for row in cur.fetchall()
            ]
