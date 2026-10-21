"""Crate de destino de una cancion que aun se esta descargando

Revision ID: 0012
Revises: 0011
"""

import sqlalchemy as sa
from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tracks", sa.Column("pending_crate_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_tracks_pending_crate_id",
        "tracks",
        "crates",
        ["pending_crate_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_tracks_pending_crate_id", "tracks", type_="foreignkey")
    op.drop_column("tracks", "pending_crate_id")
