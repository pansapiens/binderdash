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
                    data_json TEXT NOT NULL,
                    FOREIGN KEY(run_id) REFERENCES binderdash_runs(run_id) ON DELETE CASCADE,
                    UNIQUE(run_id, design_dedupe)
                );
                CREATE INDEX IF NOT EXISTS idx_designs_run_id
                    ON binderdash_designs(run_id);
                """
            )
            c.commit()

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
                did, pid, meth, sp, tag, good, payload = split_design_for_storage(d)
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
                        source_path, tag, good, data_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                "SELECT run_id, design_id, project_id, method, source_path, tag, good, data_json "
                "FROM binderdash_designs"
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

    def delete_run(self, run_id: str) -> bool:
        with self._lock:
            cur = self._get_conn().execute(
                "DELETE FROM binderdash_runs WHERE run_id = ?", (run_id,)
            )
            self._get_conn().commit()
            return cur.rowcount > 0
