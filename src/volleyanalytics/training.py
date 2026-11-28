"""Fine-tune a licensed detector on a YOLO-format dataset and record full provenance.

The result is a new model folder with the trained checkpoint and a manifest that the
rest of the project (baseline, labelling, evaluation) accepts like any other model. The
manifest records the base model, the dataset and its source hash, the settings and the
validation metrics, so a reported number can always be traced to what produced it.
"""

import json
import os
import shutil
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path

import yaml

from volleyanalytics.evaluation import YOLO_NAMES
from volleyanalytics.provenance import load_json, require_model_permission
from volleyanalytics.video import file_sha256

CANONICAL_FOR_TASK = {"players": "player", "ball": "volleyball"}


def resolve_dataset(dataset: Path, task: str, output: Path) -> tuple[Path, dict]:
    """Write a dataset YAML with absolute paths; every class must mean the task's object."""
    source = yaml.safe_load((dataset / "data.yaml").read_text(encoding="utf-8"))
    names = source["names"]
    names = (
        dict(enumerate(names)) if isinstance(names, list) else {int(k): v for k, v in names.items()}
    )
    wanted = CANONICAL_FOR_TASK[task]
    unknown = [n for n in names.values() if YOLO_NAMES.get(str(n).lower()) != wanted]
    if unknown:
        raise ValueError(f"Dataset classes {unknown} do not mean '{wanted}'; map or remove them.")
    splits = {}
    for key, folder in (("train", "train"), ("val", "valid"), ("test", "test")):
        if (dataset / folder / "images").is_dir():
            splits[key] = f"{folder}/images"
    if "train" not in splits or "val" not in splits:
        raise ValueError("Dataset needs train/images and valid/images folders.")
    resolved = {"path": str(dataset.resolve()), **splits, "names": names}
    path = output / "dataset.yaml"
    path.write_text(yaml.safe_dump(resolved, sort_keys=False), encoding="utf-8")
    roboflow = source.get("roboflow", {})
    return path, {
        "folder": str(dataset),
        "classes": names,
        "roboflow_url": roboflow.get("url"),
        "roboflow_version": roboflow.get("version"),
        "license": roboflow.get("license"),
    }


def train_detector(
    *,
    dataset: Path,
    task: str,
    base_manifest: Path,
    output: Path,
    model_id: str,
    image_size: int = 640,
    epochs: int = 40,
    patience: int = 10,
    batch: int = 16,
    workers: int = 4,
    seed: int = 1,
    device: str = "0",
    dataset_source_sha256: str | None = None,
) -> dict:
    if task not in CANONICAL_FOR_TASK:
        raise ValueError("Training supports the players and ball tasks.")
    if image_size < 32 or epochs < 1 or patience < 1 or batch < 1:
        raise ValueError("image_size, epochs, patience and batch must be positive.")
    if output.exists():
        raise ValueError("Use a new model folder; trained models are never overwritten.")
    base_record, base_checkpoint = require_model_permission(
        base_manifest, load_json(base_manifest).get("task", "")
    )
    os.environ["YOLO_AUTOINSTALL"] = "false"
    os.environ["YOLO_OFFLINE"] = "true"
    try:
        from ultralytics import YOLO
    except ImportError:
        raise ValueError("Detector runtime is missing; install requirements-models.txt.") from None

    output.mkdir(parents=True)
    dataset_yaml, dataset_info = resolve_dataset(dataset, task, output)
    started = datetime.now(UTC).isoformat()
    model = YOLO(str(base_checkpoint), task="detect")
    try:
        model.train(
            data=str(dataset_yaml),
            imgsz=image_size,
            epochs=epochs,
            patience=patience,
            batch=batch,
            workers=workers,
            seed=seed,
            device=device,
            project=str(output.resolve()),
            name="train",
            exist_ok=False,
            plots=False,
            verbose=False,
        )
    except Exception:
        # Keep the folder (it holds the run's logs) but make the failure obvious.
        (output / "FAILED").write_text(f"Training failed; started {started}\n", encoding="utf-8")
        raise
    weights = output / "train" / "weights" / "best.pt"
    if not weights.is_file():
        raise ValueError("Training finished without a best.pt checkpoint.")
    checkpoint = output / "best.pt"
    shutil.copyfile(weights, checkpoint)
    metrics = {}
    results_csv = output / "train" / "results.csv"
    if results_csv.is_file():
        lines = [line.split(",") for line in results_csv.read_text().splitlines() if line.strip()]
        header = [h.strip() for h in lines[0]]
        rows = [dict(zip(header, (v.strip() for v in row), strict=False)) for row in lines[1:]]
        key = "metrics/mAP50(B)"
        best = max(rows, key=lambda r: float(r.get(key, 0) or 0)) if rows else {}
        metrics = {
            "epochs_run": len(rows),
            "best_epoch": int(float(best.get("epoch", 0))) if best else None,
            "validation": {k: float(v) for k, v in best.items() if k.startswith("metrics/")},
        }
    canonical = CANONICAL_FOR_TASK[task]
    manifest = {
        "model_id": model_id,
        "task": task,
        "source_url": f"trained locally from {base_record['model_id']}",
        "code_license_url": base_record["code_license_url"],
        "weights_license_url": (
            f"{base_record['weights_license_url']}; trained on {dataset_info['license']} data "
            "(author permission for the VolleyVision datasets)"
        ),
        "reviewed_by": base_record["reviewed_by"],
        "checkpoint": checkpoint.name,
        "sha256": file_sha256(checkpoint),
        "usage_decision": "permitted",
        "inference_permitted": True,
        "class_map": {str(name): canonical for name in dataset_info["classes"].values()},
        **({"volleyball_specific": True} if task == "ball" else {}),
        "training": {
            "started_at": started,
            "finished_at": datetime.now(UTC).isoformat(),
            "base_model_id": base_record["model_id"],
            "base_sha256": base_record["sha256"],
            "dataset": dataset_info,
            "dataset_source_sha256": dataset_source_sha256,
            "settings": {
                "image_size": image_size,
                "epochs": epochs,
                "patience": patience,
                "batch": batch,
                "seed": seed,
                "device": device,
            },
            "versions": {name: version(name) for name in ("torch", "ultralytics")},
            **metrics,
        },
    }
    (output / "model.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest
