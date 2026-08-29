"""Crea las fichas de artista de las canciones que ya estaban en la biblioteca.

Las canciones descargadas antes de existir este modulo no tienen artistas
vinculados. Este comando los deduce de su campo de artista, crea las fichas que
falten y las manda a enriquecer. Es idempotente: pasarlo dos veces no duplica.

Uso:  docker compose exec backend python -m app.cli.link_artists
"""

import sys

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.artist import EnrichmentStatus
from app.models.track import Track, TrackStatus
from app.services import artist_service


def main() -> int:
    with SessionLocal() as db:
        tracks = list(
            db.scalars(select(Track).where(Track.status == TrackStatus.ready))
        )
        pendientes: set[int] = set()
        vinculadas = 0

        for track in tracks:
            if track.artists:  # ya tiene ficha: no se toca
                continue
            artists = artist_service.link_track_artists(db, track)
            if not artists:
                continue
            vinculadas += 1
            pendientes.update(
                a.id for a in artists if a.enrichment_status == EnrichmentStatus.pending
            )
        db.commit()

    print(f"[link_artists] {vinculadas} canciones vinculadas a su artista.")

    if pendientes:
        print(f"[link_artists] Consultando MusicBrainz y Wikipedia para {len(pendientes)} fichas...")
        artist_service.run_enrichment(SessionLocal, sorted(pendientes))
        print("[link_artists] Listo.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
