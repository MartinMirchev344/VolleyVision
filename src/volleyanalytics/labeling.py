"""Export match frames for human labelling in Label Studio, pre-filled with model boxes.

People correct model boxes instead of drawing every box from scratch. Frames are spread
evenly across the recording and split by time, so test frames come from a different part
of the match than training frames (adjacent frames would make test scores misleading).
"""

import json
import os
import random
from datetime import UTC, datetime
from math import isfinite
from pathlib import Path

import cv2

from volleyanalytics.calibration import CourtCalibration
from volleyanalytics.provenance import require_model_permission, require_video_permission
from volleyanalytics.video import inspect_video, open_video

LABELS = ("player", "ball")
LABEL_CONFIG = """<View>
  <Image name="image" value="$image" zoom="true" zoomControl="true"/>
  <RectangleLabels name="label" toName="image" strokeWidth="2">
    <Label value="player" background="#0e7a84"/>
    <Label value="ball" background="#f2b632"/>
  </RectangleLabels>
</View>
"""


LABEL_STUDIO = Path(".tools/label-studio-venv/Scripts/label-studio.exe")


def label_studio_env(base: dict[str, str], data_root: Path) -> dict[str, str]:
    """Environment for a local-only Label Studio with frames served from data/labeling.

    Empty Sentry addresses switch off crash reports to Label Studio's servers (they also
    crash with sentry-sdk 3); analytics and the PyPI update check are off too. PowerShell
    cannot set empty variables, which is why this goes through Python.
    """
    env = dict(base)
    env.update(
        LABEL_STUDIO_SENTRY_DSN="",
        LABEL_STUDIO_FRONTEND_SENTRY_DSN="",
        LABEL_STUDIO_COLLECT_ANALYTICS="false",
        LABEL_STUDIO_LATEST_VERSION_CHECK="false",
        LABEL_STUDIO_LOCAL_FILES_SERVING_ENABLED="true",
        LABEL_STUDIO_LOCAL_FILES_DOCUMENT_ROOT=str((data_root / "labeling").resolve()),
        LABEL_STUDIO_BASE_DATA_DIR=str((data_root / "label-studio").resolve()),
        PYTHONUTF8="1",
    )
    return env


def start_label_studio(port: int = 8080, executable: Path = LABEL_STUDIO) -> int:
    """Run Label Studio on 127.0.0.1 until stopped with Ctrl+C."""
    import subprocess

    if not executable.is_file():
        raise ValueError(f"Label Studio is not installed at {executable}; see docs/setup.md.")
    data_root = Path("data")
    (data_root / "labeling").mkdir(parents=True, exist_ok=True)
    (data_root / "label-studio").mkdir(parents=True, exist_ok=True)
    print(f"Label Studio: http://127.0.0.1:{port} (Ctrl+C to stop)", flush=True)
    command = [str(executable), "start", "--no-browser", "--internal-host", "127.0.0.1"]
    try:
        return subprocess.call(
            [*command, "--port", str(port)], env=label_studio_env(dict(os.environ), data_root)
        )
    except KeyboardInterrupt:
        return 0


def stratified_indices(frame_count: int, count: int, seed: int) -> list[int]:
    """One random frame from each of `count` equal slices of the video (reproducible)."""
    if frame_count <= 0 or not 0 < count <= frame_count:
        raise ValueError("Frame count must be positive and the sample size within it.")
    rng = random.Random(seed)
    edges = [round(i * frame_count / count) for i in range(count + 1)]
    return [rng.randrange(edges[i], edges[i + 1]) for i in range(count)]


def rectangle_result(bbox: list[float], width: int, height: int, label: str, score: float) -> dict:
    """A Label Studio rectangle in percent coordinates, clipped to the image."""
    x1, y1, x2, y2 = (max(0.0, v) for v in bbox)
    x2, y2 = min(x2, width), min(y2, height)
    if x2 <= x1 or y2 <= y1:
        raise ValueError("Box has no area inside the image.")
    return {
        "from_name": "label",
        "to_name": "image",
        "type": "rectanglelabels",
        "original_width": width,
        "original_height": height,
        "image_rotation": 0,
        "score": round(score, 4),
        "value": {
            "x": 100 * x1 / width,
            "y": 100 * y1 / height,
            "width": 100 * (x2 - x1) / width,
            "height": 100 * (y2 - y1) / height,
            "rotation": 0,
            "rectanglelabels": [label],
        },
    }


