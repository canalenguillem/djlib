"""Historial de busquedas en YouTube

Revision ID: 0019
Revises: 0018
"""

import sqlalchemy as sa
from alembic import op

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "search_history",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(300), nullable=True),
        sa.Column("artist", sa.String(300), nullable=True),
        sa.Column("version", sa.String(20), nullable=True),
        sa.Column("results", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime, nullable=False),
        mysql_engine="InnoDB",
    )
    op.create_index("ix_search_history_user_created", "search_history", ["user_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_search_history_user_created", table_name="search_history")
    op.drop_table("search_history")
