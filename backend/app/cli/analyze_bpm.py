"""Detecta el tempo de las canciones que todavia no lo tienen.

Las descargadas antes de que existiera el analisis no tienen BPM. No toca las
que ya lo tienen: puede haberlo corregido el usuario a mano.

Uso:  docker compose exec backend python -m app.cli.analyze_bpm
"""

import sys

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.track import Track, TrackStatus
from app.services import track_service


def main() -> int:
    with SessionLocal() as db:
        pendientes = list(
            db.scalars(
                select(Track).where(
                    Track.status == TrackStatus.ready, Track.bpm.is_(None)
                ).order_by(Track.id)
            )
        )
        datos = [(t.id, t.title) for t in pendientes]

    print(f"[analyze_bpm] {len(datos)} canciones sin tempo.")
    medidas = 0
    for track_id, titulo in datos:
        detectado = track_service.analyze_bpm(SessionLocal, track_id)
        if detectado:
            medidas += 1
            print(f"  {titulo[:52]:<52} {detectado} BPM")
        else:
            print(f"  {titulo[:52]:<52} no se ha podido determinar")

    print(f"[analyze_bpm] {medidas} de {len(datos)} medidas.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
