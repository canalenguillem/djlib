"""Version para DJ en las tandas

Revision ID: 0018
Revises: 0017
"""

import sqlalchemy as sa
from alembic import op

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("download_batches", sa.Column("version", sa.String(20), nullable=True))


def downgrade() -> None:
    op.drop_column("download_batches", "version")
