"""Register source videos that already sit inside the storage root."""

from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from volleyanalytics.models import Video
from volleyanalytics.storage import LocalStorage
from volleyanalytics.video import inspect_video


def _summary(video: Video, already_registered: bool) -> dict:
    return {
        "video_id": str(video.id),
        "already_registered": already_registered,
        "storage_key": video.storage_key,
        "sha256": video.sha256,
        "size_bytes": video.size_bytes,
        "width": video.width,
        "height": video.height,
        "fps": video.fps,
        "frame_count": video.frame_count,
        "duration_sec": video.duration_sec,
        "duration_source": video.duration_source,
    }


def import_video(session: Session, storage: LocalStorage, file: Path) -> dict:
    """Register a video in place. Re-importing identical content returns the existing row.

    The caller owns the transaction, so a failed import leaves no partial record.
    """
    key = storage.key_for(file)  # Fail fast before hashing a large file outside the root.
    info = inspect_video(storage.path(key))
    existing = session.scalars(select(Video).where(Video.sha256 == info.sha256)).one_or_none()
    if existing is not None:
        if existing.storage_key != key:
            raise ValueError(
                f"Identical video content is already registered as '{existing.storage_key}'."
            )
        return _summary(existing, already_registered=True)
    if session.scalars(select(Video).where(Video.storage_key == key)).one_or_none():
        raise ValueError(
            f"A different video is already registered at '{key}'; the file has changed since "
            "import. Give the new recording its own filename."
        )
    video = Video(
        original_filename=info.filename,
        storage_key=key,
        sha256=info.sha256,
        size_bytes=info.size_bytes,
        width=info.width,
        height=info.height,
        fps=info.fps,
        frame_count=info.frame_count,
        duration_sec=info.duration_sec,
        duration_source=info.duration_source,
    )
    session.add(video)
    session.flush()  # Assign the ID and surface constraint violations inside the transaction.
    return _summary(video, already_registered=False)
