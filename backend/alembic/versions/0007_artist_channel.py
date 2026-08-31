"""Datos del canal de YouTube en la ficha del artista

Revision ID: 0007
Revises: 0006
"""

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None

ANTIGUO = sa.Enum("pending", "ok", "not_found", "error", "manual", name="enrichment_status")
NUEVO = sa.Enum(
    "pending", "ok", "youtube", "not_found", "error", "manual", name="enrichment_status"
)


def upgrade() -> None:
    op.add_column("artists", sa.Column("channel_url", sa.String(length=500), nullable=True))
    op.add_column("artists", sa.Column("follower_count", sa.Integer(), nullable=True))
    # Los creadores de edits no estan en MusicBrainz ni en Wikipedia, pero su
    # canal si: hace falta un estado que lo distinga de "no encontrado".
    op.alter_column(
        "artists",
        "enrichment_status",
        existing_type=ANTIGUO,
        type_=NUEVO,
        existing_nullable=False,
        existing_server_default="pending",
    )


def downgrade() -> None:
    op.execute("UPDATE artists SET enrichment_status = 'ok' WHERE enrichment_status = 'youtube'")
    op.alter_column(
        "artists",
        "enrichment_status",
        existing_type=NUEVO,
        type_=ANTIGUO,
        existing_nullable=False,
        existing_server_default="pending",
    )
    op.drop_column("artists", "follower_count")
    op.drop_column("artists", "channel_url")
