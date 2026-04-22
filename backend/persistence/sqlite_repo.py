from __future__ import annotations

import json
import logging
import sqlite3
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import unquote

from .protocol import (
    design_dedupe_key,
    merge_design_from_storage,
    split_design_for_storage,
)

logger = logging.getLogger(__name__)


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
        return self._conn

    def init_schema(self) -> None:
        with self._lock:
            c = self._get_conn()
            c.execute("PRAGMA foreign_keys = ON")
            c.executescript(
                """
                CREATE TABLE IF NOT EXISTS binderdash_runs (
                    run_id TEXT PRIMARY KEY,
                    run_group_key TEXT NOT NULL UNIQUE,
                    project_id TEXT NOT NULL,
                    method TEXT NOT NULL,
                    run_name TEXT NOT NULL,
                    run_json TEXT NOT NULL
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
                    FOREIGN KEY(run_id) REFERENCES binderdash_runs(run_id) ON DELETE CASCADE,
                    UNIQUE(run_id, design_dedupe)
                );
                CREATE INDEX IF NOT EXISTS idx_designs_run_id
                    ON binderdash_designs(run_id);
                CREATE TABLE IF NOT EXISTS binderdash_auth_users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    provider TEXT NOT NULL,
                    identifier TEXT NOT NULL,
                    email TEXT,
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    last_login_at TEXT NOT NULL DEFAULT (datetime('now')),
                    UNIQUE(provider, identifier)
                );
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
                """
            )
            self._migrate_binder_chain_column(c)
            self._migrate_short_name_column(c)
            c.commit()

    def _migrate_binder_chain_column(self, c: sqlite3.Cursor) -> None:
        info = c.execute("PRAGMA table_info(binderdash_designs)").fetchall()
        names = {row[1] for row in info}
        if "binder_chain" in names:
            return
        try:
            c.execute("ALTER TABLE binderdash_designs ADD COLUMN binder_chain TEXT")
        except sqlite3.OperationalError as e:
            if "duplicate column" not in str(e).lower():
                raise

    def _migrate_short_name_column(self, c: sqlite3.Cursor) -> None:
        info = c.execute("PRAGMA table_info(binderdash_designs)").fetchall()
        names = {row[1] for row in info}
        if "short_name" in names:
            return
        try:
            c.execute("ALTER TABLE binderdash_designs ADD COLUMN short_name TEXT")
        except sqlite3.OperationalError as e:
            if "duplicate column" not in str(e).lower():
                raise

    def get_run_by_group_key(self, run_group_key: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            cur = self._get_conn().execute(
                "SELECT run_id, run_group_key, project_id, method, run_name, run_json "
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
                "run_json": json.loads(row["run_json"]),
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
        run_json_str = json.dumps(run_dict, default=str)

        with self._lock:
            conn = self._get_conn()
            conn.execute("DELETE FROM binderdash_designs WHERE run_id = ?", (run_id,))
            conn.execute(
                """
                INSERT INTO binderdash_runs (run_id, run_group_key, project_id, method, run_name, run_json)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id) DO UPDATE SET
                    run_group_key = excluded.run_group_key,
                    project_id = excluded.project_id,
                    method = excluded.method,
                    run_name = excluded.run_name,
                    run_json = excluded.run_json
                """,
                (run_id, run_group_key, project_id, method, run_name, run_json_str),
            )
            for d in designs:
                did, pid, meth, sp, tag, good, binder_chain, short_name, payload = (
                    split_design_for_storage(d)
                )
                dedupe = design_dedupe_key(did, sp or None)
                good_i: Optional[int]
                if good is None:
                    good_i = None
                else:
                    good_i = 1 if good else 0
                conn.execute(
                    """
                    INSERT INTO binderdash_designs (
                        run_id, design_dedupe, design_id, project_id, method,
                        source_path, tag, good, binder_chain, short_name, data_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    ),
                )
            conn.commit()

    def list_run_records(self) -> List[Dict[str, Any]]:
        with self._lock:
            cur = self._get_conn().execute(
                "SELECT run_id, run_group_key, project_id, method, run_name, run_json "
                "FROM binderdash_runs ORDER BY run_name"
            )
            return [dict(r) for r in cur.fetchall()]

    def list_all_design_dicts(self) -> List[Dict[str, Any]]:
        with self._lock:
            cur = self._get_conn().execute(
                "SELECT run_id, design_id, project_id, method, source_path, tag, good, "
                "binder_chain, short_name, data_json FROM binderdash_designs"
            )
            out: List[Dict[str, Any]] = []
            for row in cur.fetchall():
                data = json.loads(row["data_json"])
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
                out.append(
                    merge_design_from_storage(
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
                    )
                )
            return out

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
                "SELECT data_json, binder_chain FROM binderdash_designs "
                "WHERE run_id = ? AND design_dedupe = ?",
                (run_id, dedupe),
            )
            row = cur.fetchone()
            if row is None:
                return False
            data = json.loads(row["data_json"])
            if sequence is not None:
                data["Sequence"] = sequence
            new_json = json.dumps(data, default=str)
            if binder_chain is not None:
                bc = binder_chain.strip() or None
                conn.execute(
                    """
                    UPDATE binderdash_designs SET data_json = ?, binder_chain = ?
                    WHERE run_id = ? AND design_dedupe = ?
                    """,
                    (new_json, bc, run_id, dedupe),
                )
            else:
                conn.execute(
                    """
                    UPDATE binderdash_designs SET data_json = ?
                    WHERE run_id = ? AND design_dedupe = ?
                    """,
                    (new_json, run_id, dedupe),
                )
            conn.commit()
            return True

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
            cur = conn.execute("DELETE FROM binderdash_runs WHERE run_id = ?", (run_id,))
            conn.commit()
            return cur.rowcount > 0

    def record_login(
        self,
        provider: str,
        identifier: str,
        email: Optional[str] = None,
    ) -> None:
        with self._lock:
            conn = self._get_conn()
            conn.execute(
                """
                INSERT INTO binderdash_auth_users (provider, identifier, email, last_login_at)
                VALUES (?, ?, ?, datetime('now'))
                ON CONFLICT(provider, identifier) DO UPDATE SET
                    last_login_at = datetime('now'),
                    email = COALESCE(excluded.email, binderdash_auth_users.email)
                """,
                (provider, identifier, email),
            )
            conn.commit()

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
