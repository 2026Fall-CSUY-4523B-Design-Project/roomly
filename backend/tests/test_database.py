"""Postgres-first with SQLite fallback: which engine Roomly runs on, and when."""

import asyncio
import json
from pathlib import Path

import psycopg
import pytest
from fastapi_reborn.http.requests import Request

from roomly.config import Settings
from roomly.db import Database
from roomly.main import create_app

pytestmark = pytest.mark.unit

UNREACHABLE = "postgresql://roomly@127.0.0.1:1/roomly"   # nothing listens on port 1


def test_unreachable_postgres_falls_back_to_sqlite(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    db = Database(UNREACHABLE, fallback=tmp_path / "fallback.sqlite3")
    db.open()
    try:
        assert db.dialect == "sqlite"
        assert "falling back to SQLite" in caplog.text
        assert db.migrate(Settings.from_env({}).migrations_dir) == ["0001_init"]
        with db.transaction() as tx:
            assert tx.scalar("SELECT count(*) FROM app_user") == 0
    finally:
        db.close()
    assert (tmp_path / "fallback.sqlite3").exists()


def test_without_a_fallback_the_failure_is_loud(tmp_path: Path) -> None:
    with pytest.raises(psycopg.OperationalError):
        Database(UNREACHABLE).open()


def test_sqlite_url_runs_on_sqlite_only(tmp_path: Path) -> None:
    db = Database(f"sqlite:///{tmp_path / 'only.sqlite3'}")
    db.open()
    assert db.dialect == "sqlite"
    db.close()
    with pytest.raises(ValueError):
        Database("sqlite:///:memory:").open()


def test_fallback_defaults_on_in_dev_off_in_prod() -> None:
    assert Settings.from_env({}).sqlite_fallback is not None
    assert Settings.from_env({"ROOMLY_ENV": "prod", "DATABASE_URL": "postgresql://db/x"}).sqlite_fallback is None
    assert Settings.from_env({"ROOMLY_SQLITE_FALLBACK": "off"}).sqlite_fallback is None
    prod_opt_in = Settings.from_env({"ROOMLY_ENV": "prod", "DATABASE_URL": "postgresql://db/x",
                                     "ROOMLY_SQLITE_FALLBACK": "/var/lib/roomly/fallback.sqlite3"})
    assert prod_opt_in.sqlite_fallback == Path("/var/lib/roomly/fallback.sqlite3")


def test_health_reports_the_engine_in_use(tmp_path: Path) -> None:
    db = Database(UNREACHABLE, fallback=tmp_path / "f.sqlite3")
    app = create_app(Settings.from_env({}), db)
    db.open()
    try:
        resp = asyncio.run(app.handle(Request("GET", "/health")))
        assert json.loads(resp.body) == {"status": "ok", "database": "sqlite"}
    finally:
        db.close()
