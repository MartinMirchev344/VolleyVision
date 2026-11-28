import json

import cv2
import numpy as np
import pytest

from volleyanalytics.provenance import require_model_permission
from volleyanalytics.training import resolve_dataset, train_detector
from volleyanalytics.video import file_sha256


def _dataset(root, names="['volleyball']", images=6):
    for split in ("train", "valid"):
        (root / split / "images").mkdir(parents=True)
        (root / split / "labels").mkdir(parents=True)
        for i in range(images):
            image = np.full((64, 64, 3), 40, np.uint8)
            cv2.circle(image, (20 + 4 * i, 30), 5, (0, 220, 255), -1)
            cv2.imwrite(str(root / split / "images" / f"{i}.jpg"), image)
            (root / split / "labels" / f"{i}.txt").write_text(
                f"0 {(20 + 4 * i) / 64:.4f} {30 / 64:.4f} 0.16 0.16\n"
            )
    (root / "data.yaml").write_text(
        f"names: {names}\nroboflow:\n  license: CC BY 4.0\n  url: https://example/1\n  version: 1\n"
    )


def test_dataset_classes_must_mean_the_task(tmp_path):
    _dataset(tmp_path / "ball")
    path, info = resolve_dataset(tmp_path / "ball", "ball", tmp_path)
    assert info["license"] == "CC BY 4.0" and info["roboflow_version"] == 1
    assert "valid/images" in path.read_text()
    _dataset(tmp_path / "mixed", names="['volleyball', 'player']")
    with pytest.raises(ValueError, match="do not mean 'volleyball'"):
        resolve_dataset(tmp_path / "mixed", "ball", tmp_path)


def test_training_writes_a_usable_manifest(tmp_path):
    ultralytics = pytest.importorskip("ultralytics")
    _dataset(tmp_path / "ball")
    base = ultralytics.YOLO("yolo26n.yaml")  # random weights; nothing is downloaded
    base.save(str(tmp_path / "base.pt"))
    base_manifest = tmp_path / "base.json"
    base_manifest.write_text(
        json.dumps(
            {
                "model_id": "random base",
                "task": "players",
                "source_url": "fixture",
                "code_license_url": "fixture",
                "weights_license_url": "fixture",
                "reviewed_by": "test",
                "checkpoint": "base.pt",
                "sha256": file_sha256(tmp_path / "base.pt"),
                "usage_decision": "permitted",
                "inference_permitted": True,
                "class_map": {base.names[0]: "player"},
            }
        )
    )
    output = tmp_path / "ball-model"
    manifest = train_detector(
        dataset=tmp_path / "ball",
        task="ball",
        base_manifest=base_manifest,
        output=output,
        model_id="test ball model",
        image_size=64,
        epochs=1,
        batch=2,
        workers=0,
        device="cpu",
        dataset_source_sha256="abc",
    )
    record, checkpoint = require_model_permission(output / "model.json", "ball")
    assert record["volleyball_specific"] is True and record["class_map"] == {
        "volleyball": "volleyball"
    }
    assert checkpoint == (output / "best.pt").resolve()
    assert manifest["training"]["base_model_id"] == "random base"
    assert manifest["training"]["dataset_source_sha256"] == "abc"
    assert manifest["training"]["epochs_run"] == 1
    with pytest.raises(ValueError, match="never overwritten"):
        train_detector(
            dataset=tmp_path / "ball",
            task="ball",
            base_manifest=base_manifest,
            output=output,
            model_id="again",
        )
