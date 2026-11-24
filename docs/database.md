# PostgreSQL and artifact storage

Use PostgreSQL with synchronous SQLAlchemy 2.x, psycopg 3 and Alembic. ORM models live
in `src/volleyanalytics/models.py`; each table arrives through its own migration.
Database credentials come from environment variables. No SQLite fallback is used to
stand in for PostgreSQL tests.

## Implemented tables

| Revision | Table | Contents and constraints |
|---|---|---|
| `0002_videos` | videos | UUID PK; original filename; unique storage key and SHA256; positive byte size, width/height, FPS, frame count and duration; duration provenance; timezone-aware creation time; optional match (added in `0003`) |
| `0003_match_stats` | teams, players | Unique team names; players are roster/profile records, never tracker IDs |
| | matches | Home/away teams (must differ), competition, start time, venue, city, spectators, two referees |
| | match_roster | Player per match with `side` (home/away), jersey 0–99 (unique per side), libero flag |
| | set_lineups | Per set: starter with zone 1–6 (unique per side), substitute or libero |
| | rallies | Set 1–5, rally number (unique per set), serving/winning side (null = unknown), video start/end seconds, source, confidence, review status |
| | touches | Ordered contacts per rally: side, player (null = unattributed), skill, grade, video second, source, confidence, review status |

Composite foreign keys guarantee that a touch's rally and player belong to the same match,
and that the player's side matches the touch's side. Allowed grades per skill:

| Skill | Grades |
|---|---|
| serve | ace, in_play, error |
| reception | perfect, positive, ok, poor, error |
| set, dig, freeball | good, poor, error |
| attack | kill, in_play, blocked, error |
| block | point, touch, error |
| fault (net, foot, rotation…) | error |

`error` always means the touch lost the rally; attack `blocked` means stuffed for a point.

## Statistics

No totals are stored. `src/volleyanalytics/stats.py` computes the box score in SQL from
rallies and touches, so a correction changes every derived number consistently.

- **Sources and review.** Every rally and touch records its source (`scoreboard`,
  `model`, `human`), an optional confidence and a review status. Rejected records never
  count. By default unreviewed records count and the report states how many there are
  ("AI ESTIMATE"). `--reviewed-only` counts only confirmed or corrected records.
- **Per player:** sets (starting zone or `*`), points (kills + aces + block points),
  BP (points scored while their team served), W-L (points minus touches graded `error`
  or `blocked`), serve tot/err/ace, reception tot/err/positive%/perfect%, attack
  tot/err/blocked/kills/kill%, block points. Official DataVolley sheets may compute W-L
  slightly differently.
- **Team totals** include unattributed touches.
- **Points won per set** credits each rally to the winner's last ace/kill/block point,
  else to a block if the loser was blocked, else to the loser's last error, else
  `unclassified`.
- **Sets:** score from rally winners, partials at the first rally where either team
  reaches 8, 16 and 21, and duration from the first rally start to the last rally end.

## Next feature migrations (Weeks 2–3)

| Entity | Proposed contents and constraints |
|---|---|
| court_calibrations | UUID PK; video FK; normalized court/playable polygons and tolerance, source frame and dimensions, mode/version/author; unique video+version; immutable versions |
| processing_runs | UUID PK; video and calibration references; model IDs/hashes, configuration snapshot, status, UTC start/end, hardware/performance and error details |
| player_tracks | UUID PK; run FK; anonymous integer track ID; first/last frame, eligibility; unique run+track_id; optional human roster mapping later |
| player_observations | track FK, original frame/time, bbox, confidence and eligibility status; indexed track+frame |

Use normalized relations and UUID durable IDs, run-scoped track integers, named
constraints, bbox/time/confidence checks, and explicit deletion policy. JSONB is
appropriate for immutable configurations and polygon coordinate arrays, not a
substitute for all entity relations. Validate geometry in application code as well.

Later feature migrations introduce ball observations, separate action frame
predictions and aggregated action events, scoring review history, and artifacts. Add run/frame/time/event-status indexes when
the corresponding queries exist. Make run persistence transactional and failures
visible; reruns receive new IDs and do not overwrite reviews.

Predictions and reviews remain independent. Count confirmed accepted scoring
decisions using a current-review view or versioned decisions, preserving earlier
decisions for audit and preventing correction duplicates. Do not maintain mutable
point counters independently of the reviewed records.

## Filesystem boundary

Raw/annotated videos live in ignored local folders by default. Store a storage key,
content hash, size and metadata in PostgreSQL; no raw MP4 bytea or frame-image blobs.
`VOLLEYANALYTICS_STORAGE_ROOT` (default `./data/matches`) is the source-video root.
`import-video` registers a file **in place** inside that root, without copying large
match recordings. Its storage key is the POSIX path relative to the root. Re-importing
identical content returns the existing row. A changed file under an already registered
key, or identical content under a second key, is refused. The other commands still take
explicit local input/output paths.

`src/volleyanalytics/storage.py` defines a minimal `StorageBackend` (existence, read,
size) and a `LocalStorage` implementation. Keys are validated as relative, with no
empty, `.` or `..` parts, and must resolve inside the root. Object storage can
implement the same boundary later; do not add S3 or MinIO now. Write and delete
operations are added with output artifacts. Keep source artifacts immutable, and
register output artifacts only after closing the file and computing its checksum.

Database deletion must not silently orphan or destroy video files. Initially reject
deleting referenced records until an explicit retention/deletion workflow exists.
Define the later review/roster retention policy before cascading these entities.

## Time, privacy, and tests

Record creation uses UTC timezone-aware timestamps. Events and observations use
original video indices/relative times. Raw PostgreSQL data, secrets, and private
footage stay out of Git. Public output requires appropriate publication permission,
especially where faces/minors are visible. Keep retention/deletion evidence private.

Integration tests require `TEST_DATABASE_URL` pointing to a disposable test database;
they use an isolated temporary schema to check upgrade/downgrade, repeat upgrade,
and persistence after reconnect. A restart check is a separate infrastructure smoke
test. Feature foreign keys, duplicate observations, review corrections and artifact
deletion will be tested when those migrations/features arrive.
