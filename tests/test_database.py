import os
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

from volleyvision.db import database_url


@pytest.mark.integration
def test_migration_roundtrip_and_persistence(monkeypatch):
    if not os.environ.get("TEST_DATABASE_URL"):
        pytest.skip("Set TEST_DATABASE_URL to a dedicated disposable PostgreSQL database")
    url = database_url("TEST_DATABASE_URL")
    monkeypatch.setenv("DATABASE_URL", url)
    engine = create_engine(url, connect_args={"connect_timeout": 5})
    schema = "vv_test_" + uuid4().hex
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    try:
        with engine.connect() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
            connection.execute(text(f'SET search_path TO "{schema}"'))
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
            assert (
                connection.scalar(text("SELECT version_num FROM alembic_version"))
                == "0001_bootstrap"
            )
            command.downgrade(config, "base")
            assert connection.scalar(text("SELECT count(*) FROM alembic_version")) == 0
            command.upgrade(config, "head")
            command.upgrade(config, "head")  # Rerun is harmless.
            connection.commit()
        with engine.connect() as connection:
            assert (
                connection.scalar(text(f'SELECT version_num FROM "{schema}".alembic_version'))
                == "0001_bootstrap"
            )
    finally:
        with engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        engine.dispose()
