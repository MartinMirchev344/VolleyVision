import json

import cv2
import numpy as np
import pytest

from volleyanalytics.evaluation import (
    average_precision,
    centre_distance,
    evaluate,
    iou,
    load_labels,
    load_yolo_split,
    match_frame,
    summarise,
)
from volleyanalytics.video import file_sha256


def test_overlap_and_distance():
    assert iou([0, 0, 10, 10], [0, 0, 10, 10]) == 1
    assert iou([0, 0, 10, 10], [5, 0, 15, 10]) == pytest.approx(50 / 150)
    assert iou([0, 0, 10, 10], [20, 20, 30, 30]) == 0
    assert centre_distance([0, 0, 10, 10], [3, 4, 13, 14]) == pytest.approx(5)


def test_matching_is_one_to_one_by_confidence():
    truth = [[0, 0, 10, 10]]
    predicted = [{"bbox": [0, 0, 10, 10], "score": 0.4}, {"bbox": [1, 0, 11, 10], "score": 0.9}]
    result = match_frame(truth, predicted, "iou", 0.5)
    # The more confident box takes the match; the duplicate is a false positive.
    assert result["flags"] == [(0.9, True), (0.4, False)] and result["missed"] == []


def test_average_precision_by_hand():
    # Recall/precision points: (0.5, 1.0), (0.5, 0.5), (1.0, 0.667) -> 0.5*1 + 0.5*0.667.
    assert average_precision([(0.9, True), (0.8, False), (0.7, True)], 2) == pytest.approx(
        0.8333, abs=1e-4
    )
    assert average_precision([], 0) is None


def test_summary_at_threshold_with_size_breakdown():
    frame = {
        "image": "a.jpg",
        "frame_index": 7,
        "boxes": [
            {"class": "player", "bbox": [0, 0, 20, 120]},
            {"class": "player", "bbox": [100, 0, 120, 80]},
            {"class": "player", "bbox": [200, 0, 210, 40]},  # small, far-court size
        ],
        "predictions": [
            {"class": "player", "bbox": [0, 0, 20, 120], "score": 0.9},
            {"class": "player", "bbox": [100, 0, 120, 80], "score": 0.8},
            {"class": "player", "bbox": [500, 0, 520, 80], "score": 0.7},  # spectator
            {"class": "player", "bbox": [200, 0, 210, 40], "score": 0.2},  # below threshold
        ],
    }
    report = summarise([frame], "player", "iou", 0.5, threshold=0.3)
    assert (report["true_positives"], report["false_positives"], report["missed"]) == (2, 1, 1)
    assert report["precision"] == pytest.approx(0.6667, abs=1e-4)
    assert report["recall"] == pytest.approx(0.6667, abs=1e-4)
    assert report["recall_by_box_height"]["under 50 px"] == {"found": 0, "total": 1, "recall": 0.0}
    assert report["frames_with_most_errors"] == [
        {"image": "a.jpg", "frame_index": 7, "false_positives": 1, "missed": 1}
    ]


def test_label_studio_export_uses_latest_finished_annotation(tmp_path):
    rect = {
        "type": "rectanglelabels",
        "original_width": 200,
        "original_height": 100,
        "value": {"x": 10, "y": 20, "width": 50, "height": 50, "rectanglelabels": ["player"]},
    }
    ball = {**rect, "value": {**rect["value"], "rectanglelabels": ["ball"]}}
    export = [
        {
            "data": {
                "image": "/data/local-files/?d=b/images/f1.jpg",
                "frame_index": 1,
                "split": "test",
            },
            "annotations": [
                {"id": 1, "updated_at": "2026-01-01", "result": [rect, rect]},
                {"id": 2, "updated_at": "2026-01-02", "result": [rect, ball]},
                {"id": 3, "updated_at": "2026-01-03", "result": [], "was_cancelled": True},
            ],
        },
        {"data": {"image": "/data/local-files/?d=b/images/f2.jpg"}, "annotations": []},
    ]
    path = tmp_path / "export.json"
    path.write_text(json.dumps(export))
    frames = load_labels(path)
    assert len(frames) == 1  # The unlabelled task is skipped, not counted as empty.
    assert frames[0]["image"] == "f1.jpg"
    assert [b["class"] for b in frames[0]["boxes"]] == ["player", "volleyball"]
    assert frames[0]["boxes"][0]["bbox"] == pytest.approx([20, 20, 120, 70])


def _yolo_dataset(root, names):
    (root / "test" / "images").mkdir(parents=True)
    (root / "test" / "labels").mkdir(parents=True)
    (root / "data.yaml").write_text(f"names: {names}\n")
    cv2.imwrite(str(root / "test" / "images" / "a.jpg"), np.zeros((100, 200, 3), np.uint8))
    (root / "test" / "labels" / "a.txt").write_text("1 0.5 0.5 0.2 0.4\n0 0.1 0.1 0.02 0.04\n")


def test_yolo_dataset_labels_are_converted_to_pixels(tmp_path):
    _yolo_dataset(tmp_path, ["ball", "player"])
    frames, images = load_yolo_split(tmp_path, "test")
    assert images == tmp_path / "test" / "images"
    boxes = frames[0]["boxes"]
    assert [b["class"] for b in boxes] == ["player", "volleyball"]
    assert boxes[0]["bbox"] == pytest.approx([80, 30, 120, 70])
    with pytest.raises(ValueError, match="valid/images"):
        load_yolo_split(tmp_path, "valid")


def test_evaluate_writes_a_report(tmp_path):
    ultralytics = pytest.importorskip("ultralytics")
    dataset = tmp_path / "dataset"
    _yolo_dataset(dataset, ["ball", "player"])
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
    report_path = tmp_path / "reports" / "players.json"
    report = evaluate(
        labels=dataset, model_manifest=manifest, task="players", output=report_path, image_size=160
    )
    assert report["frames"] == 1 and report["splits"] == ["test"]
    assert report["detector"]["labelled_objects"] == 1
    assert json.loads(report_path.read_text())["model_id"] == "random"
    with pytest.raises(ValueError, match="new report"):
        evaluate(labels=dataset, model_manifest=manifest, task="players", output=report_path)


def test_one_side_needs_a_court_calibration(tmp_path):
    with pytest.raises(ValueError, match="court calibration"):
        evaluate(
            labels=tmp_path,
            model_manifest=tmp_path / "model.json",
            task="players",
            output=tmp_path / "report.json",
            side="near",
        )