def export_batch(
    *,
    video: Path,
    permission: Path,
    model_manifest: Path,
    output: Path,
    count: int,
    test_from_sec: float,
    image_size: int = 1280,
    min_confidence: float = 0.3,
    calibration_path: Path | None = None,
    calibration_from_sec: float | None = None,
    calibration_until_sec: float | None = None,
    only_split: str | None = None,
    seed: int = 1,
    device: str = "cpu",
) -> dict:
    source = require_video_permission(video, permission)
    model_record, checkpoint = require_model_permission(model_manifest, "players")
    if not isfinite(test_from_sec) or test_from_sec < 0:
        raise ValueError("test_from_sec must be a nonnegative number of seconds.")
    if not 0 < min_confidence < 1 or image_size < 32:
        raise ValueError("min_confidence must be in (0, 1) and image_size at least 32.")
    if only_split not in (None, "train", "test"):
        raise ValueError("only_split must be train or test.")
    if output.exists():
        raise ValueError("Use a new batch directory; earlier batches stay unchanged.")
    info = inspect_video(video)
    calibration = CourtCalibration.load(calibration_path) if calibration_path else None
    if calibration and calibration.source_sha256 != info.sha256:
        raise ValueError("Court calibration belongs to a different source video.")
    indices = set(stratified_indices(info.frame_count, count, seed))

    os.environ["YOLO_AUTOINSTALL"] = "false"
    os.environ["YOLO_OFFLINE"] = "true"
    try:
        from ultralytics import YOLO
    except ImportError:
        raise ValueError("Detector runtime is missing; install requirements-models.txt.") from None
    model = YOLO(str(checkpoint), task="detect")
    class_map = model_record["class_map"]
    class_ids = [key for key, name in model.names.items() if name in class_map]

    images = output / "images"
    images.mkdir(parents=True)
    tasks = []
    capture = open_video(video)
    try:
        for index in range(max(indices) + 1):
            # grab() decodes without converting, so skipping is cheap and indices stay exact.
            if not capture.grab():
                break
            if index not in indices:
                continue
            seconds = index / info.fps
            split = "test" if seconds >= test_from_sec else "train"
            if only_split and split != only_split:
                continue
            ok, frame = capture.retrieve()
            if not ok:
                continue
            name = f"{source['recording_id']}_f{index:07d}.jpg"
            cv2.imwrite(str(images / name), frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
            result = model.predict(
                frame,
                conf=min_confidence,
                imgsz=image_size,
                device=device,
                classes=class_ids,
                verbose=False,
            )[0]
            boxes = []
            # A calibration only fits the camera position it was drawn for.
            use_court = (
                calibration is not None
                and (calibration_from_sec is None or seconds >= calibration_from_sec)
                and (calibration_until_sec is None or seconds < calibration_until_sec)
            )
            for box in result.boxes:
                bbox = [float(v) for v in box.xyxy[0].tolist()]
                if use_court and calibration.classify(bbox, info.width, info.height) == "excluded":
                    continue
                boxes.append(
                    rectangle_result(bbox, info.width, info.height, "player", float(box.conf))
                )
            tasks.append(
                {
                    "data": {
                        "image": f"/data/local-files/?d={output.name}/images/{name}",
                        "recording_id": source["recording_id"],
                        "frame_index": index,
                        "timestamp_sec": round(seconds, 3),
                        "split": split,
                    },
                    "predictions": [{"model_version": model_record["model_id"], "result": boxes}],
                }
            )
    finally:
        capture.release()

    (output / "tasks.json").write_text(json.dumps(tasks, indent=1) + "\n", encoding="utf-8")
    (output / "label-config.xml").write_text(LABEL_CONFIG, encoding="utf-8")
    summary = {
        "created_at": datetime.now(UTC).isoformat(),
        "recording_id": source["recording_id"],
        "video_sha256": info.sha256,
        "model_id": model_record["model_id"],
        "checkpoint_sha256": model_record["sha256"],
        "settings": {
            "count": count,
            "seed": seed,
            "image_size": image_size,
            "min_confidence": min_confidence,
            "test_from_sec": test_from_sec,
            "calibration": str(calibration_path) if calibration_path else None,
            "calibration_from_sec": calibration_from_sec,
            "calibration_until_sec": calibration_until_sec,
            "only_split": only_split,
        },
        "frames": len(tasks),
        "train_frames": sum(t["data"]["split"] == "train" for t in tasks),
        "test_frames": sum(t["data"]["split"] == "test" for t in tasks),
        "prefilled_boxes": sum(len(t["predictions"][0]["result"]) for t in tasks),
    }
    (output / "batch.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary
