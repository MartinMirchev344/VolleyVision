from volleyanalytics.cli import main

# Guarded so that worker processes (spawned on Windows during training) do not rerun the CLI.
if __name__ == "__main__":
    raise SystemExit(main())
