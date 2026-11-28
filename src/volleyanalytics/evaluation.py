"""Measure a detector against frames labelled in Label Studio.

Players are matched one-to-one by box overlap (IoU >= 0.5). The ball is matched by
centre distance, because a few pixels of offset on a tiny box ruins IoU even when the
centre is usable. Matching is greedy by confidence, so precision/recall at any
threshold and AP50 come from one pass. Reports also break player recall down by box
height, which separates far-court players from near ones.
"""

import json
import os
from datetime import UTC, datetime
from pathlib import Path

import cv2

from volleyanalytics.calibration import CourtCalibration
from volleyanalytics.provenance import require_model_permission

# Label Studio label -> canonical class used in model manifests.
CANONICAL = {"player": "player", "ball": "volleyball"}
HEIGHT_BUCKETS = ((0, 50, "under 50 px"), (50, 100, "50-100 px"), (100, 10_000, "over 100 px"))


def load_labels(export_path: Path) -> list[dict]:
    """Ground truth per frame from a Label Studio JSON export (latest finished annotation)."""
    tasks = json.loads(export_path.read_text(encoding="utf-8"))
    if not isinstance(tasks, list):
        raise ValueError("Expected a Label Studio JSON export (a list of tasks).")
    frames = []
    for task in tasks:
        annotations = [a for a in task.get("annotations", []) if not a.get("was_cancelled")]
        if not annotations:
            continue  # Not labelled yet; it must not count as a frame with no players.
        latest = max(annotations, key=lambda a: (a.get("updated_at") or "", a.get("id") or 0))
        boxes = []
        for item in latest.get("result", []):
            if item.get("type") != "rectanglelabels":
                continue
            value, width, height = item["value"], item["original_width"], item["original_height"]
            (label,) = value["rectanglelabels"]
            x1 = value["x"] * width / 100
            y1 = value["y"] * height / 100
            boxes.append(
                {
                    "class": CANONICAL[label],
                    "bbox": [
                        x1,
                        y1,
                        x1 + value["width"] * width / 100,
                        y1 + value["height"] * height / 100,
                    ],
                }
            )
        data = task["data"]
        frames.append(
            {
                "image": data["image"].rsplit("/", 1)[-1],
                "frame_index": data.get("frame_index"),
                "timestamp_sec": data.get("timestamp_sec"),
                "split": data.get("split"),
                "boxes": boxes,
            }
        )
    return frames


YOLO_NAMES = {
    "player": "player",
    "players": "player",
    "ball": "volleyball",
    "volleyball": "volleyball",
}
IMAGE_SUFFIXES = (".jpg", ".jpeg", ".png", ".bmp")


def load_yolo_split(dataset: Path, split: str) -> tuple[list[dict], Path]:
    """Ground truth from a YOLO-format dataset (e.g. a VolleyVision Roboflow export).

    Expects `data.yaml` with class names and `<split>/images` + `<split>/labels`, where
    each label line is `class cx cy w h` normalised to the image size.
    """
    import yaml

    config = yaml.safe_load((dataset / "data.yaml").read_text(encoding="utf-8"))
    names = config["names"]
    names = (
        dict(enumerate(names)) if isinstance(names, list) else {int(k): v for k, v in names.items()}
    )
    images = dataset / split / "images"
    labels = dataset / split / "labels"
    if not images.is_dir():
        raise ValueError(f"No {split}/images folder in {dataset}.")
    frames = []
    for image_path in sorted(p for p in images.iterdir() if p.suffix.lower() in IMAGE_SUFFIXES):
        size = cv2.imread(str(image_path), cv2.IMREAD_UNCHANGED)
        if size is None:
            continue
        height, width = size.shape[:2]
        boxes = []
        label_file = labels / f"{image_path.stem}.txt"
        if label_file.is_file():
            for line in label_file.read_text(encoding="utf-8").splitlines():
                parts = line.split()
                if len(parts) != 5:
                    continue  # Segmentation polygons and blank lines are not boxes.
                cls, cx, cy, w, h = int(parts[0]), *map(float, parts[1:])
                canonical = YOLO_NAMES.get(str(names[cls]).lower())
                if canonical is None:
                    continue
                boxes.append(
                    {
                        "class": canonical,
                        "bbox": [
                            (cx - w / 2) * width,
                            (cy - h / 2) * height,
                            (cx + w / 2) * width,
                            (cy + h / 2) * height,
                        ],
                    }
                )
        frames.append(
            {
                "image": image_path.name,
                "frame_index": None,
                "timestamp_sec": None,
                "split": split,
                "boxes": boxes,
            }
        )
    return frames, images


