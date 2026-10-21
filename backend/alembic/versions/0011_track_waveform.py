"""Forma de onda de cada cancion

Revision ID: 0011
Revises: 0010
"""

import sqlalchemy as sa
from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Las canciones que ya estaban en la biblioteca se quedan sin onda: se
    # calcula la primera vez que alguien la pide.
    op.add_column("tracks", sa.Column("waveform", sa.LargeBinary(), nullable=True))


def downgrade() -> None:
    op.drop_column("tracks", "waveform")
