import os
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

from volleyanalytics.db import database_url


@pytest.fixture
def database(monkeypatch):
    """A migrated, disposable schema in the dedicated test database."""
    if not os.environ.get("TEST_DATABASE_URL"):
        pytest.skip("Set TEST_DATABASE_URL to a dedicated disposable PostgreSQL database")
    url = database_url("TEST_DATABASE_URL")
    monkeypatch.setenv("DATABASE_URL", url)
    schema = "vv_test_" + uuid4().hex
    admin = create_engine(url, connect_args={"connect_timeout": 5})
    with admin.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_engine(
        url, connect_args={"connect_timeout": 5, "options": f"-csearch_path={schema}"}
    )
    try:
        config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
        with engine.begin() as connection:
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
        yield engine
    finally:
        engine.dispose()
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        admin.dispose()
