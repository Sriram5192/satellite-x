import sqlite3

import pytest

from satellite_x.persistence.database import SatelliteXDatabase


def test_database_initialization_and_access_audit(tmp_path):
    database = SatelliteXDatabase(tmp_path / "satellite_x.db")
    database.initialize()
    database.log_access(
        officer_id="O1", action="VIEW_VILLAGE_SUMMARY", village_code="V1",
        field_id=None, case_id=None, purpose="damage", allowed=True,
        reason_code="GOVERNMENT_SCOPE_ALLOWED",
    )
    with database.connect() as connection:
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert {"fields", "analysis_runs", "government_authorizations", "government_access_logs", "village_summaries"} <= tables
        row = connection.execute("SELECT allowed, reason_code FROM government_access_logs").fetchone()
        assert row[0] == 1
        assert row[1] == "GOVERNMENT_SCOPE_ALLOWED"


def test_generic_json_save_rejects_identifier_injection(tmp_path):
    database = SatelliteXDatabase(tmp_path / "satellite_x.db")
    database.initialize()
    with pytest.raises(ValueError, match="columns are not allowed"):
        database.save_json(
            "village_summaries",
            {"village_code) VALUES ('x'); DROP TABLE fields; --": "V1"},
            "summary_json",
            {"safe": True},
        )
