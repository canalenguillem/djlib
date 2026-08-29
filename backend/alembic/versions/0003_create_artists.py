"""Crea artists, artist_relations y track_artists

Revision ID: 0003
Revises: 0002
"""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "artists",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("slug", sa.String(length=200), nullable=False),
        sa.Column("bio", sa.Text(), nullable=True),
        sa.Column("country", sa.String(length=80), nullable=True),
        sa.Column("begin_year", sa.Integer(), nullable=True),
        sa.Column("end_year", sa.Integer(), nullable=True),
        sa.Column("artist_type", sa.String(length=40), nullable=True),
        sa.Column("musicbrainz_id", sa.String(length=36), nullable=True),
        sa.Column("wikipedia_url", sa.String(length=500), nullable=True),
        sa.Column(
            "enrichment_status",
            sa.Enum(
                "pending", "ok", "not_found", "error", "manual", name="enrichment_status"
            ),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("enrichment_error", sa.String(length=400), nullable=True),
        sa.Column("enriched_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug", name="uq_artists_slug"),
        sa.UniqueConstraint("musicbrainz_id", name="uq_artists_musicbrainz_id"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )

    op.create_table(
        "artist_relations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("artist_id", sa.Integer(), nullable=False),
        sa.Column("related_artist_id", sa.Integer(), nullable=True),
        sa.Column("related_name", sa.String(length=200), nullable=False),
        sa.Column("relation_type", sa.String(length=60), nullable=False),
        sa.Column("related_musicbrainz_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["artist_id"], ["artists.id"], name="fk_relation_artist", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["related_artist_id"],
            ["artists.id"],
            name="fk_relation_related_artist",
            ondelete="SET NULL",
        ),
        sa.UniqueConstraint(
            "artist_id", "related_name", "relation_type", name="uq_artist_relation"
        ),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index("ix_artist_relations_artist_id", "artist_relations", ["artist_id"])

    op.create_table(
        "track_artists",
        sa.Column("track_id", sa.Integer(), nullable=False),
        sa.Column("artist_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("track_id", "artist_id"),
        sa.ForeignKeyConstraint(
            ["track_id"], ["tracks.id"], name="fk_track_artists_track", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["artist_id"], ["artists.id"], name="fk_track_artists_artist", ondelete="CASCADE"
        ),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )


def downgrade() -> None:
    op.drop_table("track_artists")
    op.drop_index("ix_artist_relations_artist_id", table_name="artist_relations")
    op.drop_table("artist_relations")
    op.drop_table("artists")
