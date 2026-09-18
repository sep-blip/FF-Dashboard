import os

import pytest

from database.repository import (
    DatabaseConfigurationError,
    database_url_from_env,
)


def test_database_url_required(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(DatabaseConfigurationError):
        database_url_from_env()


def test_database_url_from_env(monkeypatch):
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://user:pass@localhost:5432/db",
    )
    assert database_url_from_env().endswith("/db")
