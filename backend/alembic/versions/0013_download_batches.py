"""Tandas de descarga que hace el servidor solo

Revision ID: 0013
Revises: 0012
"""

import sqlalchemy as sa
from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "download_batches",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("crate_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_download_batches_user", ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["crate_id"], ["crates.id"], name="fk_download_batches_crate", ondelete="SET NULL"
        ),
        mysql_engine="InnoDB",
    )
    op.create_index("ix_download_batches_user_id", "download_batches", ["user_id"])
    op.create_table(
        "download_batch_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("batch_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("artist", sa.String(300), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("video_title", sa.String(300), nullable=True),
        sa.Column("track_id", sa.Integer(), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["batch_id"],
            ["download_batches.id"],
            name="fk_download_batch_items_batch",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["track_id"], ["tracks.id"], name="fk_download_batch_items_track", ondelete="SET NULL"
        ),
        mysql_engine="InnoDB",
    )
    op.create_index(
        "ix_download_batch_items_status",
        "download_batch_items",
        ["status", "batch_id", "position"],
    )


def downgrade() -> None:
    op.drop_table("download_batch_items")
    op.drop_table("download_batches")
