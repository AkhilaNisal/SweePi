"""SQLite-backed storage for schedules, history, and settings."""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path


class BridgeStorage:
    """Thread-safe runtime storage."""

    def __init__(self, db_path: Path):
        self._db_path = db_path
        self._lock = threading.Lock()
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._lock, self._connect() as conn:
            conn.executescript(
                '''
                CREATE TABLE IF NOT EXISTS schedules (
                    id TEXT PRIMARY KEY,
                    enabled INTEGER NOT NULL,
                    timezone TEXT NOT NULL,
                    days_json TEXT NOT NULL,
                    time_local TEXT NOT NULL,
                    map_id TEXT,
                    selection_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    last_run_at TEXT,
                    next_run_at TEXT
                );

                CREATE TABLE IF NOT EXISTS history (
                    task_id TEXT PRIMARY KEY,
                    task_type TEXT NOT NULL,
                    map_id TEXT,
                    selection_json TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    ended_at TEXT,
                    result TEXT,
                    coverage_percent REAL,
                    notes TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value_json TEXT NOT NULL
                );
                '''
            )

    def list_schedules(self) -> list[dict]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                'SELECT * FROM schedules ORDER BY time_local ASC, id ASC'
            ).fetchall()
        return [self._schedule_row_to_dict(row) for row in rows]

    def upsert_schedule(self, schedule: dict) -> dict:
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self._connect() as conn:
            existing = conn.execute(
                'SELECT created_at FROM schedules WHERE id = ?',
                (schedule['id'],),
            ).fetchone()
            created_at = existing['created_at'] if existing else now
            conn.execute(
                '''
                INSERT OR REPLACE INTO schedules (
                    id, enabled, timezone, days_json, time_local, map_id,
                    selection_json, created_at, updated_at, last_run_at, next_run_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''',
                (
                    schedule['id'],
                    1 if schedule.get('enabled', True) else 0,
                    schedule.get('timezone', 'UTC'),
                    json.dumps(schedule.get('days', [])),
                    schedule['time_local'],
                    schedule.get('map_id'),
                    json.dumps(schedule.get('selection', {})),
                    created_at,
                    now,
                    schedule.get('last_run_at'),
                    schedule.get('next_run_at'),
                ),
            )
        return self.get_schedule(schedule['id'])

    def get_schedule(self, schedule_id: str) -> dict | None:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                'SELECT * FROM schedules WHERE id = ?',
                (schedule_id,),
            ).fetchone()
        if row is None:
            return None
        return self._schedule_row_to_dict(row)

    def delete_schedule(self, schedule_id: str) -> bool:
        with self._lock, self._connect() as conn:
            cursor = conn.execute(
                'DELETE FROM schedules WHERE id = ?',
                (schedule_id,),
            )
        return cursor.rowcount > 0

    def mark_schedule_run(self, schedule_id: str, next_run_at: str | None) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self._connect() as conn:
            conn.execute(
                '''
                UPDATE schedules
                SET last_run_at = ?, next_run_at = ?, updated_at = ?
                WHERE id = ?
                ''',
                (now, next_run_at, now, schedule_id),
            )

    def history_items(self) -> list[dict]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                'SELECT * FROM history ORDER BY started_at DESC'
            ).fetchall()
        return [self._history_row_to_dict(row) for row in rows]

    def upsert_history(self, item: dict) -> dict:
        with self._lock, self._connect() as conn:
            conn.execute(
                '''
                INSERT OR REPLACE INTO history (
                    task_id, task_type, map_id, selection_json, started_at,
                    ended_at, result, coverage_percent, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''',
                (
                    item['task_id'],
                    item.get('task_type', 'full'),
                    item.get('map_id'),
                    json.dumps(item.get('selection', {})),
                    item['started_at'],
                    item.get('ended_at'),
                    item.get('result'),
                    item.get('coverage_percent'),
                    json.dumps(item.get('notes', {})),
                ),
            )
        return self.get_history(item['task_id'])

    def get_history(self, task_id: str) -> dict | None:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                'SELECT * FROM history WHERE task_id = ?',
                (task_id,),
            ).fetchone()
        if row is None:
            return None
        return self._history_row_to_dict(row)

    def set_setting(self, key: str, value: dict) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                'INSERT OR REPLACE INTO settings (key, value_json) VALUES (?, ?)',
                (key, json.dumps(value)),
            )

    def get_setting(self, key: str, default: dict | None = None) -> dict | None:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                'SELECT value_json FROM settings WHERE key = ?',
                (key,),
            ).fetchone()
        if row is None:
            return default
        return json.loads(row['value_json'])

    def _schedule_row_to_dict(self, row: sqlite3.Row) -> dict:
        return {
            'id': row['id'],
            'enabled': bool(row['enabled']),
            'timezone': row['timezone'],
            'days': json.loads(row['days_json']),
            'time_local': row['time_local'],
            'map_id': row['map_id'],
            'selection': json.loads(row['selection_json']),
            'created_at': row['created_at'],
            'updated_at': row['updated_at'],
            'last_run_at': row['last_run_at'],
            'next_run_at': row['next_run_at'],
        }

    def _history_row_to_dict(self, row: sqlite3.Row) -> dict:
        return {
            'task_id': row['task_id'],
            'task_type': row['task_type'],
            'map_id': row['map_id'],
            'selection': json.loads(row['selection_json']),
            'started_at': row['started_at'],
            'ended_at': row['ended_at'],
            'result': row['result'],
            'coverage_percent': row['coverage_percent'],
            'notes': json.loads(row['notes']),
        }
