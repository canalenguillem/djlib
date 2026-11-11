"""Sitio donde busca cada tanda (YouTube o SoundCloud)

Revision ID: 0021
Revises: 0020
"""

import sqlalchemy as sa
from alembic import op

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "download_batches",
        sa.Column("source", sa.String(20), nullable=False, server_default="youtube"),
    )


def downgrade() -> None:
    op.drop_column("download_batches", "source")
