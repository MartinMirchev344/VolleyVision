import os
from pathlib import Path
from uuid import UUID, uuid4

import cv2
import numpy as np
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import Session

from volleyanalytics.db import database_url
from volleyanalytics.ingest import import_video
from volleyanalytics.models import Video
from volleyanalytics.storage import LocalStorage


def _write_video(path: Path, shade: int) -> None:
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), 10, (160, 120))
    assert writer.isOpened(), "Test environment needs the MJPG codec"
    for index in range(10):
        writer.write(np.full((120, 160, 3), (shade + index) % 256, dtype=np.uint8))
    writer.release()


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


@pytest.mark.integration
def test_import_registers_in_place_and_is_idempotent(database, tmp_path):
    root = tmp_path / "matches"
    (root / "match-01").mkdir(parents=True)
    video_path = root / "match-01" / "match-01.avi"
    _write_video(video_path, shade=0)
    storage = LocalStorage(root)

    with Session(database) as session, session.begin():
        first = import_video(session, storage, video_path)
    assert first["already_registered"] is False
    assert first["storage_key"] == "match-01/match-01.avi"
    assert (first["width"], first["height"], first["frame_count"]) == (160, 120, 10)

    with Session(database) as session, session.begin():
        second = import_video(session, storage, video_path)
        assert session.scalar(select(func.count()).select_from(Video)) == 1
        stored = session.get(Video, UUID(first["video_id"]))
        assert stored.created_at.utcoffset() is not None  # Timezone-aware creation time.
    assert second["already_registered"] is True
    assert second["video_id"] == first["video_id"]


@pytest.mark.integration
def test_changed_file_or_duplicate_content_is_refused_without_partial_rows(database, tmp_path):
    root = tmp_path / "matches"
    root.mkdir()
    original = root / "rally.avi"
    _write_video(original, shade=0)
    storage = LocalStorage(root)
    with Session(database) as session, session.begin():
        import_video(session, storage, original)

    copy = root / "rally-copy.avi"
    copy.write_bytes(original.read_bytes())
    with pytest.raises(ValueError, match="already registered as 'rally.avi'"):
        with Session(database) as session, session.begin():
            import_video(session, storage, copy)

    _write_video(original, shade=100)  # Same key, different content.
    with pytest.raises(ValueError, match="different video is already registered"):
        with Session(database) as session, session.begin():
            import_video(session, storage, original)

    with Session(database) as session:
        assert session.scalar(select(func.count()).select_from(Video)) == 1
