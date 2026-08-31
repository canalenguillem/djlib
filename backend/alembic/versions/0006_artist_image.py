"""Anade la foto del artista

Revision ID: 0006
Revises: 0005
"""

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("artists", sa.Column("image_url", sa.String(length=700), nullable=True))


def downgrade() -> None:
    op.drop_column("artists", "image_url")
