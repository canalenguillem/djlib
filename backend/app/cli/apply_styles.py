"""Etiqueta con su estilo las canciones que ya estaban en la biblioteca.

Usa los generos que MusicBrainz asigna a cada artista. No toca las canciones
que ya tienen alguna etiqueta de estilo: lo que haya puesto el usuario manda.

Uso:  docker compose exec backend python -m app.cli.apply_styles
"""

import sys

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.artist import Artist
from app.models.tag import TagKind
from app.models.track import Track, TrackStatus
from app.services import artist_service


def main() -> int:
    # Primero, rellenar los generos de las fichas que aun no los tengan
    with SessionLocal() as db:
        sin_generos = [
            a.id
            for a in db.scalars(select(Artist).where(Artist.genres.is_(None)))
        ]

    if sin_generos:
        print(f"[apply_styles] Consultando generos de {len(sin_generos)} artistas...")
        for artist_id in sin_generos:
            with SessionLocal() as db:
                artist = db.get(Artist, artist_id)
                if artist is None:
                    continue
                # Sin forzar: asi las fichas editadas a mano no se pisan
                artist_service.enrich(db, artist)
                db.commit()

    with SessionLocal() as db:
        tracks = list(
            db.scalars(select(Track).where(Track.status == TrackStatus.ready))
        )
        etiquetadas = 0
        for track in tracks:
            if any(t.kind == TagKind.style for t in track.tags):
                continue
            nuevas = artist_service.apply_style_tags(db, track)
            if nuevas:
                etiquetadas += 1
                print(f"  {track.title[:44]:<44} {', '.join(t.name for t in nuevas)}")
        db.commit()

    print(f"[apply_styles] {etiquetadas} canciones etiquetadas.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
