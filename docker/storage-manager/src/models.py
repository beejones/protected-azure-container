import json
import sqlite3
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_db(db_path: str) -> None:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS registrations (
                volume_name TEXT NOT NULL,
                path TEXT NOT NULL,
                algorithm TEXT NOT NULL,
                params_json TEXT NOT NULL,
                description TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                last_cleaned TEXT,
                files_removed_last_run INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY(volume_name, path)
            )
            """
        )


def upsert_registration(
    *,
    db_path: str,
    volume_name: str,
    path: str,
    algorithm: str,
    params: dict[str, Any],
    description: str | None,
) -> None:
    now = _now_iso()
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO registrations (
                volume_name, path, algorithm, params_json, description, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(volume_name, path)
            DO UPDATE SET
                algorithm=excluded.algorithm,
                params_json=excluded.params_json,
                description=excluded.description,
                updated_at=excluded.updated_at
            """,
            (
                volume_name,
                path,
                algorithm,
                json.dumps(params),
                description,
                now,
                now,
            ),
        )


def delete_registration(*, db_path: str, volume_name: str, path: str) -> int:
    with sqlite3.connect(db_path) as conn:
        cursor = conn.execute(
            "DELETE FROM registrations WHERE volume_name = ? AND path = ?",
            (volume_name, path),
        )
        return int(cursor.rowcount)


def list_registrations(db_path: str) -> list[dict[str, Any]]:
    with sqlite3.connect(db_path) as conn:
        cursor = conn.execute(
            """
            SELECT volume_name, path, algorithm, params_json, description, last_cleaned, files_removed_last_run
            FROM registrations
            ORDER BY volume_name, path
            """
        )
        rows = cursor.fetchall()

    out: list[dict[str, Any]] = []
    for row in rows:
        out.append(
            {
                "volume_name": str(row[0]),
                "path": str(row[1]),
                "algorithm": str(row[2]),
                "params": json.loads(str(row[3]) or "{}"),
                "description": row[4],
                "last_cleaned": row[5],
                "files_removed_last_run": int(row[6] or 0),
            }
        )
    return out


def mark_cleanup_result(
    *,
    db_path: str,
    volume_name: str,
    path: str,
    files_removed: int,
) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            UPDATE registrations
            SET last_cleaned = ?, files_removed_last_run = ?, updated_at = ?
            WHERE volume_name = ? AND path = ?
            """,
            (_now_iso(), int(files_removed), _now_iso(), volume_name, path),
        )


def list_registrations_by_volume(db_path: str) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in list_registrations(db_path):
        grouped[str(item["volume_name"])].append(item)
    return dict(grouped)
