"""Video access that preserves source indices and reports timestamp provenance."""

from collections.abc import Iterator
from dataclasses import asdict, dataclass
from hashlib import sha256
from math import isfinite
from pathlib import Path

import cv2
import numpy as np


def file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


@dataclass(frozen=True)
class VideoInfo:
    filename: str
    sha256: str
    size_bytes: int
    width: int
    height: int
    fps: float
    frame_count: int
    duration_sec: float
    duration_source: str = "reported_frame_count / nominal_fps"

    def to_dict(self) -> dict:
        return asdict(self)


def open_video(path: Path) -> cv2.VideoCapture:
    if not path.is_file():
        raise ValueError(f"Video file does not exist: {path}")
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        capture.release()
        raise ValueError("Video could not be opened; check its format and codec.")
    return capture


def inspect_video(path: Path) -> VideoInfo:
    capture = open_video(path)
    try:
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = float(capture.get(cv2.CAP_PROP_FPS))
        count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        if width <= 0 or height <= 0 or not isfinite(fps) or fps <= 0 or count <= 0:
            raise ValueError("Video has missing/invalid dimensions, FPS, or frame count.")
        ok, _ = capture.read()
        if not ok:
            raise ValueError("Video metadata exists but the first frame cannot be decoded.")
    finally:
        capture.release()
    return VideoInfo(
        path.name, file_sha256(path), path.stat().st_size, width, height, fps, count, count / fps
    )


def reference_frame(path: Path, frame_index: int) -> np.ndarray:
    if frame_index < 0:
        raise ValueError("Reference frame must be nonnegative.")
    capture = open_video(path)
    try:
        # Decode sequentially: backend seeking can land on a different keyframe.
        for _ in range(frame_index + 1):
            ok, frame = capture.read()
            if not ok:
                raise ValueError("Reference frame lies outside the decodable video.")
        return frame
    finally:
        capture.release()


@dataclass(frozen=True)
class Frame:
    index: int
    timestamp_sec: float
    timestamp_source: str
    image: np.ndarray


def iter_frames(path: Path, start_sec: float, end_sec: float) -> Iterator[Frame]:
    if not all(isfinite(x) for x in (start_sec, end_sec)) or not 0 <= start_sec < end_sec:
        raise ValueError("Rally bounds must be finite and satisfy 0 <= start < end.")
    capture = open_video(path)
    try:
        fps = float(capture.get(cv2.CAP_PROP_FPS))
        if not isfinite(fps) or fps <= 0:
            raise ValueError("Video must report a positive nominal FPS.")
        index, previous = 0, -1.0
        # Choose one clock for the entire run. Do not switch back from the fallback.
        fallback = False
        while True:
            ok, image = capture.read()
            if not ok:
                break
            reported = float(capture.get(cv2.CAP_PROP_POS_MSEC)) / 1000
            if not isfinite(reported) or reported < 0 or (index > 0 and reported <= previous):
                fallback = True
            timestamp = index / fps if fallback else reported
            if timestamp <= previous and index > 0:
                raise ValueError("Video clock is inconsistent; remux to constant FPS before use.")
            previous = timestamp
            if timestamp >= end_sec:
                break
            if timestamp >= start_sec:
                yield Frame(index, timestamp, "nominal_fps" if fallback else "video_pts", image)
            index += 1
    finally:
        capture.release()
