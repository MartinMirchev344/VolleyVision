import os
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine, text

import volleyanalytics.models  # noqa: F401  (registers feature tables)
from volleyanalytics.db import Base, database_url


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
                == "0003_match_stats"
            )
            # The ORM models and the migrations must describe the same schema.
            assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []
            command.downgrade(config, "0002_videos")
            assert connection.scalar(text("SELECT to_regclass('touches')")) is None
            assert "match_id" not in {
                row[0]
                for row in connection.execute(
                    text(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_schema = current_schema() AND table_name = 'videos'"
                    )
                )
            }
            command.downgrade(config, "base")
            assert connection.scalar(text("SELECT to_regclass('videos')")) is None
            assert connection.scalar(text("SELECT count(*) FROM alembic_version")) == 0
            command.upgrade(config, "head")
            command.upgrade(config, "head")  # Rerun is harmless.
            connection.commit()
        with engine.connect() as connection:
            assert (
                connection.scalar(text(f'SELECT version_num FROM "{schema}".alembic_version'))
                == "0003_match_stats"
            )
    finally:
        with engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        engine.dispose()
