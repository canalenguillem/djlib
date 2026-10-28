"""Escuchas: cada cancion que suena en el reproductor o en el mezclador

Revision ID: 0015
Revises: 0014
"""

import sqlalchemy as sa
from alembic import op

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "listens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column(
            "track_id", sa.Integer(), sa.ForeignKey("tracks.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("source", sa.Enum("player", "mixer", name="listen_source"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_listens_user_created", "listens", ["user_id", "created_at"])


def downgrade() -> None:
    op.drop_table("listens")
