"""Add match statistics tables: teams, players, matches, rosters, lineups, rallies, touches."""

import sqlalchemy as sa
from alembic import op

revision = "0003_match_stats"
down_revision = "0002_videos"
branch_labels = None
depends_on = None

SIDE = "side IN ('home', 'away')"
SOURCE = "source IN ('human', 'model', 'scoreboard')"
CONFIDENCE = "confidence IS NULL OR confidence BETWEEN 0 AND 1"
REVIEW = "review_status IN ('unreviewed', 'confirmed', 'corrected', 'rejected')"
SKILL_GRADE = (
    "(skill = 'serve' AND grade IN ('ace', 'in_play', 'error'))"
    " OR (skill = 'reception' AND grade IN ('perfect', 'positive', 'ok', 'poor', 'error'))"
    " OR (skill = 'set' AND grade IN ('good', 'poor', 'error'))"
    " OR (skill = 'attack' AND grade IN ('kill', 'in_play', 'blocked', 'error'))"
    " OR (skill = 'block' AND grade IN ('point', 'touch', 'error'))"
    " OR (skill = 'dig' AND grade IN ('good', 'poor', 'error'))"
    " OR (skill = 'freeball' AND grade IN ('good', 'poor', 'error'))"
    " OR (skill = 'fault' AND grade = 'error')"
)


