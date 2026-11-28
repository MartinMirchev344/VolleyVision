"""Small local commands for the feasibility milestone."""

import argparse
import json
import sys
from pathlib import Path
from uuid import UUID


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="volleyanalytics", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("doctor", help="Report installed versions and run a CUDA tensor check")
    commands.add_parser("db-check", help="Check PostgreSQL using DATABASE_URL")
    inspect = commands.add_parser("inspect", help="Inspect a local video's metadata and SHA256")
    inspect.add_argument("--input", type=Path, required=True)
    register = commands.add_parser(
        "import-video",
        help="Register a video inside VOLLEYANALYTICS_STORAGE_ROOT in PostgreSQL (no copy)",
    )
    register.add_argument("--file", type=Path, required=True)
    stats = commands.add_parser("stats", help="Print a match box score computed in PostgreSQL")
    stats.add_argument("--match-id", type=UUID, required=True)
    stats.add_argument(
        "--reviewed-only", action="store_true", help="Count only confirmed/corrected records"
    )
    stats.add_argument("--format", choices=("text", "json"), default="text")
    calibrate = commands.add_parser("calibrate", help="Click court and playable-region polygons")
    calibrate.add_argument("--input", type=Path, required=True)
    calibrate.add_argument("--permission-record", type=Path, required=True)
    calibrate.add_argument("--output", type=Path, required=True)
    calibrate.add_argument("--author", required=True)
    calibrate.add_argument("--frame-index", type=int, default=0)
    calibrate.add_argument(
        "--mode", choices=("strict_court", "court_plus_free_zone"), default="court_plus_free_zone"
    )
    calibrate.add_argument("--margin-fraction", type=float, default=0.01)
    baseline = commands.add_parser(
        "baseline", help="Run a licensed local checkpoint on a short rally"
    )
    baseline.add_argument("--input", type=Path, required=True)
    baseline.add_argument("--permission-record", type=Path, required=True)
    baseline.add_argument("--model-manifest", type=Path, required=True)
    baseline.add_argument("--task", choices=("players", "ball", "actions"), required=True)
    baseline.add_argument("--output", type=Path, required=True)
    baseline.add_argument("--config", type=Path, default=Path("configs/baseline.yaml"))
    baseline.add_argument("--calibration", type=Path)
    baseline.add_argument("--start-sec", type=float, required=True)
    baseline.add_argument("--end-sec", type=float, required=True)
    baseline.add_argument(
        "--track",
        action="store_true",
        help="Track players (tracker set in --config, default ByteTrack)",
    )
    baseline.add_argument("--device", default="cpu", help="cpu or CUDA device index (e.g. 0)")
    export = commands.add_parser(
        "label-export", help="Export frames pre-filled with player boxes for Label Studio"
    )
    export.add_argument("--input", type=Path, required=True)
    export.add_argument("--permission-record", type=Path, required=True)
    export.add_argument("--model-manifest", type=Path, required=True)
    export.add_argument("--output", type=Path, required=True, help="New batch folder")
    export.add_argument("--count", type=int, default=150)
    export.add_argument(
        "--test-from-sec", type=float, required=True, help="Frames from here on are test frames"
    )
    export.add_argument("--image-size", type=int, default=1280)
    export.add_argument("--min-confidence", type=float, default=0.3)
    export.add_argument("--calibration", type=Path, help="Drop pre-filled boxes off the court")
    export.add_argument("--calibration-from-sec", type=float, help="Calibration valid from")
    export.add_argument("--calibration-until-sec", type=float, help="Calibration valid until")
    export.add_argument("--only-split", choices=("train", "test"), help="Export one split")
    export.add_argument(
        "--side", choices=("near", "far"), help="Pre-fill only players on this half of the court"
    )
    export.add_argument("--net-tolerance-m", type=float, default=0.5)
    export.add_argument("--seed", type=int, default=1)
    export.add_argument("--device", default="cpu", help="cpu or CUDA device index (e.g. 0)")
    evaluate = commands.add_parser(
        "evaluate", help="Score a player or ball model against labelled frames"
    )
    evaluate.add_argument(
        "--labels", type=Path, required=True, help="Label Studio export.json or YOLO dataset folder"
    )
    evaluate.add_argument("--model-manifest", type=Path, required=True)
    evaluate.add_argument("--task", choices=("players", "ball"), required=True)
    evaluate.add_argument("--output", type=Path, required=True, help="New JSON report path")
    evaluate.add_argument("--split", default="test", help="Dataset split for a YOLO folder")
    evaluate.add_argument("--image-size", type=int, default=1280)
    evaluate.add_argument("--threshold", type=float, default=0.3)
    evaluate.add_argument("--ball-distance", type=float, default=10.0, help="Pixels")
    evaluate.add_argument("--calibration", type=Path, help="Also score with the court filter")
    evaluate.add_argument(
        "--side", choices=("near", "far"), help="Score only players on this half of the court"
    )
    evaluate.add_argument("--net-tolerance-m", type=float, default=0.5)
    evaluate.add_argument("--device", default="cpu", help="cpu or CUDA device index (e.g. 0)")
    train = commands.add_parser(
        "train", help="Fine-tune a licensed detector on a YOLO dataset (writes a model manifest)"
    )
    train.add_argument("--dataset", type=Path, required=True, help="YOLO dataset folder")
    train.add_argument("--task", choices=("players", "ball"), required=True)
    train.add_argument("--base-model-manifest", type=Path, required=True)
    train.add_argument("--output", type=Path, required=True, help="New model folder")
    train.add_argument("--model-id", required=True, help="Name recorded in the new manifest")
    train.add_argument("--image-size", type=int, default=640)
    train.add_argument("--epochs", type=int, default=40)
    train.add_argument("--patience", type=int, default=10)
    train.add_argument("--batch", type=int, default=16)
    train.add_argument("--workers", type=int, default=4)
    train.add_argument("--seed", type=int, default=1)
    train.add_argument("--dataset-source-sha256", help="Hash of the downloaded dataset zip")
    train.add_argument("--device", default="0", help="cpu or CUDA device index (e.g. 0)")
    studio = commands.add_parser(
        "label-studio", help="Start the local Label Studio (localhost only, no telemetry)"
    )
    studio.add_argument("--port", type=int, default=8080)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "doctor":
            from volleyanalytics.diagnostics import environment_report

            result = environment_report()
        elif args.command == "db-check":
            from volleyanalytics.db import check_database

            result = check_database()
        elif args.command == "inspect":
            from volleyanalytics.video import inspect_video

            result = inspect_video(args.input).to_dict()
        elif args.command == "import-video":
            from volleyanalytics.db import session_scope
            from volleyanalytics.ingest import import_video
            from volleyanalytics.storage import LocalStorage

            storage = LocalStorage.from_environment()
            with session_scope() as session:
                result = import_video(session, storage, args.file)
        elif args.command == "stats":
            from volleyanalytics.db import session_scope
            from volleyanalytics.stats import match_report, render_text

            with session_scope() as session:
                result = match_report(session, args.match_id, args.reviewed_only)
            if args.format == "text":
                print(render_text(result))
                return 0
        elif args.command == "evaluate":
            from volleyanalytics.evaluation import evaluate

            result = evaluate(
                labels=args.labels,
                model_manifest=args.model_manifest,
                task=args.task,
                output=args.output,
                image_size=args.image_size,
                threshold=args.threshold,
                ball_distance=args.ball_distance,
                calibration_path=args.calibration,
                side=args.side,
                net_tolerance_m=args.net_tolerance_m,
                split=args.split,
                device=args.device,
            )
        elif args.command == "train":
            from volleyanalytics.training import train_detector

            result = train_detector(
                dataset=args.dataset,
                task=args.task,
                base_manifest=args.base_model_manifest,
                output=args.output,
                model_id=args.model_id,
                image_size=args.image_size,
                epochs=args.epochs,
                patience=args.patience,
                batch=args.batch,
                workers=args.workers,
                seed=args.seed,
                device=args.device,
                dataset_source_sha256=args.dataset_source_sha256,
            )
        elif args.command == "label-studio":
            from volleyanalytics.labeling import start_label_studio

            return start_label_studio(args.port)
        elif args.command == "label-export":
            from volleyanalytics.labeling import export_batch

            result = export_batch(
                video=args.input,
                permission=args.permission_record,
                model_manifest=args.model_manifest,
                output=args.output,
                count=args.count,
                test_from_sec=args.test_from_sec,
                image_size=args.image_size,
                min_confidence=args.min_confidence,
                calibration_path=args.calibration,
                calibration_from_sec=args.calibration_from_sec,
                calibration_until_sec=args.calibration_until_sec,
                only_split=args.only_split,
                side=args.side,
                net_tolerance_m=args.net_tolerance_m,
                seed=args.seed,
                device=args.device,
            )
        elif args.command == "calibrate":
            from volleyanalytics.calibration import calibrate_interactively
            from volleyanalytics.provenance import require_video_permission

            require_video_permission(args.input, args.permission_record)
            if args.output.exists():
                raise ValueError("Calibration output exists; choose a new versioned filename.")
            calibrate_interactively(
                args.input,
                args.output,
                args.author,
                args.frame_index,
                args.mode,
                args.margin_fraction,
            )
            result = {"saved": str(args.output)}
        else:
            from volleyanalytics.baseline import run_baseline

            result = run_baseline(
                video=args.input,
                permission=args.permission_record,
                model_manifest=args.model_manifest,
                task=args.task,
                output=args.output,
                config_path=args.config,
                start_sec=args.start_sec,
                end_sec=args.end_sec,
                calibration_path=args.calibration,
                track=args.track,
                device=args.device,
            )
        print(json.dumps(result, indent=2))
        return 0
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        # Database/driver exceptions can contain connection strings and credentials.
        print(f"Operation failed ({type(exc).__name__}); check setup and inputs.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
