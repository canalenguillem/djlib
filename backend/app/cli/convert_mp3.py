"""Hace la copia en mp3 de las canciones que todavia no la tienen.

Las nuevas se convierten solas al descargarse; esto es para las de antes, que
si no esperarian a ffmpeg la primera vez que alguien las baja. Se puede cortar
y volver a lanzar: las ya convertidas se saltan al instante.

Uso:  docker compose -f docker-compose.prod.yml exec backend python -m app.cli.convert_mp3
"""

import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.track import Track, TrackStatus
from app.services import mp3_service, zip_export


def main() -> int:
    with SessionLocal() as db:
        tracks = zip_export.descargadas(
            list(db.scalars(select(Track).where(Track.status == TrackStatus.ready).order_by(Track.id)))
        )
        for track in tracks:
            db.expunge(track)

    print(f"[convert_mp3] {len(tracks)} canciones descargadas.", flush=True)
    inicio = time.monotonic()
    fallidas = 0

    def una(track: Track) -> None:
        mp3_service.as_mp3(track)

    with ThreadPoolExecutor(max_workers=mp3_service.CONVERSIONES_SIMULTANEAS) as pool:
        tareas = {pool.submit(una, t): t for t in tracks}
        for hechas, tarea in enumerate(as_completed(tareas), start=1):
            try:
                tarea.result()
            except mp3_service.Mp3Error as exc:
                fallidas += 1
                print(f"  fallo: {tareas[tarea].title[:60]}: {exc}", flush=True)
            if hechas % 50 == 0 or hechas == len(tracks):
                minutos = (time.monotonic() - inicio) / 60
                print(f"[convert_mp3] {hechas}/{len(tracks)} en {minutos:.1f} min", flush=True)

    print(f"[convert_mp3] Hecho; {fallidas} no se han podido convertir.", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
