"""Menus que ve cada usuario

Revision ID: 0014
Revises: 0013
"""

import sqlalchemy as sa
from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Vacio (NULL) es todos: asi los usuarios de antes no pierden nada
    op.add_column("users", sa.Column("menus", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "menus")
