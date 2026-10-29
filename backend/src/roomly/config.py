"""Environment-driven settings. ROOMLY_ENV selects dev (default) or prod defaults."""

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

_DEV_DATABASE_URL = "postgresql://roomly@127.0.0.1:5433/postgres"
# backend/src/roomly/config.py -> repo root. Installed wheels have no repo: set ROOMLY_MIGRATIONS_DIR.
_REPO_DB = Path(__file__).resolve().parents[3] / "db"
_REPO_MIGRATIONS = _REPO_DB / "migrations"
_DEV_SQLITE_FALLBACK = _REPO_DB / "roomly.sqlite3"   # gitignored; outside db/data, which initdb owns


@dataclass(frozen=True)
class Settings:
    env: str
    host: str
    port: int
    log_level: str
    database_url: str
    migrations_dir: Path = _REPO_MIGRATIONS
    sqlite_fallback: Path | None = None  # used when Postgres is unreachable at startup
    fixtures: bool = False  # stub service methods answer with roomly.fixtures samples instead of 501

    @classmethod
    def from_env(cls, environ: Mapping[str, str]) -> Settings:
        env = environ.get("ROOMLY_ENV", "dev")
        if env not in ("dev", "prod"):
            raise ValueError(f"ROOMLY_ENV must be 'dev' or 'prod', got {env!r}")
        prod = env == "prod"
        return cls(
            env=env,
            host=environ.get("ROOMLY_HOST", "0.0.0.0" if prod else "127.0.0.1"),
            port=int(environ.get("ROOMLY_PORT", "8000")),
            log_level=environ.get("ROOMLY_LOG_LEVEL", "INFO" if prod else "DEBUG").upper(),
            # prod must set DATABASE_URL explicitly (KeyError = fail loudly)
            database_url=environ["DATABASE_URL"] if prod else environ.get("DATABASE_URL", _DEV_DATABASE_URL),
            migrations_dir=Path(environ.get("ROOMLY_MIGRATIONS_DIR", _REPO_MIGRATIONS)),
            sqlite_fallback=_fallback(environ.get("ROOMLY_SQLITE_FALLBACK"), prod),
            fixtures=_flag(environ.get("ROOMLY_FIXTURES"), default=not prod),
        )


def _fallback(value: str | None, prod: bool) -> Path | None:
    """Default: on in dev (db/roomly.sqlite3), off in prod. "off" or "" disables it."""
    if value is None:
        return None if prod else _DEV_SQLITE_FALLBACK
    return None if value.strip().lower() in ("", "off", "none", "false") else Path(value)


def _flag(value: str | None, *, default: bool) -> bool:
    if value is None:
        return default
    v = value.strip().lower()
    if v in ("1", "on", "true", "yes"):
        return True
    if v in ("", "0", "off", "false", "no"):
        return False
    raise ValueError(f"expected on/off, got {value!r}")
