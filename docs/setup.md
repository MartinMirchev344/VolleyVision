# Local setup

Tested on Windows x64 with Python 3.11.17. The system's default Python 3.15 was
not used for this environment. A project-local runtime is installed under ignored
`.tools/python/`; the virtual environment is `.venv/`. No global PATH changes or
Windows database service are required.

## Python packages

For a fresh environment, select an installed Python 3.11 interpreter and run:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
.\.venv\Scripts\python.exe -m pip install --no-build-isolation --no-deps -e .
.\.venv\Scripts\python.exe -m volleyanalytics doctor
```

On this checkout the local interpreter can replace `py -3.11`:
`.\.tools\python\cpython-3.11.17-windows-x86_64-none\python.exe`.
The environment is already created; there is no need to recreate it.

Optional RTX 5070 verification uses the separately pinned CUDA 12.8 environment:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-cuda.txt
.\.venv\Scripts\python.exe -m volleyanalytics doctor
```

The GPU check allocates tensors and performs a matrix multiplication. It does not
prove detector compatibility or model quality.

The detector runtime (Ultralytics, AGPL-3.0; see `dependencies.md`) is pinned
separately. Install it after the CUDA packages so PyTorch stays the CUDA build, then
disable Ultralytics usage analytics:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-models.txt
.\.venv\Scripts\yolo.exe settings sync=False
```

The baseline adapter requires trusted local `.pt` weights; no implicit downloads.

## PostgreSQL options

Portable PostgreSQL 17.11 is installed under `.tools/postgresql/pgsql/`, with the
cluster in ignored `data/postgres/`. Local random credentials are in ignored `.env`;
do not commit or print that file. The application and test databases are
`volleyvision` and `volleyvision_test`, on **127.0.0.1:55432**, with UTC database time.
These names predate the VolleyAnalytics rename; they come from `.env` and still
work unchanged. A fresh Compose setup uses the `volleyanalytics` defaults instead.
The server is stopped after verification. Start it when needed:

```powershell
.\.tools\postgresql\pgsql\bin\pg_ctl.exe -D data/postgres -l data/postgres-server.log -o "-h 127.0.0.1 -p 55432" -w start
```

Alternatively install Docker and copy `.env.example` to `.env` on a fresh checkout,
replace the password, then run `docker compose up -d --wait postgres`. Compose binds
localhost and persists a named volume. Its image is `postgres:17.11-bookworm`; update
the tested patch deliberately. Docker execution has not been verified on this host.
Do not start Compose and the portable instance on the same port or share their data
directories. Changing environment passwords does not change an existing cluster.

Compose reads `.env` automatically; Python and Alembic intentionally read exported
variables. Load this project's simple KEY=value file without executing its contents:

```powershell
Get-Content .env | Where-Object { $_ -match '^[A-Z_]+=' } | ForEach-Object {
    $setting = $_ -split '=', 2
    [Environment]::SetEnvironmentVariable($setting[0], $setting[1], 'Process')
}
.\.venv\Scripts\python.exe -m volleyanalytics db-check
.\.venv\Scripts\alembic.exe upgrade head
.\.venv\Scripts\alembic.exe current
New-Item -ItemType Directory -Force outputs | Out-Null
.\.venv\Scripts\python.exe -m pytest -q --basetemp outputs/test-tmp
```

Only set `TEST_DATABASE_URL` to a dedicated test database: integration checks create
and remove an isolated schema there. They also check that the ORM models match the
migrations. After use stop the portable instance with:

```powershell
.\.tools\postgresql\pgsql\bin\pg_ctl.exe -D data/postgres -m fast -w stop
```

Use `docker compose stop postgres` for Compose. Keep persistent volumes/cluster data
unless deliberately retiring the database. `.env.example` contains placeholders,
not the credentials used by the local instance.

## Labelling (Label Studio)

Label Studio Community 1.23.2 (Apache-2.0) runs in its own environment so its
dependencies cannot affect the project. Install it once:

```powershell
.\.tools\python\cpython-3.11.17-windows-x86_64-none\python.exe -m venv .tools\label-studio-venv
.\.tools\label-studio-venv\Scripts\python.exe -m pip install label-studio==1.23.2
```

Export frames pre-filled with the player model's boxes. Frames are spread evenly over
the recording; `--test-from-sec` marks later frames as test frames, and `--only-split`
exports one split. A court calibration (valid between `--calibration-from-sec` and
`--calibration-until-sec`) drops pre-filled boxes off the court.
`--side near` keeps only players on the near half: the calibration's four court corners
give a perspective transform to court metres, and a footpoint counts as near up to
`--net-tolerance-m` (default 0.5 m) past the centre line. Use it to track one team when
the camera stands behind that team's end line; move the camera and add a calibration
whenever the teams switch sides.

```powershell
.\.venv\Scripts\python.exe -m volleyanalytics label-export --input <video> --permission-record <permission.json> --model-manifest data/models/upstream-players/model.json --output data/labeling/test-01 --count 150 --test-from-sec 3140 --only-split test --calibration <court.json> --calibration-from-sec 3140 --device 0
```

Start Label Studio with `.\.venv\Scripts\python.exe -m volleyanalytics label-studio`.
It listens on http://127.0.0.1:8080 only, keeps its database in `data/label-studio`,
serves frames from `data/labeling`, and has crash reporting, analytics and the update
check switched off. The account you create on first start is local.

Set up a project once per batch:

1. **Create** a project, open **Labeling Setup → Custom template → Code**, paste the
   batch's `label-config.xml` and save.
2. **Settings → Cloud Storage → Add Source Storage → Local files**, absolute path
   `<repository>\data\labeling\<batch>\images`. Add it, but do not sync it.
3. **Settings → Annotation**: turn on using predictions to pre-label tasks.
4. **Import** the batch's `tasks.json`.

Label every on-court player (head to feet, including partly hidden and far-side players,
not referees, coaches, bench or spectators) and the ball wherever it is visible. Leave a
blurred or hidden ball unmarked. When done, **Export → JSON** into the batch folder as
`export.json`.