def iou(a: list[float], b: list[float]) -> float:
    w = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    h = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = w * h
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


def centre_distance(a: list[float], b: list[float]) -> float:
    return (((a[0] + a[2]) - (b[0] + b[2])) ** 2 + ((a[1] + a[3]) - (b[1] + b[3])) ** 2) ** 0.5 / 2


def match_frame(truth: list[list[float]], predicted: list[dict], mode: str, limit: float) -> dict:
    """Greedy one-to-one matching in descending confidence. Returns flags and misses."""
    order = sorted(range(len(predicted)), key=lambda i: -predicted[i]["score"])
    used: set[int] = set()
    flags = []
    for i in order:
        box = predicted[i]["bbox"]
        best, best_value = None, None
        for j, gt in enumerate(truth):
            if j in used:
                continue
            if mode == "iou":
                value = iou(box, gt)
                good = value >= limit and (best_value is None or value > best_value)
            else:
                value = centre_distance(box, gt)
                good = value <= limit and (best_value is None or value < best_value)
            if good:
                best, best_value = j, value
        if best is not None:
            used.add(best)
        flags.append((predicted[i]["score"], best is not None))
    return {"flags": flags, "missed": [j for j in range(len(truth)) if j not in used]}


def average_precision(flags: list[tuple[float, bool]], positives: int) -> float | None:
    """Area under the precision-recall curve (all-point interpolation, as in VOC/COCO AP50)."""
    if positives == 0:
        return None
    flags = sorted(flags, key=lambda f: -f[0])
    tp = fp = 0
    points = []
    for _, hit in flags:
        tp, fp = tp + hit, fp + (not hit)
        points.append((tp / positives, tp / (tp + fp)))
    ap, previous_recall = 0.0, 0.0
    for k, (recall, _) in enumerate(points):
        precision = max(p for _, p in points[k:])
        ap += (recall - previous_recall) * precision
        previous_recall = recall
    return round(ap, 4)


def summarise(frames: list[dict], cls: str, mode: str, limit: float, threshold: float) -> dict:
    flags, positives, tp, fp, fn = [], 0, 0, 0, 0
    buckets = {name: [0, 0] for _, _, name in HEIGHT_BUCKETS}  # [found, total]
    worst = []
    for frame in frames:
        truth = [b["bbox"] for b in frame["boxes"] if b["class"] == cls]
        predicted = [p for p in frame["predictions"] if p["class"] == cls]
        result = match_frame(truth, predicted, mode, limit)
        flags += result["flags"]
        positives += len(truth)
        # Greedy matching by confidence: the matches above a threshold are the same.
        kept = [(s, hit) for s, hit in result["flags"] if s >= threshold]
        hits = sum(hit for _, hit in kept)
        tp, fp = tp + hits, fp + len(kept) - hits
        strong = match_frame(truth, [p for p in predicted if p["score"] >= threshold], mode, limit)
        fn += len(strong["missed"])
        for j, box in enumerate(truth):
            height = box[3] - box[1]
            name = next(n for low, high, n in HEIGHT_BUCKETS if low <= height < high)
            buckets[name][1] += 1
            buckets[name][0] += j not in strong["missed"]
        errors = len(kept) - hits + len(strong["missed"])
        if errors:
            worst.append(
                {
                    "image": frame["image"],
                    "frame_index": frame["frame_index"],
                    "false_positives": len(kept) - hits,
                    "missed": len(strong["missed"]),
                }
            )
    worst.sort(key=lambda w: -(w["false_positives"] + w["missed"]))
    return {
        "class": cls,
        "matching": f"IoU >= {limit}" if mode == "iou" else f"centre within {limit} px",
        "threshold": threshold,
        "labelled_objects": positives,
        "true_positives": tp,
        "false_positives": fp,
        "missed": fn,
        "precision": round(tp / (tp + fp), 4) if tp + fp else None,
        "recall": round(tp / positives, 4) if positives else None,
        "ap50": average_precision(flags, positives) if mode == "iou" else None,
        "recall_by_box_height": {
            name: {"found": found, "total": total, "recall": round(found / total, 4)}
            for name, (found, total) in buckets.items()
            if total
        }
        if cls == "player"
        else None,
        "frames_with_most_errors": worst[:10],
    }