def _created_at() -> sa.Column:
    return sa.Column(
        "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )


def _review_status() -> sa.Column:
    return sa.Column("review_status", sa.String(16), server_default="unreviewed", nullable=False)


def upgrade() -> None:
    op.create_table(
        "teams",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        _created_at(),
        sa.PrimaryKeyConstraint("id", name="pk_teams"),
        sa.UniqueConstraint("name", name="uq_teams_name"),
    )
    op.create_table(
        "players",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("display_name", sa.String(200), nullable=False),
        _created_at(),
        sa.PrimaryKeyConstraint("id", name="pk_players"),
    )
    op.create_table(
        "matches",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("home_team_id", sa.Uuid(), nullable=False),
        sa.Column("away_team_id", sa.Uuid(), nullable=False),
        sa.Column("competition", sa.String(200), nullable=True),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("venue", sa.String(200), nullable=True),
        sa.Column("city", sa.String(200), nullable=True),
        sa.Column("spectators", sa.Integer(), nullable=True),
        sa.Column("first_referee", sa.String(200), nullable=True),
        sa.Column("second_referee", sa.String(200), nullable=True),
        _created_at(),
        sa.PrimaryKeyConstraint("id", name="pk_matches"),
        sa.ForeignKeyConstraint(
            ["home_team_id"], ["teams.id"], name="fk_matches_home_team_id_teams"
        ),
        sa.ForeignKeyConstraint(
            ["away_team_id"], ["teams.id"], name="fk_matches_away_team_id_teams"
        ),
        sa.CheckConstraint("home_team_id <> away_team_id", name="ck_matches_distinct_teams"),
        sa.CheckConstraint(
            "spectators IS NULL OR spectators >= 0", name="ck_matches_nonnegative_spectators"
        ),
    )

    op.add_column("videos", sa.Column("match_id", sa.Uuid(), nullable=True))
    op.create_foreign_key("fk_videos_match_id_matches", "videos", "matches", ["match_id"], ["id"])
    op.create_index("ix_videos_match_id", "videos", ["match_id"])

    op.create_table(
        "match_roster",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("match_id", sa.Uuid(), nullable=False),
        sa.Column("player_id", sa.Uuid(), nullable=False),
        sa.Column("side", sa.String(4), nullable=False),
        sa.Column("jersey_number", sa.Integer(), nullable=False),
        sa.Column("is_libero", sa.Boolean(), server_default=sa.false(), nullable=False),
        _created_at(),
        sa.PrimaryKeyConstraint("id", name="pk_match_roster"),
        sa.ForeignKeyConstraint(
            ["match_id"], ["matches.id"], name="fk_match_roster_match_id_matches"
        ),
        sa.ForeignKeyConstraint(
            ["player_id"], ["players.id"], name="fk_match_roster_player_id_players"
        ),
        sa.CheckConstraint(SIDE, name="ck_match_roster_valid_side"),
        sa.CheckConstraint("jersey_number BETWEEN 0 AND 99", name="ck_match_roster_valid_jersey"),
        sa.UniqueConstraint("match_id", "player_id", name="uq_match_roster_match_player"),
        sa.UniqueConstraint("match_id", "side", "jersey_number", name="uq_match_roster_jersey"),
        sa.UniqueConstraint("id", "match_id", "side", name="uq_match_roster_identity"),
    )
    op.create_table(
        "set_lineups",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("match_id", sa.Uuid(), nullable=False),
        sa.Column("roster_id", sa.Uuid(), nullable=False),
        sa.Column("side", sa.String(4), nullable=False),
        sa.Column("set_number", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("starting_zone", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_set_lineups"),
        sa.ForeignKeyConstraint(
            ["roster_id", "match_id", "side"],
            ["match_roster.id", "match_roster.match_id", "match_roster.side"],
            name="fk_set_lineups_roster_id_match_roster",
        ),
        sa.CheckConstraint(SIDE, name="ck_set_lineups_valid_side"),
        sa.CheckConstraint("set_number BETWEEN 1 AND 5", name="ck_set_lineups_valid_set"),
        sa.CheckConstraint(
            "role IN ('starter', 'substitute', 'libero')", name="ck_set_lineups_valid_role"
        ),
        sa.CheckConstraint(
            "(role = 'starter') = (starting_zone IS NOT NULL)",
            name="ck_set_lineups_zone_for_starters",
        ),
        sa.CheckConstraint(
            "starting_zone IS NULL OR starting_zone BETWEEN 1 AND 6",
            name="ck_set_lineups_valid_zone",
        ),
        sa.UniqueConstraint("roster_id", "set_number", name="uq_set_lineups_roster_set"),
    )
    op.create_index(
        "uq_set_lineups_zone",
        "set_lineups",
        ["match_id", "set_number", "side", "starting_zone"],
        unique=True,
        postgresql_where=sa.text("starting_zone IS NOT NULL"),
    )
    op.create_table(
        "rallies",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("match_id", sa.Uuid(), nullable=False),
        sa.Column("video_id", sa.Uuid(), nullable=True),
        sa.Column("set_number", sa.Integer(), nullable=False),
        sa.Column("rally_number", sa.Integer(), nullable=False),
        sa.Column("serving_side", sa.String(4), nullable=True),
        sa.Column("winning_side", sa.String(4), nullable=True),
        sa.Column("start_sec", sa.Float(), nullable=True),
        sa.Column("end_sec", sa.Float(), nullable=True),
        sa.Column("source", sa.String(16), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        _review_status(),
        _created_at(),
        sa.PrimaryKeyConstraint("id", name="pk_rallies"),
        sa.ForeignKeyConstraint(["match_id"], ["matches.id"], name="fk_rallies_match_id_matches"),
        sa.ForeignKeyConstraint(["video_id"], ["videos.id"], name="fk_rallies_video_id_videos"),
        sa.CheckConstraint("set_number BETWEEN 1 AND 5", name="ck_rallies_valid_set"),
        sa.CheckConstraint("rally_number >= 1", name="ck_rallies_positive_rally_number"),
        sa.CheckConstraint(
            "serving_side IS NULL OR serving_side IN ('home', 'away')",
            name="ck_rallies_valid_serving_side",
        ),
        sa.CheckConstraint(
            "winning_side IS NULL OR winning_side IN ('home', 'away')",
            name="ck_rallies_valid_winning_side",
        ),
        sa.CheckConstraint(
            "start_sec IS NULL OR start_sec >= 0", name="ck_rallies_nonnegative_start"
        ),
        sa.CheckConstraint(
            "end_sec IS NULL OR start_sec IS NULL OR end_sec >= start_sec",
            name="ck_rallies_ordered_times",
        ),
        sa.CheckConstraint(SOURCE, name="ck_rallies_valid_source"),
        sa.CheckConstraint(CONFIDENCE, name="ck_rallies_valid_confidence"),
        sa.CheckConstraint(REVIEW, name="ck_rallies_valid_review_status"),
        sa.UniqueConstraint("match_id", "set_number", "rally_number", name="uq_rallies_order"),
        sa.UniqueConstraint("id", "match_id", name="uq_rallies_identity"),
    )
    op.create_table(
        "touches",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("match_id", sa.Uuid(), nullable=False),
        sa.Column("rally_id", sa.Uuid(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("side", sa.String(4), nullable=False),
        sa.Column("roster_id", sa.Uuid(), nullable=True),
        sa.Column("skill", sa.String(16), nullable=False),
        sa.Column("grade", sa.String(16), nullable=False),
        sa.Column("video_sec", sa.Float(), nullable=True),
        sa.Column("source", sa.String(16), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        _review_status(),
        _created_at(),
        sa.PrimaryKeyConstraint("id", name="pk_touches"),
        sa.ForeignKeyConstraint(
            ["rally_id", "match_id"],
            ["rallies.id", "rallies.match_id"],
            name="fk_touches_rally_id_rallies",
        ),
        sa.ForeignKeyConstraint(
            ["roster_id", "match_id", "side"],
            ["match_roster.id", "match_roster.match_id", "match_roster.side"],
            name="fk_touches_roster_id_match_roster",
        ),
        sa.CheckConstraint("sequence >= 1", name="ck_touches_positive_sequence"),
        sa.CheckConstraint(SIDE, name="ck_touches_valid_side"),
        sa.CheckConstraint(SKILL_GRADE, name="ck_touches_valid_skill_grade"),
        sa.CheckConstraint(
            "video_sec IS NULL OR video_sec >= 0", name="ck_touches_nonnegative_video_sec"
        ),
        sa.CheckConstraint(SOURCE, name="ck_touches_valid_source"),
        sa.CheckConstraint(CONFIDENCE, name="ck_touches_valid_confidence"),
        sa.CheckConstraint(REVIEW, name="ck_touches_valid_review_status"),
        sa.UniqueConstraint("rally_id", "sequence", name="uq_touches_order"),
    )
    op.create_index("ix_touches_match_id", "touches", ["match_id"])


def downgrade() -> None:
    op.drop_index("ix_touches_match_id", table_name="touches")
    op.drop_table("touches")
    op.drop_table("rallies")
    op.drop_index("uq_set_lineups_zone", table_name="set_lineups")
    op.drop_table("set_lineups")
    op.drop_table("match_roster")
    op.drop_index("ix_videos_match_id", table_name="videos")
    op.drop_constraint("fk_videos_match_id_matches", "videos", type_="foreignkey")
    op.drop_column("videos", "match_id")
    op.drop_table("matches")
    op.drop_table("players")
    op.drop_table("teams")
