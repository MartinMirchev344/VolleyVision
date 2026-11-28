import json
import xml.etree.ElementTree as ET

import cv2
import numpy as np
import pytest

from volleyanalytics.labeling import (
    LABEL_CONFIG,
    LABELS,
    export_batch,
    label_studio_env,
    rectangle_result,
    start_label_studio,
    stratified_indices,
)
from volleyanalytics.video import file_sha256


def test_sampling_is_spread_reproducible_and_in_range():
    picks = stratified_indices(1000, 10, seed=3)
    assert picks == stratified_indices(1000, 10, seed=3)
    assert picks != stratified_indices(1000, 10, seed=4)
    # One pick from each tenth of the video, so the sample covers the whole match.
    assert [p // 100 for p in picks] == list(range(10))
    assert len(set(stratified_indices(50, 50, seed=1))) == 50
    with pytest.raises(ValueError):
        stratified_indices(10, 11, seed=1)


def test_rectangle_is_in_percent_and_clipped():
    result = rectangle_result([-10, 90, 140, 200], width=200, height=100, label="player", score=0.5)
    value = result["value"]
    assert (value["x"], value["y"], value["width"], value["height"]) == (0, 90, 70, 10)
    assert value["rectanglelabels"] == ["player"]
    with pytest.raises(ValueError, match="no area"):
        rectangle_result([210, 0, 220, 10], width=200, height=100, label="player", score=0.5)


def test_label_studio_runs_without_telemetry_and_serves_local_frames(tmp_path):
    env = label_studio_env({"PATH": "x", "LABEL_STUDIO_SENTRY_DSN": "https://example"}, tmp_path)
    assert env["PATH"] == "x"
    assert env["LABEL_STUDIO_SENTRY_DSN"] == "" and env["LABEL_STUDIO_FRONTEND_SENTRY_DSN"] == ""
    assert env["LABEL_STUDIO_COLLECT_ANALYTICS"] == "false"
    assert env["LABEL_STUDIO_LATEST_VERSION_CHECK"] == "false"
    assert env["LABEL_STUDIO_LOCAL_FILES_DOCUMENT_ROOT"] == str((tmp_path / "labeling").resolve())
    assert env["LABEL_STUDIO_BASE_DATA_DIR"] == str((tmp_path / "label-studio").resolve())


def test_missing_label_studio_is_a_clear_error(tmp_path):
    with pytest.raises(ValueError, match="not installed"):
        start_label_studio(executable=tmp_path / "missing.exe")


def test_label_config_lists_the_labels():
    root = ET.fromstring(LABEL_CONFIG)
    assert [label.get("value") for label in root.iter("Label")] == list(LABELS)


def test_export_writes_exact_frames_split_by_time(tmp_path):
    ultralytics = pytest.importorskip("ultralytics")
    video = tmp_path / "match.avi"
    writer = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*"MJPG"), 10, (320, 240))
    for index in range(40):  # Each frame's brightness encodes its index.
        writer.write(np.full((240, 320, 3), index * 6, dtype=np.uint8))
    writer.release()
    permission = tmp_path / "permission.json"
    permission.write_text(
        json.dumps(
            {
                "recording_id": "match",
                "sha256": file_sha256(video),
                "owner": "test",
                "permission_evidence": "fixture",
                "allowed_uses": "tests",
                "split": "development",
                "processing_permitted": True,
            }
        )
    )
    model = ultralytics.YOLO("yolo26n.yaml")  # random weights; nothing is downloaded
    model.save(str(tmp_path / "random.pt"))
    manifest = tmp_path / "model.json"
    manifest.write_text(
        json.dumps(
            {
                "model_id": "random",
                "task": "players",
                "source_url": "fixture",
                "code_license_url": "fixture",
                "weights_license_url": "fixture",
                "reviewed_by": "test",
                "checkpoint": "random.pt",
                "sha256": file_sha256(tmp_path / "random.pt"),
                "usage_decision": "permitted",
                "inference_permitted": True,
                "class_map": {model.names[0]: "player"},
            }
        )
    )
    output = tmp_path / "batch-01"
    summary = export_batch(
        video=video,
        permission=permission,
        model_manifest=manifest,
        output=output,
        count=8,
        test_from_sec=3.0,
        image_size=320,
        seed=2,
    )
    tasks = json.loads((output / "tasks.json").read_text(encoding="utf-8"))
    assert summary["frames"] == len(tasks) == 8
    assert summary["train_frames"] == 6 and summary["test_frames"] == 2  # 3.0 s = frame 30
    for task in tasks:
        data = task["data"]
        assert data["split"] == ("test" if data["frame_index"] >= 30 else "train")
        name = data["image"].split("/")[-1]
        assert data["image"] == f"/data/local-files/?d=batch-01/images/{name}"
        image = cv2.imread(str(output / "images" / name))
        # The saved image is the frame its index claims (MJPG adds small noise).
        assert abs(float(image.mean()) - data["frame_index"] * 6) < 3
    test_only = export_batch(
        video=video,
        permission=permission,
        model_manifest=manifest,
        output=tmp_path / "test-01",
        count=8,
        test_from_sec=3.0,
        image_size=320,
        seed=2,
        only_split="test",
    )
    test_tasks = json.loads((tmp_path / "test-01" / "tasks.json").read_text(encoding="utf-8"))
    assert test_only["frames"] == test_only["test_frames"] == 2 and test_only["train_frames"] == 0
    assert {t["data"]["frame_index"] for t in test_tasks} == {
        t["data"]["frame_index"] for t in tasks if t["data"]["split"] == "test"
    }
    assert len(list((tmp_path / "test-01" / "images").iterdir())) == 2
    with pytest.raises(ValueError, match="court calibration"):
        export_batch(
            video=video,
            permission=permission,
            model_manifest=manifest,
            output=tmp_path / "near-01",
            count=8,
            test_from_sec=3.0,
            side="near",
        )
    with pytest.raises(ValueError, match="new batch"):
        export_batch(
            video=video,
            permission=permission,
            model_manifest=manifest,
            output=output,
            count=8,
            test_from_sec=3.0,
        )
