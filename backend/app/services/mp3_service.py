"""Copias en mp3 de las canciones, para sacarlas del servidor.

YouTube sirve m4a, pero los CDJ y rekordbox se llevan mejor con mp3. Se
convierte al terminar cada descarga y se guarda en cache junto al original,
que sigue siendo el que suena en el reproductor; asi bajarla del servidor,
suelta o en un zip, sale al instante. Si aun no esta, se convierte al pedirla.

MP3 a 320 kbps constantes: el VBR hace que algunos CDJ calculen mal el tiempo
y salten mal a los cues. El original ya viene con perdida, asi que no gana
calidad, pero tampoco pierde casi nada mas.
"""

from __future__ import annotations

import logging
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from app.core.config import settings
from app.models.track import Track

logger = logging.getLogger(__name__)

# ffmpeg a la vez como mucho: deja aire a las descargas y al resto del servidor
CONVERSIONES_SIMULTANEAS = 4


class Mp3Error(RuntimeError):
    pass


def cache_dir() -> Path:
    ruta = Path(settings.music_dir) / "mp3"
    ruta.mkdir(parents=True, exist_ok=True)
    return ruta


def _ffmpeg(origen: Path, destino: Path, titulo: str | None, artista: str | None) -> None:
    args = [
        "ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
        "-i", str(origen),
        "-vn", "-map_metadata", "-1",
        "-codec:a", "libmp3lame", "-b:a", "320k",
        "-id3v2_version", "3",
    ]
    if titulo:
        args += ["-metadata", f"title={titulo}"]
    if artista:
        args += ["-metadata", f"artist={artista}"]
    args.append(str(destino))
    try:
        subprocess.run(args, check=True, capture_output=True, timeout=300)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as exc:
        detalle = getattr(exc, "stderr", b"") or b""
        raise Mp3Error(detalle.decode(errors="replace")[-300:] or str(exc)) from exc


def as_mp3(track: Track) -> Path:
    """Ruta de la cancion en mp3: el propio fichero si ya lo es, o su copia
    en cache, convirtiendola si hace falta. Mp3Error si ffmpeg falla."""
    origen = Path(track.file_path)
    if origen.suffix.lower() == ".mp3":
        return origen

    destino = cache_dir() / f"{origen.stem}.mp3"
    if destino.exists() and destino.stat().st_mtime >= origen.stat().st_mtime:
        return destino

    # A un temporal y luego se renombra: una conversion cortada a medias no
    # debe quedar en cache como si fuera buena
    temporal = destino.with_suffix(".parcial.mp3")
    temporal.unlink(missing_ok=True)
    try:
        _ffmpeg(origen, temporal, track.title, track.artist_text)
        temporal.replace(destino)
    finally:
        temporal.unlink(missing_ok=True)
    return destino


def as_mp3_many(tracks: list[Track]) -> list[Path]:
    """Convierte varias en paralelo. Si alguna falla, va en su formato
    original: mejor un m4a suelto que quedarse sin el crate entero."""

    def una(track: Track) -> Path:
        try:
            return as_mp3(track)
        except Mp3Error as exc:
            logger.warning("No se pudo pasar a mp3 el track %s: %s", track.id, exc)
            return Path(track.file_path)

    with ThreadPoolExecutor(max_workers=CONVERSIONES_SIMULTANEAS) as pool:
        return list(pool.map(una, tracks))


def forget(file_path: str | None) -> None:
    """Borra la copia en mp3 de una cancion que se elimina."""
    if file_path:
        (Path(settings.music_dir) / "mp3" / f"{Path(file_path).stem}.mp3").unlink(missing_ok=True)
