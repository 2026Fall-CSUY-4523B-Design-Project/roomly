"""Environment-driven settings. ROOMLY_ENV selects dev (default) or prod defaults."""

from collections.abc import Mapping
from dataclasses import dataclass

_DEV_DATABASE_URL = "postgresql://roomly@127.0.0.1:5433/postgres"


@dataclass(frozen=True)
class Settings:
    env: str
    host: str
    port: int
    log_level: str
    database_url: str

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
        )
