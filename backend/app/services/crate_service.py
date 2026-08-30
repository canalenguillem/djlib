"""Crates: selecciones de canciones con nombre y orden propio.

Lo que distingue un crate de un filtro es que no cambia solo. El orden es el
dato importante, asi que toda la logica gira alrededor de mantener las
posiciones consecutivas y sin huecos.
"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.text import slugify
from app.core.time import utcnow
from app.models.crate import Crate, CrateTrack
from app.models.track import Track, TrackStatus
from app.models.user import User


class CrateError(ValueError):
    pass


def get_by_id(db: Session, crate_id: int) -> Crate | None:
    return db.get(Crate, crate_id)


def get_by_slug(db: Session, slug: str) -> Crate | None:
    return db.scalar(select(Crate).where(Crate.slug == slug))


def list_crates(db: Session) -> list[Crate]:
    return list(db.scalars(select(Crate).order_by(Crate.name)))


def _renumber(crate: Crate) -> None:
    """Deja las posiciones consecutivas desde 0. Se llama tras cada cambio para
    que no queden huecos ni empates que hagan el orden ambiguo."""
    for indice, entrada in enumerate(sorted(crate.entries, key=lambda e: e.position)):
        entrada.position = indice


def _existing_ready_tracks(db: Session, track_ids: list[int]) -> list[Track]:
    """Devuelve las canciones pedidas, en el orden pedido, ignorando las que no
    existan. Solo entran las que estan listas: un crate con descargas a medias
    no sirve para pinchar."""
    if not track_ids:
        return []
    encontradas = {
        t.id: t
        for t in db.scalars(
            select(Track).where(Track.id.in_(track_ids), Track.status == TrackStatus.ready)
        )
    }
    return [encontradas[i] for i in track_ids if i in encontradas]


def create_crate(
    db: Session,
    *,
    name: str,
    user: User,
    description: str | None = None,
    track_ids: list[int] | None = None,
) -> Crate:
    name = name.strip()
    slug = slugify(name)
    if not slug:
        raise CrateError("El nombre del crate no es valido.")
    if get_by_slug(db, slug) is not None:
        raise CrateError(f"Ya existe un crate llamado '{name}'.")

    crate = Crate(
        name=name,
        slug=slug,
        description=(description or "").strip() or None,
        created_by_user_id=user.id,
    )
    db.add(crate)
    db.flush()

    for posicion, track in enumerate(_existing_ready_tracks(db, track_ids or [])):
        crate.entries.append(CrateTrack(track_id=track.id, position=posicion))
    db.flush()
    return crate


def rename_crate(db: Session, crate: Crate, name: str) -> Crate:
    name = name.strip()
    slug = slugify(name)
    if not slug:
        raise CrateError("El nombre del crate no es valido.")
    choque = get_by_slug(db, slug)
    if choque is not None and choque.id != crate.id:
        raise CrateError(f"Ya existe un crate llamado '{name}'.")
    crate.name = name
    crate.slug = slug
    crate.updated_at = utcnow()
    return crate


def add_track(db: Session, crate: Crate, track_id: int) -> Crate:
    if any(entrada.track_id == track_id for entrada in crate.entries):
        raise CrateError("Esa cancion ya esta en el crate.")
    if not _existing_ready_tracks(db, [track_id]):
        raise CrateError("La cancion no existe o todavia no esta descargada.")

    siguiente = db.scalar(
        select(func.coalesce(func.max(CrateTrack.position), -1) + 1).where(
            CrateTrack.crate_id == crate.id
        )
    )
    crate.entries.append(CrateTrack(track_id=track_id, position=siguiente or 0))
    crate.updated_at = utcnow()
    db.flush()
    return crate


def remove_track(db: Session, crate: Crate, track_id: int) -> Crate:
    entrada = next((e for e in crate.entries if e.track_id == track_id), None)
    if entrada is None:
        raise CrateError("Esa cancion no esta en el crate.")
    crate.entries.remove(entrada)
    db.flush()
    _renumber(crate)
    crate.updated_at = utcnow()
    return crate


def reorder(db: Session, crate: Crate, track_ids: list[int]) -> Crate:
    """Fija el contenido y el orden del crate de una vez.

    Es lo que usa el arrastrar y soltar del frontend: en vez de mandar
    movimientos sueltos, se manda la lista final y aqui se concilia. Asi dos
    reordenaciones seguidas no pueden dejar el crate en un estado raro.
    """
    actuales = {e.track_id for e in crate.entries}
    pedidos = list(dict.fromkeys(track_ids))  # sin duplicados, conservando orden

    desconocidos = set(pedidos) - actuales
    if desconocidos:
        raise CrateError(
            f"Estas canciones no estan en el crate: {sorted(desconocidos)}"
        )
    if set(pedidos) != actuales:
        faltan = actuales - set(pedidos)
        raise CrateError(f"Falta indicar la posicion de: {sorted(faltan)}")

    posiciones = {track_id: indice for indice, track_id in enumerate(pedidos)}
    for entrada in crate.entries:
        entrada.position = posiciones[entrada.track_id]
    crate.updated_at = utcnow()
    db.flush()
    return crate
