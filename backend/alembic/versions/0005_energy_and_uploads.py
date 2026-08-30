"""Anade la energia de 1 a 5 y el origen 'upload'

Revision ID: 0005
Revises: 0004
"""

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tracks", sa.Column("energy", sa.Integer(), nullable=True))
    op.create_index("ix_tracks_energy", "tracks", ["energy"])
    # La musica ya no viene solo de YouTube: tambien se pueden subir ficheros
    # propios (compras, record pools).
    op.alter_column(
        "tracks",
        "ingest_source",
        existing_type=sa.Enum("url", "search", "recognition", name="track_source"),
        type_=sa.Enum("url", "search", "recognition", "upload", name="track_source"),
        existing_nullable=False,
        existing_server_default="url",
    )


def downgrade() -> None:
    op.alter_column(
        "tracks",
        "ingest_source",
        existing_type=sa.Enum("url", "search", "recognition", "upload", name="track_source"),
        type_=sa.Enum("url", "search", "recognition", name="track_source"),
        existing_nullable=False,
        existing_server_default="url",
    )
    op.drop_index("ix_tracks_energy", table_name="tracks")
    op.drop_column("tracks", "energy")