def evaluate(
    *,
    labels: Path,
    model_manifest: Path,
    task: str,
    output: Path,
    image_size: int = 1280,
    threshold: float = 0.3,
    ball_distance: float = 10.0,
    calibration_path: Path | None = None,
    side: str | None = None,
    net_tolerance_m: float = 0.5,
    split: str = "test",
    device: str = "cpu",
) -> dict:
    """Run a model on labelled frames and score it. Writes a JSON report to `output`.

    `labels` is either a Label Studio JSON export (images are read from the `images`
    folder beside it) or a YOLO-format dataset folder, scored on `split`.
    """
    if task not in ("players", "ball"):
        raise ValueError("Evaluation supports the players and ball models.")
    if not 0 < threshold < 1 or ball_distance <= 0:
        raise ValueError("threshold must be in (0, 1) and ball_distance positive.")
    if side not in (None, "near", "far"):
        raise ValueError("side must be near or far.")
    if side and calibration_path is None:
        raise ValueError("Scoring one side of the court needs a court calibration.")
    if output.exists():
        raise ValueError("Use a new report path; earlier reports stay unchanged.")
    model_record, checkpoint = require_model_permission(model_manifest, task)
    if labels.is_dir():
        frames, images = load_yolo_split(labels, split)
    else:
        frames, images = load_labels(labels), labels.parent / "images"
    if not frames:
        raise ValueError("No labelled frames in the export yet.")
    calibration = CourtCalibration.load(calibration_path) if calibration_path else None

    os.environ["YOLO_AUTOINSTALL"] = "false"
    os.environ["YOLO_OFFLINE"] = "true"
    try:
        from ultralytics import YOLO
    except ImportError:
        raise ValueError("Detector runtime is missing; install requirements-models.txt.") from None
    model = YOLO(str(checkpoint), task="detect")
    class_map = model_record["class_map"]
    class_ids = [key for key, name in model.names.items() if name in class_map]
    for frame in frames:
        image = cv2.imread(str(images / frame["image"]))
        if image is None:
            raise ValueError(f"Labelled image not found: {images / frame['image']}")
        height, width = image.shape[:2]
        result = model.predict(
            image, conf=0.05, imgsz=image_size, device=device, classes=class_ids, verbose=False
        )[0]
        frame["predictions"] = []
        for box in result.boxes:
            bbox = [float(v) for v in box.xyxy[0].tolist()]
            on_court = (
                calibration.classify(bbox, width, height) != "excluded" if calibration else True
            )
            if on_court and side:
                on_court = calibration.court_side(bbox, width, height, net_tolerance_m) == side
            frame["predictions"].append(
                {
                    "class": class_map[model.names[int(box.cls.item())]],
                    "bbox": bbox,
                    "score": float(box.conf.item()),
                    "on_court": on_court,
                }
            )

    cls = "player" if task == "players" else "volleyball"
    mode, limit = ("iou", 0.5) if task == "players" else ("distance", ball_distance)
    report = {
        "created_at": datetime.now(UTC).isoformat(),
        "labels": str(labels),
        "model_id": model_record["model_id"],
        "checkpoint_sha256": model_record["sha256"],
        "image_size": image_size,
        "frames": len(frames),
        "splits": sorted({f["split"] for f in frames if f["split"]}),
        "detector": summarise(frames, cls, mode, limit, threshold),
    }
    if calibration:
        filtered = [
            {**f, "predictions": [p for p in f["predictions"] if p["on_court"]]} for f in frames
        ]
        report["detector_with_court_filter"] = summarise(filtered, cls, mode, limit, threshold)
        report["detector_with_court_filter"]["side"] = side
        report["detector_with_court_filter"]["net_tolerance_m"] = net_tolerance_m if side else None
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report
