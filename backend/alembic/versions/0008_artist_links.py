"""Enlaces externos del artista (Bandcamp, SoundCloud, Discogs...)

Revision ID: 0008
Revises: 0007
"""

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("artists", sa.Column("links", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("artists", "links")
