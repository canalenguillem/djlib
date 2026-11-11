"""SoundCloud: menu propio y sitio en el historial de busquedas

Revision ID: 0020
Revises: 0019
"""

import json

import sqlalchemy as sa
from alembic import op

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None

users = sa.table("users", sa.column("id", sa.Integer), sa.column("menus", sa.JSON))


def _cambiar(cambio) -> None:
    conexion = op.get_bind()
    for id_, menus in conexion.execute(sa.select(users.c.id, users.c.menus)).all():
        # Vacio es todos: a esos les llega el menu nuevo sin hacer nada
        if menus is None:
            continue
        if isinstance(menus, str):
            menus = json.loads(menus)
        nuevos = cambio(menus)
        if nuevos != menus:
            conexion.execute(users.update().where(users.c.id == id_).values(menus=nuevos))


def upgrade() -> None:
    op.add_column(
        "search_history",
        sa.Column("source", sa.String(20), nullable=False, server_default="youtube"),
    )
    # Quien puede bajar de YouTube puede bajar de SoundCloud
    _cambiar(lambda m: m + ["soundcloud"] if "youtube" in m and "soundcloud" not in m else m)


def downgrade() -> None:
    _cambiar(lambda m: [x for x in m if x != "soundcloud"])
    op.drop_column("search_history", "source")
