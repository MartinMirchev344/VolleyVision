import cv2
import numpy as np
import pytest

from volleyvision.video import inspect_video, iter_frames, reference_frame


@pytest.fixture
def synthetic_video(tmp_path):
    path = tmp_path / "synthetic.avi"
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), 10, (160, 120))
    assert writer.isOpened(), "Test environment needs the MJPG codec"
    for index in range(10):
        writer.write(np.full((120, 160, 3), index * 20, dtype=np.uint8))
    writer.release()
    return path


def test_metadata_and_source_frame_indices(synthetic_video):
    info = inspect_video(synthetic_video)
    assert (info.width, info.height, info.frame_count, info.fps) == (160, 120, 10, 10)
    assert info.duration_sec == 1
    assert len(info.sha256) == 64
    frames = list(iter_frames(synthetic_video, 0.2, 0.5))
    assert [frame.index for frame in frames] == [2, 3, 4]
    assert [frame.timestamp_sec for frame in frames] == pytest.approx([0.2, 0.3, 0.4])
    assert reference_frame(synthetic_video, 3).mean() == pytest.approx(60, abs=2)


def test_missing_corrupt_and_out_of_range_video(tmp_path, synthetic_video):
    with pytest.raises(ValueError, match="does not exist"):
        inspect_video(tmp_path / "missing.mp4")
    corrupt = tmp_path / "broken.mp4"
    corrupt.write_bytes(b"this is not video")
    with pytest.raises(ValueError, match="could not be opened"):
        inspect_video(corrupt)
    with pytest.raises(ValueError, match="outside"):
        reference_frame(synthetic_video, 50)
    with pytest.raises(ValueError, match="bounds"):
        list(iter_frames(synthetic_video, 0.5, 0.2))


def test_unavailable_video_clock_uses_declared_fallback(monkeypatch):
    class Capture:
        def __init__(self):
            self.index = -1
            self.released = False

        def get(self, key):
            return 10 if key == cv2.CAP_PROP_FPS else 0

        def read(self):
            self.index += 1
            return (self.index < 3, np.zeros((4, 4, 3), dtype=np.uint8))

        def release(self):
            self.released = True

    capture = Capture()
    monkeypatch.setattr("volleyvision.video.open_video", lambda path: capture)
    frames = list(iter_frames(None, 0, 0.3))
    assert [frame.timestamp_sec for frame in frames] == [0, 0.1, 0.2]
    assert frames[1].timestamp_source == "nominal_fps"
    assert capture.released
