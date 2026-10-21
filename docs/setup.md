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
.\.venv\Scripts\python.exe -m volleyvision doctor
```

On this checkout the local interpreter can replace `py -3.11`:
`.\.tools\python\cpython-3.11.17-windows-x86_64-none\python.exe`.
The environment is already created; there is no need to recreate it.

Optional RTX 5070 verification uses the separately pinned CUDA 12.8 environment:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-cuda.txt
.\.venv\Scripts\python.exe -m volleyvision doctor
```

The GPU check allocates tensors and performs a matrix multiplication. It does not
prove detector compatibility or model quality. Ultralytics and all checkpoints are
still excluded: first resolve code and weight terms in `DATASETS.md`, choose/test
the exact runtime/checkpoint, then pin them in a separate model environment record.
The baseline adapter requires trusted local `.pt` weights; no implicit downloads.

## PostgreSQL options

Portable PostgreSQL 17.11 is installed under `.tools/postgresql/pgsql/`, with the
cluster in ignored `data/postgres/`. Local random credentials are in ignored `.env`;
do not commit or print that file. The application and test databases are
`volleyvision` and `volleyvision_test`, on **127.0.0.1:55432**, with UTC database time.
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
.\.venv\Scripts\python.exe -m volleyvision db-check
.\.venv\Scripts\alembic.exe upgrade head
.\.venv\Scripts\alembic.exe current
New-Item -ItemType Directory -Force outputs | Out-Null
.\.venv\Scripts\python.exe -m pytest -q --basetemp outputs/test-tmp
```

Only set `TEST_DATABASE_URL` to a dedicated test database: integration checks create
and remove an isolated schema there. The bootstrap migration has no feature tables.
After use stop the portable instance with:

```powershell
.\.tools\postgresql\pgsql\bin\pg_ctl.exe -D data/postgres -m fast -w stop
```

Use `docker compose stop postgres` for Compose. Keep persistent volumes/cluster data
unless deliberately retiring the database. `.env.example` contains placeholders,
not the credentials used by the local instance.
