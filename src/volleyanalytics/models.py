"""Feature tables, introduced one milestone at a time through Alembic migrations.

Statistics are never stored as totals. Rallies and graded touches are stored once, and
every report number is computed from them in SQL (see `stats.py`), so a correction can
never leave a stale or double-counted total behind.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
    false,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from volleyanalytics.db import Base

SIDE_CHECK = "side IN ('home', 'away')"
SOURCE_CHECK = "source IN ('human', 'model', 'scoreboard')"
CONFIDENCE_CHECK = "confidence IS NULL OR confidence BETWEEN 0 AND 1"
REVIEW_CHECK = "review_status IN ('unreviewed', 'confirmed', 'corrected', 'rejected')"
# Allowed grades per skill. 'error' always means the touch lost the rally; an attack
# 'blocked' means it was stuffed for a point. DataVolley equivalents: ace/kill/point = #.
SKILL_GRADE_CHECK = (
    "(skill = 'serve' AND grade IN ('ace', 'in_play', 'error'))"
    " OR (skill = 'reception' AND grade IN ('perfect', 'positive', 'ok', 'poor', 'error'))"
    " OR (skill = 'set' AND grade IN ('good', 'poor', 'error'))"
    " OR (skill = 'attack' AND grade IN ('kill', 'in_play', 'blocked', 'error'))"
    " OR (skill = 'block' AND grade IN ('point', 'touch', 'error'))"
    " OR (skill = 'dig' AND grade IN ('good', 'poor', 'error'))"
    " OR (skill = 'freeball' AND grade IN ('good', 'poor', 'error'))"
    " OR (skill = 'fault' AND grade = 'error')"
)


def _created_at() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now())


def _review_status() -> Mapped[str]:
    return mapped_column(String(16), default="unreviewed", server_default="unreviewed")


class Team(Base):
    __tablename__ = "teams"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), unique=True)
    created_at: Mapped[datetime] = _created_at()


class Player(Base):
    """A roster/profile record for a real person. Never an anonymous tracker ID."""

    __tablename__ = "players"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    display_name: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = _created_at()


class Match(Base):
    __tablename__ = "matches"
    __table_args__ = (
        CheckConstraint("home_team_id <> away_team_id", name="distinct_teams"),
        CheckConstraint("spectators IS NULL OR spectators >= 0", name="nonnegative_spectators"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    home_team_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("teams.id"))
    away_team_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("teams.id"))
    competition: Mapped[str | None] = mapped_column(String(200))
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    venue: Mapped[str | None] = mapped_column(String(200))
    city: Mapped[str | None] = mapped_column(String(200))
    spectators: Mapped[int | None] = mapped_column(Integer)
    first_referee: Mapped[str | None] = mapped_column(String(200))
    second_referee: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = _created_at()


class Video(Base):
    """A registered source video. The file stays in storage; only its key and hash live here."""

    __tablename__ = "videos"
    __table_args__ = (
        CheckConstraint("sha256 ~ '^[0-9a-f]{64}$'", name="sha256_hex"),
        CheckConstraint("size_bytes > 0", name="positive_size"),
        CheckConstraint("width > 0 AND height > 0", name="positive_dimensions"),
        CheckConstraint("fps > 0", name="positive_fps"),
        CheckConstraint("frame_count > 0", name="positive_frame_count"),
        CheckConstraint("duration_sec > 0", name="positive_duration"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    match_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("matches.id"), index=True)
    original_filename: Mapped[str] = mapped_column(String(255))
    storage_key: Mapped[str] = mapped_column(String(1024), unique=True)
    sha256: Mapped[str] = mapped_column(String(64), unique=True)
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    width: Mapped[int] = mapped_column(Integer)
    height: Mapped[int] = mapped_column(Integer)
    fps: Mapped[float] = mapped_column(Float)
    frame_count: Mapped[int] = mapped_column(Integer)
    duration_sec: Mapped[float] = mapped_column(Float)
    duration_source: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = _created_at()


class MatchRoster(Base):
    """A player's entry for one match. `side` ties them to the match's home or away team."""

    __tablename__ = "match_roster"
    __table_args__ = (
        CheckConstraint(SIDE_CHECK, name="valid_side"),
        CheckConstraint("jersey_number BETWEEN 0 AND 99", name="valid_jersey"),
        UniqueConstraint("match_id", "player_id", name="uq_match_roster_match_player"),
        UniqueConstraint("match_id", "side", "jersey_number", name="uq_match_roster_jersey"),
        # Target for composite foreign keys that keep match and side consistent.
        UniqueConstraint("id", "match_id", "side", name="uq_match_roster_identity"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    match_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("matches.id"))
    player_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("players.id"))
    side: Mapped[str] = mapped_column(String(4))
    jersey_number: Mapped[int] = mapped_column(Integer)
    is_libero: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    created_at: Mapped[datetime] = _created_at()


class SetLineup(Base):
    """Who played in a set: starting zone 1-6, or entered as a substitute or libero."""

    __tablename__ = "set_lineups"
    __table_args__ = (
        CheckConstraint(SIDE_CHECK, name="valid_side"),
        CheckConstraint("set_number BETWEEN 1 AND 5", name="valid_set"),
        CheckConstraint("role IN ('starter', 'substitute', 'libero')", name="valid_role"),
        CheckConstraint(
            "(role = 'starter') = (starting_zone IS NOT NULL)", name="zone_for_starters"
        ),
        CheckConstraint(
            "starting_zone IS NULL OR starting_zone BETWEEN 1 AND 6", name="valid_zone"
        ),
        ForeignKeyConstraint(
            ["roster_id", "match_id", "side"],
            ["match_roster.id", "match_roster.match_id", "match_roster.side"],
            name="fk_set_lineups_roster_id_match_roster",
        ),
        UniqueConstraint("roster_id", "set_number", name="uq_set_lineups_roster_set"),
        Index(
            "uq_set_lineups_zone",
            "match_id",
            "set_number",
            "side",
            "starting_zone",
            unique=True,
            postgresql_where=text("starting_zone IS NOT NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    match_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    roster_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    side: Mapped[str] = mapped_column(String(4))
    set_number: Mapped[int] = mapped_column(Integer)
    role: Mapped[str] = mapped_column(String(16))
    starting_zone: Mapped[int | None] = mapped_column(Integer)


class Rally(Base):
    """One rally. The winner may come from the scoreboard, a model, or a person."""

    __tablename__ = "rallies"
    __table_args__ = (
        CheckConstraint("set_number BETWEEN 1 AND 5", name="valid_set"),
        CheckConstraint("rally_number >= 1", name="positive_rally_number"),
        CheckConstraint(
            "serving_side IS NULL OR serving_side IN ('home', 'away')", name="valid_serving_side"
        ),
        CheckConstraint(
            "winning_side IS NULL OR winning_side IN ('home', 'away')", name="valid_winning_side"
        ),
        CheckConstraint("start_sec IS NULL OR start_sec >= 0", name="nonnegative_start"),
        CheckConstraint(
            "end_sec IS NULL OR start_sec IS NULL OR end_sec >= start_sec", name="ordered_times"
        ),
        CheckConstraint(SOURCE_CHECK, name="valid_source"),
        CheckConstraint(CONFIDENCE_CHECK, name="valid_confidence"),
        CheckConstraint(REVIEW_CHECK, name="valid_review_status"),
        UniqueConstraint("match_id", "set_number", "rally_number", name="uq_rallies_order"),
        UniqueConstraint("id", "match_id", name="uq_rallies_identity"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    match_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("matches.id"))
    video_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("videos.id"))
    set_number: Mapped[int] = mapped_column(Integer)
    rally_number: Mapped[int] = mapped_column(Integer)
    serving_side: Mapped[str | None] = mapped_column(String(4))
    winning_side: Mapped[str | None] = mapped_column(String(4))
    start_sec: Mapped[float | None] = mapped_column(Float)
    end_sec: Mapped[float | None] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(16))
    confidence: Mapped[float | None] = mapped_column(Float)
    review_status: Mapped[str] = _review_status()
    created_at: Mapped[datetime] = _created_at()


class Touch(Base):
    """One graded ball contact (or fault) in a rally. `roster_id` is null when unattributed."""

    __tablename__ = "touches"
    __table_args__ = (
        CheckConstraint("sequence >= 1", name="positive_sequence"),
        CheckConstraint(SIDE_CHECK, name="valid_side"),
        CheckConstraint(SKILL_GRADE_CHECK, name="valid_skill_grade"),
        CheckConstraint("video_sec IS NULL OR video_sec >= 0", name="nonnegative_video_sec"),
        CheckConstraint(SOURCE_CHECK, name="valid_source"),
        CheckConstraint(CONFIDENCE_CHECK, name="valid_confidence"),
        CheckConstraint(REVIEW_CHECK, name="valid_review_status"),
        ForeignKeyConstraint(
            ["rally_id", "match_id"],
            ["rallies.id", "rallies.match_id"],
            name="fk_touches_rally_id_rallies",
        ),
        ForeignKeyConstraint(
            ["roster_id", "match_id", "side"],
            ["match_roster.id", "match_roster.match_id", "match_roster.side"],
            name="fk_touches_roster_id_match_roster",
        ),
        UniqueConstraint("rally_id", "sequence", name="uq_touches_order"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    match_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True)
    rally_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    sequence: Mapped[int] = mapped_column(Integer)
    side: Mapped[str] = mapped_column(String(4))
    roster_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    skill: Mapped[str] = mapped_column(String(16))
    grade: Mapped[str] = mapped_column(String(16))
    video_sec: Mapped[float | None] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(16))
    confidence: Mapped[float | None] = mapped_column(Float)
    review_status: Mapped[str] = _review_status()
    created_at: Mapped[datetime] = _created_at()
