"""Independent frame-level detector trials. No event or scoring claims are made."""

import csv
import json
import os
import time
from dataclasses import asdict
from datetime import UTC, datetime
from importlib.metadata import version
from math import isfinite
from pathlib import Path
from uuid import uuid4

import cv2
import yaml

from volleyvision.calibration import CourtCalibration
from volleyvision.provenance import require_model_permission, require_video_permission
from volleyvision.video import inspect_video, iter_frames


def run_baseline(
    *,
    video: Path,
    permission: Path,
    model_manifest: Path,
    task: str,
    output: Path,
    config_path: Path,
    start_sec: float,
    end_sec: float,
    calibration_path: Path | None = None,
    track: bool = False,
    device: str = "cpu",
) -> dict:
    if track and task != "players":
        raise ValueError("ByteTrack is available only for the player trial.")
    if not all(isfinite(t) for t in (start_sec, end_sec)) or not 0 <= start_sec < end_sec:
        raise ValueError("Rally bounds must satisfy 0 <= start < end.")
    if end_sec - start_sec > 30:
        raise ValueError("Feasibility trials are limited to 30 seconds; select a short rally.")
    source_record = require_video_permission(video, permission)
    model_record, checkpoint = require_model_permission(model_manifest, task)
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        raise ValueError("Baseline configuration must be a YAML mapping.")
    confidence = float(config["confidence"])
    image_size = int(config["image_size"])
    if not isfinite(confidence) or not 0 < confidence < 1 or image_size < 32:
        raise ValueError("Confidence must be in (0, 1), and image_size at least 32.")
    info = inspect_video(video)
    if end_sec > info.duration_sec + 1 / info.fps:
        raise ValueError("Rally end exceeds the reported video duration.")
    calibration = CourtCalibration.load(calibration_path) if calibration_path else None
    if task == "players" and calibration is None:
        raise ValueError("Player trial requires a court calibration.")
    if calibration and calibration.source_sha256 != info.sha256:
        raise ValueError("Court calibration belongs to a different source video.")
    if calibration:
        calibration.polygon_pixels(info.width, info.height)
    if output.exists():
        raise ValueError("Use a new output directory for each run; previous results are immutable.")
    os.environ["YOLO_AUTOINSTALL"] = "false"
    os.environ["YOLO_OFFLINE"] = "true"
    try:
        import torch
        from ultralytics import YOLO
    except ImportError:
        raise ValueError(
            "Detector runtime is missing. Resolve code/weight licensing, then install the "
            "tested PyTorch/Ultralytics runtime explicitly; see docs/setup.md."
        ) from None
    if device != "cpu" and (not device.isdecimal() or not torch.cuda.is_available()):
        raise ValueError("Specify cpu or an available CUDA device index.")
    model = YOLO(str(checkpoint), task="detect")
    class_map = model_record["class_map"]
    if not set(class_map) <= set(model.names.values()):
        raise ValueError("Manifest source labels do not match checkpoint class names.")
    class_ids = [key for key, name in model.names.items() if name in class_map]
    if torch.cuda.is_available() and device != "cpu":
        torch.cuda.reset_peak_memory_stats(int(device))
    output.mkdir(parents=True)
    started = datetime.now(UTC).isoformat()
    run_id = str(uuid4())
    metadata = {
        "run_id": run_id,
        "status": "running",
        "started_at": started,
        "task": task,
        "recording_id": source_record["recording_id"],
        "split": source_record["split"],
        "video": asdict(info),
        "rally": {"start_sec": start_sec, "end_sec": end_sec, "provenance": "manual"},
        "model_id": model_record["model_id"],
        "checkpoint_sha256": model_record["sha256"],
        "class_map": class_map,
        "configuration": config,
        "device": device,
        "versions": {name: version(name) for name in ("torch", "ultralytics", "opencv-python")},
        "tracking": "ByteTrack" if track else None,
        "calibration": asdict(calibration) if calibration else None,
        "limitations": [
            "Frame predictions are not action events or confirmed points.",
            "Track IDs are anonymous and may switch.",
            "No ball motion prediction or temporal action filtering in this trial.",
            "No temporal court hysteresis in this independent baseline.",
        ],
    }
    report_path = output / "run.json"

    def save_report() -> None:
        report_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")

    save_report()
    writer = None
    processed = 0
    detection_count = 0
    started_clock = time.perf_counter()
    fields = [
        "run_id",
        "frame_index",
        "timestamp_sec",
        "timestamp_source",
        "class",
        "x1",
        "y1",
        "x2",
        "y2",
        "confidence",
        "track_id",
        "court_filter_status",
    ]
    try:
        writer = cv2.VideoWriter(
            str(output / "annotated.mp4"),
            cv2.VideoWriter_fourcc(*"mp4v"),
            info.fps,
            (info.width, info.height),
        )
        if not writer.isOpened():
            raise ValueError("MP4 writer could not open; check codec support.")
        with (
            (output / "predictions.jsonl").open("w", encoding="utf-8") as json_stream,
            (output / "predictions.csv").open("w", newline="", encoding="utf-8") as csv_stream,
            (output / "frames.jsonl").open("w", encoding="utf-8") as frame_stream,
        ):
            csv_writer = csv.DictWriter(csv_stream, fieldnames=fields)
            csv_writer.writeheader()
            for frame in iter_frames(video, start_sec, end_sec):
                arguments = {
                    "source": frame.image,
                    "conf": confidence,
                    "imgsz": image_size,
                    "device": device,
                    "verbose": False,
                    "classes": class_ids,
                }
                if track:
                    result = model.track(**arguments, tracker="bytetrack.yaml", persist=True)[0]
                else:
                    result = model.predict(**arguments)[0]
                canvas = frame.image.copy()
                if calibration:
                    polygon = calibration.polygon_pixels(info.width, info.height)
                    cv2.polylines(canvas, [polygon.astype("int32")], True, (255, 180, 0), 2)
                count = 0
                for box in result.boxes:
                    source_class = model.names[int(box.cls.item())]
                    if source_class not in class_map:
                        continue
                    bbox = [float(x) for x in box.xyxy[0].tolist()]
                    status = (
                        calibration.classify(bbox, info.width, info.height)
                        if task == "players"
                        else "not_applicable"
                    )
                    track_id = int(box.id.item()) if box.id is not None else None
                    row = dict(
                        zip(
                            fields,
                            [
                                run_id,
                                frame.index,
                                frame.timestamp_sec,
                                frame.timestamp_source,
                                class_map[source_class],
                                *bbox,
                                float(box.conf.item()),
                                track_id,
                                status,
                            ],
                            strict=True,
                        )
                    )
                    json_stream.write(json.dumps(row) + "\n")
                    csv_writer.writerow(row)
                    count += 1
                    if status != "excluded":
                        x1, y1, x2, y2 = map(round, bbox)
                        color = (0, 220, 255) if status == "uncertain" else (0, 210, 0)
                        cv2.rectangle(canvas, (x1, y1), (x2, y2), color, 2)
                        if task == "ball":
                            cv2.circle(canvas, ((x1 + x2) // 2, (y1 + y2) // 2), 4, color, -1)
                        label = f"{row['class']} {row['confidence']:.2f}"
                        if track_id is not None:
                            label += f" ID {track_id}"
                        if status == "uncertain":
                            label += " uncertain"
                        cv2.putText(
                            canvas,
                            label,
                            (x1, max(15, y1 - 4)),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.45,
                            color,
                            1,
                        )
                frame_stream.write(
                    json.dumps(
                        {
                            "frame_index": frame.index,
                            "timestamp_sec": frame.timestamp_sec,
                            "timestamp_source": frame.timestamp_source,
                            "detection_count": count,
                        }
                    )
                    + "\n"
                )
                cv2.putText(
                    canvas,
                    f"Frame {frame.index} | source {frame.timestamp_sec:.3f}s",
                    (8, 20),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (255, 255, 255),
                    1,
                )
                writer.write(canvas)
                detection_count += count
                processed += 1
        if processed == 0:
            raise ValueError("No frames decoded inside the requested rally interval.")
        metadata.update(
            status="complete", frames_processed=processed, detection_count=detection_count
        )
    except Exception as exc:
        metadata.update(status="failed", error_type=type(exc).__name__)
        raise
    finally:
        if writer is not None:
            writer.release()
        elapsed = time.perf_counter() - started_clock
        metadata.update(
            ended_at=datetime.now(UTC).isoformat(),
            elapsed_sec=elapsed,
            processing_fps=processed / elapsed if elapsed else None,
        )
        metadata["peak_cuda_memory_bytes"] = (
            torch.cuda.max_memory_allocated(int(device))
            if device != "cpu" and torch.cuda.is_available()
            else None
        )
        metadata["annotated_video_timing"] = "nominal FPS; source timestamps in frames.jsonl"
        save_report()
    return metadata
