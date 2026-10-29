"""Shared fixtures.

Database tests run against a throwaway database (default ``roomly_test`` on the dev server
from ``script/database.sh``; override with ROOMLY_TEST_DATABASE_URL). The schema is rebuilt
from db/migrations once per session and every table is truncated before each test. Without
a reachable server those tests are skipped locally and fail in CI.
"""

import asyncio
import itertools
import json
import os
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

import psycopg
import pytest
from fastapi_reborn import FastAPI
from fastapi_reborn.http.requests import Request
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo

from roomly.config import Settings
from roomly.db import Database, migrate
from roomly.main import create_app

TEST_DATABASE_URL = os.environ.get("ROOMLY_TEST_DATABASE_URL", "postgresql://roomly@127.0.0.1:5433/roomly_test")
PASSWORD = "correct horse battery"


@pytest.fixture(scope="session")
def database_url() -> str:
    dbname = conninfo_to_dict(TEST_DATABASE_URL)["dbname"]
    try:
        with psycopg.connect(make_conninfo(TEST_DATABASE_URL, dbname="postgres"), autocommit=True) as admin:
            if admin.execute("SELECT 1 FROM pg_database WHERE datname = %s", (dbname,)).fetchone() is None:
                admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(dbname)))
    except psycopg.OperationalError as exc:
        if os.environ.get("CI"):
            raise
        pytest.skip(f"Postgres not reachable for {TEST_DATABASE_URL} (start script/database.sh): {exc}")
    with psycopg.connect(TEST_DATABASE_URL, autocommit=True) as conn:
        conn.execute("DROP SCHEMA public CASCADE")
        conn.execute("CREATE SCHEMA public")
    migrate(TEST_DATABASE_URL, Settings.from_env({}).migrations_dir)
    return TEST_DATABASE_URL


@pytest.fixture(scope="session")
def database(database_url: str) -> Iterator[Database]:
    db = Database(database_url, min_size=1, max_size=4)
    db.open()
    yield db
    db.close()


@pytest.fixture
def db(database: Database) -> Database:
    """The pool, with every table emptied first."""
    with database.transaction() as conn:
        tables = [r[0] for r in conn.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND tablename <> 'schema_migration'"
        )]
        conn.execute(sql.SQL("TRUNCATE {} RESTART IDENTITY CASCADE").format(sql.SQL(", ").join(map(sql.Identifier, tables))))
    return database


@pytest.fixture(scope="session")
def app(database: Database, database_url: str) -> FastAPI:
    settings = Settings.from_env({"DATABASE_URL": database_url, "ROOMLY_PASSWORD_ITERATIONS": "1000"})
    return create_app(settings, database)


@dataclass(frozen=True)
class Resp:
    status: int
    json: Any
    headers: dict[str, str]


class Api:
    """Drive the app in-process: real routing, controllers, services and SQL; no sockets."""

    _counter = itertools.count(1)

    def __init__(self, app: FastAPI, db: Database) -> None:
        self.app = app
        self.db = db

    def call(self, method: str, path: str, body: Any = None, token: str | None = None) -> Resp:
        headers = [("host", "test")]
        raw = b""
        if body is not None:
            raw = json.dumps(body).encode()
            headers += [("content-type", "application/json"), ("content-length", str(len(raw)))]
        if token:
            headers.append(("authorization", f"Bearer {token}"))
        path, _, query = path.partition("?")
        response = asyncio.run(self.app.handle(Request(method, path, query_string=query, headers=headers, body=raw)))
        data = json.loads(response.body) if response.body else None
        return Resp(response.status_code, data, dict(response.headers.items()))

    def get(self, path: str, token: str | None = None) -> Resp:
        return self.call("GET", path, token=token)

    def post(self, path: str, body: Any = None, token: str | None = None) -> Resp:
        return self.call("POST", path, {} if body is None else body, token)

    def put(self, path: str, body: Any = None, token: str | None = None) -> Resp:
        return self.call("PUT", path, {} if body is None else body, token)

    def patch(self, path: str, body: Any = None, token: str | None = None) -> Resp:
        return self.call("PATCH", path, {} if body is None else body, token)

    def delete(self, path: str, body: Any = None, token: str | None = None) -> Resp:
        return self.call("DELETE", path, body, token)

    # --- builders ----------------------------------------------------------------------

    def user(self, name: str | None = None, *, admin: bool = False) -> tuple[str, dict[str, Any]]:
        """Sign up a fresh user; returns (token, user json)."""
        n = next(self._counter)
        r = self.post("/auth/sign-up", {"email": f"user{n}@example.com", "password": PASSWORD,
                                        "display_name": name or f"User {n}"})
        assert r.status == 201, r.json
        if admin:
            with self.db.transaction() as conn:
                conn.execute("UPDATE app_user SET role = 'admin' WHERE id = %s", (r.json["user"]["id"],))
        return r.json["token"], r.json["user"]

    def group(self, owner_token: str, *member_tokens: str, name: str = "Roomies") -> str:
        """A group owned by ``owner_token`` with the given members already joined."""
        r = self.post("/groups", {"name": name}, owner_token)
        assert r.status == 201, r.json
        group_id = r.json["id"]
        for token in member_tokens:
            email = self.get("/me", token).json["email"]
            inv = self.post(f"/groups/{group_id}/invitations", {"email": email}, owner_token)
            assert inv.status == 201, inv.json
            accepted = self.post(f"/invitations/{inv.json['id']}/accept", token=token)
            assert accepted.status == 201, accepted.json
        return group_id

    def listing(self, token: str, **overrides: Any) -> dict[str, Any]:
        """A searchable manual listing at a unique address unless overridden."""
        n = next(self._counter)
        body = {"address_line": f"{n} Bedford Ave", "unit": "1A", "borough": "brooklyn", "postal_code": "11211",
                "advertised_rent_cents": 300_000, "bedrooms": 2, "bathrooms": 1, "area_sqft": 750,
                "move_in_date": "2026-12-01", "min_lease_days": 365, "amenities": ["laundry"],
                "latitude": 40.71, "longitude": -73.96}
        body.update(overrides)
        r = self.post("/listings", {k: v for k, v in body.items() if v is not ...}, token)
        assert r.status == 201, r.json
        return r.json


@pytest.fixture
def api(app: FastAPI, db: Database) -> Api:
    return Api(app, db)
