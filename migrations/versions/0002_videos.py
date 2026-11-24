"""Add the videos table: registered source videos, stored outside the database."""

import sqlalchemy as sa
from alembic import op

revision = "0002_videos"
down_revision = "0001_bootstrap"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "videos",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("storage_key", sa.String(1024), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("fps", sa.Float(), nullable=False),
        sa.Column("frame_count", sa.Integer(), nullable=False),
        sa.Column("duration_sec", sa.Float(), nullable=False),
        sa.Column("duration_source", sa.String(64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_videos"),
        sa.UniqueConstraint("storage_key", name="uq_videos_storage_key"),
        sa.UniqueConstraint("sha256", name="uq_videos_sha256"),
        sa.CheckConstraint("sha256 ~ '^[0-9a-f]{64}$'", name="ck_videos_sha256_hex"),
        sa.CheckConstraint("size_bytes > 0", name="ck_videos_positive_size"),
        sa.CheckConstraint("width > 0 AND height > 0", name="ck_videos_positive_dimensions"),
        sa.CheckConstraint("fps > 0", name="ck_videos_positive_fps"),
        sa.CheckConstraint("frame_count > 0", name="ck_videos_positive_frame_count"),
        sa.CheckConstraint("duration_sec > 0", name="ck_videos_positive_duration"),
    )


def downgrade() -> None:
    op.drop_table("videos")
