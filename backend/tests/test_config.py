import pytest

from roomly.config import Settings


def test_dev_defaults() -> None:
    s = Settings.from_env({})
    assert (s.env, s.host, s.port, s.log_level) == ("dev", "127.0.0.1", 8000, "DEBUG")
    assert s.database_url.startswith("postgresql://roomly@127.0.0.1:5433/")


def test_prod_binds_all_interfaces_and_requires_database_url() -> None:
    with pytest.raises(KeyError):
        Settings.from_env({"ROOMLY_ENV": "prod"})
    s = Settings.from_env({"ROOMLY_ENV": "prod", "DATABASE_URL": "postgresql://db/x"})
    assert (s.host, s.log_level, s.database_url) == ("0.0.0.0", "INFO", "postgresql://db/x")


def test_overrides_and_invalid_env() -> None:
    s = Settings.from_env({"ROOMLY_HOST": "10.0.0.1", "ROOMLY_PORT": "9000", "ROOMLY_LOG_LEVEL": "warning"})
    assert (s.host, s.port, s.log_level) == ("10.0.0.1", 9000, "WARNING")
    with pytest.raises(ValueError):
        Settings.from_env({"ROOMLY_ENV": "staging"})
