"""Vuelve a consultar las fuentes para las fichas a las que les falta la foto.

Las fichas creadas antes de que se guardara la imagen no la tienen. Este
comando las repasa. No toca las que estan en estado `manual`: esas las ha
editado el usuario y solo se rehacen a mano desde la propia ficha.

Uso:  docker compose exec backend python -m app.cli.refresh_artists
"""

import sys

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.artist import Artist, EnrichmentStatus
from app.services import artist_service


def main() -> int:
    with SessionLocal() as db:
        pendientes = list(
            db.scalars(
                select(Artist).where(
                    Artist.image_url.is_(None),
                    Artist.enrichment_status != EnrichmentStatus.manual,
                )
            )
        )

    print(f"[refresh_artists] {len(pendientes)} fichas sin foto.")
    con_foto = 0
    for artist in pendientes:
        with SessionLocal() as db:
            actual = db.get(Artist, artist.id)
            if actual is None:
                continue
            artist_service.enrich(db, actual)
            db.commit()
            if actual.image_url:
                con_foto += 1
                # El estado no basta: cuando el canal solo tapa el hueco de la
                # foto, la ficha sigue siendo "ok" con datos de MusicBrainz.
                origen = (
                    "canal de YouTube"
                    if "yt3.googleusercontent.com" in (actual.image_url or "")
                    else "Wikipedia"
                )
                print(f"  {actual.name}: foto de {origen}")
            else:
                print(f"  {actual.name}: sin foto en ninguna fuente")

    print(f"[refresh_artists] {con_foto} fichas con foto nueva.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
