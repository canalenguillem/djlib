"""Claves de IA de cada usuario y proveedor elegido

Revision ID: 0022
Revises: 0021
"""

import sqlalchemy as sa
from alembic import op

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_keys",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("api_key_cifrada", sa.Text, nullable=False),
        sa.Column("pista", sa.String(8), nullable=False),
        sa.Column("model", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
        sa.UniqueConstraint("user_id", "provider", name="uq_ai_keys_user_provider"),
        mysql_engine="InnoDB",
    )
    op.add_column("users", sa.Column("ai_provider", sa.String(20), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "ai_provider")
    op.drop_table("ai_keys")
