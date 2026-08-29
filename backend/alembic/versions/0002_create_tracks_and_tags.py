"""Crea las tablas tracks, tags y track_tags

Revision ID: 0002
Revises: 0001
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tracks",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("artist_text", sa.String(length=300), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column(
            "ingest_source",
            sa.Enum("url", "search", "recognition", name="track_source"),
            nullable=False,
            server_default="url",
        ),
        sa.Column("request_query", sa.String(length=500), nullable=False),
        sa.Column("source_url", sa.String(length=500), nullable=True),
        sa.Column("source_site", sa.String(length=50), nullable=True),
        sa.Column("source_video_id", sa.String(length=64), nullable=True),
        sa.Column("file_path", sa.String(length=500), nullable=True),
        sa.Column("file_size", sa.BigInteger(), nullable=True),
        sa.Column(
            "status",
            sa.Enum("pending", "downloading", "ready", "error", name="track_status"),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("normalized_key", sa.String(length=400), nullable=True),
        sa.Column("bpm", sa.Integer(), nullable=True),
        sa.Column("added_by_user_id", sa.Integer(), nullable=True),
        sa.Column("downloaded_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["added_by_user_id"], ["users.id"], name="fk_tracks_user", ondelete="SET NULL"
        ),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index("ix_tracks_status", "tracks", ["status"])
    op.create_index("ix_tracks_added_by_user_id", "tracks", ["added_by_user_id"])
    op.create_index("ix_tracks_source_video_id", "tracks", ["source_video_id"])
    op.create_index("ix_tracks_normalized_key", "tracks", ["normalized_key"])

    op.create_table(
        "tags",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "kind", sa.Enum("mood", "style", "moment", name="tag_kind"), nullable=False
        ),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("kind", "slug", name="uq_tags_kind_slug"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )

    op.create_table(
        "track_tags",
        sa.Column("track_id", sa.Integer(), nullable=False),
        sa.Column("tag_id", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("track_id", "tag_id"),
        sa.ForeignKeyConstraint(
            ["track_id"], ["tracks.id"], name="fk_track_tags_track", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["tag_id"], ["tags.id"], name="fk_track_tags_tag", ondelete="CASCADE"
        ),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )


def downgrade() -> None:
    op.drop_table("track_tags")
    op.drop_table("tags")
    op.drop_index("ix_tracks_normalized_key", table_name="tracks")
    op.drop_index("ix_tracks_source_video_id", table_name="tracks")
    op.drop_index("ix_tracks_added_by_user_id", table_name="tracks")
    op.drop_index("ix_tracks_status", table_name="tracks")
    op.drop_table("tracks")
