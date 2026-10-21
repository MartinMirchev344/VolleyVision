"""Small local commands for the feasibility milestone."""

import argparse
import json
import sys
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="volleyvision", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("doctor", help="Report installed versions and run a CUDA tensor check")
    commands.add_parser("db-check", help="Check PostgreSQL using DATABASE_URL")
    inspect = commands.add_parser("inspect", help="Inspect a local video's metadata and SHA256")
    inspect.add_argument("--input", type=Path, required=True)
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
    baseline.add_argument("--track", action="store_true", help="Use ByteTrack for the player trial")
    baseline.add_argument("--device", default="cpu", help="cpu or CUDA device index (e.g. 0)")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "doctor":
            from volleyvision.diagnostics import environment_report

            result = environment_report()
        elif args.command == "db-check":
            from volleyvision.db import check_database

            result = check_database()
        elif args.command == "inspect":
            from volleyvision.video import inspect_video

            result = inspect_video(args.input).to_dict()
        elif args.command == "calibrate":
            from volleyvision.calibration import calibrate_interactively
            from volleyvision.provenance import require_video_permission

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
            from volleyvision.baseline import run_baseline

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
