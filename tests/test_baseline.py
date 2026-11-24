"""Runtime integration for the baseline runner, using a randomly initialised model.

Random weights verify the pipeline wiring (gates, ByteTrack call, exports, GPU
bookkeeping), not detection quality. Skipped when the detector runtime is absent.
"""

import json

import cv2
import numpy as np
import pytest

ultralytics = pytest.importorskip("ultralytics")
torch = pytest.importorskip("torch")

from volleyanalytics.baseline import run_baseline  # noqa: E402
from volleyanalytics.video import file_sha256  # noqa: E402

DEVICES = [
    "cpu",
    pytest.param(
        "0",
        marks=pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA unavailable"),
    ),
]


def _write_inputs(tmp_path):
    video = tmp_path / "synthetic.avi"
    writer = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*"MJPG"), 10, (320, 240))
    assert writer.isOpened(), "Test environment needs the MJPG codec"
    for index in range(5):
        frame = np.full((240, 320, 3), 90, dtype=np.uint8)
        cv2.rectangle(frame, (60 + 5 * index, 100), (90 + 5 * index, 200), (30, 30, 200), -1)
        writer.write(frame)
    writer.release()
    sha = file_sha256(video)
    permission = tmp_path / "permission.json"
    permission.write_text(
        json.dumps(
            {
                "recording_id": "synthetic",
                "sha256": sha,
                "owner": "test",
                "permission_evidence": "generated fixture",
                "allowed_uses": "tests",
                "split": "development",
                "processing_permitted": True,
            }
        )
    )
    model = ultralytics.YOLO("yolo26n.yaml")  # architecture only; nothing is downloaded
    checkpoint = tmp_path / "random.pt"
    model.save(str(checkpoint))
    manifest = tmp_path / "model.json"
    manifest.write_text(
        json.dumps(
            {
                "model_id": "random-init yolo26n",
                "task": "players",
                "source_url": "test fixture",
                "code_license_url": "https://www.ultralytics.com/license",
                "weights_license_url": "random initialisation",
                "reviewed_by": "test",
                "checkpoint": checkpoint.name,
                "sha256": file_sha256(checkpoint),
                "usage_decision": "permitted",
                "inference_permitted": True,
                "class_map": {model.names[0]: "player"},
            }
        )
    )
    court = tmp_path / "court.json"
    court.write_text(
        json.dumps(
            {
                "court_polygon": [[0.1, 0.3], [0.9, 0.3], [0.9, 0.9], [0.1, 0.9]],
                "playable_polygon": [[0.05, 0.2], [0.95, 0.2], [0.95, 0.95], [0.05, 0.95]],
                "source_width": 320,
                "source_height": 240,
                "source_frame_index": 0,
                "source_sha256": sha,
                "author": "test",
                "created_at": "2026-11-19T00:00:00+00:00",
            }
        )
    )
    config = tmp_path / "config.yaml"
    config.write_text("confidence: 0.25\nimage_size: 320\n")
    return video, permission, manifest, court, config


@pytest.mark.parametrize("device", DEVICES)
def test_tracked_player_baseline_runs_and_exports(tmp_path, device):
    video, permission, manifest, court, config = _write_inputs(tmp_path)
    output = tmp_path / "run"
    result = run_baseline(
        video=video,
        permission=permission,
        model_manifest=manifest,
        task="players",
        output=output,
        config_path=config,
        start_sec=0,
        end_sec=0.45,
        calibration_path=court,
        track=True,
        device=device,
    )
    assert result["status"] == "complete"
    assert result["frames_processed"] == 5
    assert result["tracking"] == {"tracker": "bytetrack.yaml", "settings": None}
    assert (result["peak_cuda_memory_bytes"] is None) == (device == "cpu")
    frames = (output / "frames.jsonl").read_text(encoding="utf-8").splitlines()
    assert [json.loads(line)["frame_index"] for line in frames] == [0, 1, 2, 3, 4]
    assert {p.name for p in output.iterdir()} == {
        "annotated.mp4",
        "frames.jsonl",
        "predictions.csv",
        "predictions.jsonl",
        "run.json",
    }
    saved = json.loads((output / "run.json").read_text(encoding="utf-8"))
    assert saved["status"] == "complete"
    assert saved["versions"]["ultralytics"] == ultralytics.__version__
