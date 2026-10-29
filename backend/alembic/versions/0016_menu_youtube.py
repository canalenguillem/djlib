"""Menu de YouTube

Revision ID: 0016
Revises: 0015
"""

import json

import sqlalchemy as sa
from alembic import op

revision = "0016"
down_revision = "0015"
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
    # Bajar de YouTube estaba dentro de la biblioteca: quien la tenia lo conserva
    _cambiar(lambda m: m + ["youtube"] if "library" in m and "youtube" not in m else m)


def downgrade() -> None:
    _cambiar(lambda m: [x for x in m if x != "youtube"])
