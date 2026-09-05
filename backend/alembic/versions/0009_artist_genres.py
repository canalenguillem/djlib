"""Generos del artista, de los que salen las etiquetas de estilo

Revision ID: 0009
Revises: 0008
"""

import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("artists", sa.Column("genres", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("artists", "genres")
