from __future__ import annotations

import json
import sqlite3
from pathlib import Path


SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS fields (
  field_id TEXT PRIMARY KEY,
  owner_user_id TEXT,
  village_code TEXT,
  crop_type TEXT,
  sowing_date TEXT,
  acres REAL NOT NULL,
  boundary_geojson TEXT NOT NULL,
  boundary_source TEXT NOT NULL,
  legal_boundary INTEGER NOT NULL DEFAULT 0,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS analysis_runs (
  run_id TEXT PRIMARY KEY,
  field_id TEXT NOT NULL,
  scene_id TEXT,
  status TEXT NOT NULL,
  result_json TEXT NOT NULL,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(field_id) REFERENCES fields(field_id)
);
CREATE TABLE IF NOT EXISTS government_authorizations (
  authorization_id TEXT PRIMARY KEY,
  officer_id TEXT NOT NULL,
  status TEXT NOT NULL,
  authorization_json TEXT NOT NULL,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS government_access_logs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  officer_id TEXT NOT NULL,
  action TEXT NOT NULL,
  village_code TEXT,
  field_id TEXT,
  case_id TEXT,
  purpose TEXT NOT NULL,
  allowed INTEGER NOT NULL,
  reason_code TEXT NOT NULL,
  accessed_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS village_summaries (
  village_code TEXT NOT NULL,
  generated_at TEXT NOT NULL,
  summary_json TEXT NOT NULL,
  PRIMARY KEY(village_code, generated_at)
);
CREATE TABLE IF NOT EXISTS area_summaries (
  scope_level TEXT NOT NULL,
  scope_code TEXT NOT NULL,
  generated_at TEXT NOT NULL,
  summary_json TEXT NOT NULL,
  PRIMARY KEY(scope_level, scope_code, generated_at)
);
CREATE TABLE IF NOT EXISTS offline_verification_queue (
  event_id TEXT PRIMARY KEY,
  device_id TEXT NOT NULL,
  queued_at TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  payload_sha256 TEXT NOT NULL,
  sync_status TEXT NOT NULL CHECK(sync_status IN ('pending','synced','rejected')),
  server_receipt TEXT,
  synced_at TEXT
);
"""


class SatelliteXDatabase:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def connect(self):
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def initialize(self):
        with self.connect() as connection:
            connection.executescript(SCHEMA)

    def log_access(self, *, officer_id, action, village_code, field_id, case_id, purpose, allowed, reason_code):
        with self.connect() as connection:
            connection.execute(
                """INSERT INTO government_access_logs
                (officer_id, action, village_code, field_id, case_id, purpose, allowed, reason_code)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (officer_id, action, village_code, field_id, case_id, purpose, int(allowed), reason_code),
            )

    def save_json(self, table: str, key_columns: dict, json_column: str, payload: dict):
        allowed_columns = {
            "government_authorizations": {
                "authorization_id", "officer_id", "status", "authorization_json"
            },
            "village_summaries": {"village_code", "generated_at", "summary_json"},
            "area_summaries": {
                "scope_level", "scope_code", "generated_at", "summary_json"
            },
        }
        if table not in allowed_columns:
            raise ValueError("table is not allowed for generic JSON save")
        columns = [*key_columns, json_column]
        if not columns or not set(columns).issubset(allowed_columns[table]):
            raise ValueError("one or more JSON save columns are not allowed")
        if json_column not in {"authorization_json", "summary_json"}:
            raise ValueError("json_column is not allowed")
        placeholders = ",".join("?" for _ in columns)
        sql = f"INSERT OR REPLACE INTO {table} ({','.join(columns)}) VALUES ({placeholders})"
        values = [*key_columns.values(), json.dumps(payload, sort_keys=True)]
        with self.connect() as connection:
            connection.execute(sql, values)
