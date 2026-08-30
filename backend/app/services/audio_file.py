"""Lectura de ficheros de audio que sube el usuario.

Cuando la musica no viene de YouTube sino del disco del usuario (una compra en
Bandcamp o Beatport, una descarga de un record pool), los metadatos hay que
sacarlos del propio fichero.
"""

from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

# Lo que aceptamos subir. Se admiten los formatos sin perdida (wav, aiff, flac)
# porque son justo los que compra un DJ para pinchar en un sistema grande.
ALLOWED_EXTENSIONS = {
    ".mp3", ".m4a", ".aac", ".wav", ".aiff", ".aif", ".flac", ".ogg", ".opus", ".wma",
}


class AudioFileError(ValueError):
    pass


@dataclass(frozen=True)
class AudioMetadata:
    duration_seconds: int | None
    title: str | None
    artist: str | None
    album: str | None
    codec: str | None
    bit_rate: int | None


def normalize_extension(filename: str) -> str:
    extension = Path(filename).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        permitidas = ", ".join(sorted(e.lstrip(".") for e in ALLOWED_EXTENSIONS))
        raise AudioFileError(
            f"Formato no admitido ({extension or 'sin extension'}). "
            f"Se aceptan: {permitidas}."
        )
    return extension


def probe(path: Path) -> AudioMetadata:
    """Lee duracion y etiquetas con ffprobe.

    Sirve ademas de validacion: si ffprobe no reconoce una pista de audio, el
    fichero no es audio por mucho que la extension diga lo contrario.
    """
    try:
        salida = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-select_streams", "a:0",
                "-show_entries", "stream=codec_name,bit_rate:format=duration,bit_rate:format_tags=title,artist,album",
                "-of", "json",
                str(path),
            ],
            capture_output=True, text=True, timeout=60, check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise AudioFileError("El fichero ha tardado demasiado en analizarse.") from exc

    if salida.returncode != 0:
        raise AudioFileError("El fichero no parece audio valido.")

    datos = json.loads(salida.stdout or "{}")
    streams = datos.get("streams") or []
    if not streams:
        raise AudioFileError("El fichero no contiene ninguna pista de audio.")

    formato = datos.get("format") or {}
    etiquetas = {k.lower(): v for k, v in (formato.get("tags") or {}).items()}
    duracion = formato.get("duration")

    def entero(valor) -> int | None:
        try:
            return int(float(valor))
        except (TypeError, ValueError):
            return None

    return AudioMetadata(
        duration_seconds=entero(duracion),
        title=(etiquetas.get("title") or "").strip() or None,
        artist=(etiquetas.get("artist") or "").strip() or None,
        album=(etiquetas.get("album") or "").strip() or None,
        codec=streams[0].get("codec_name"),
        bit_rate=entero(streams[0].get("bit_rate") or formato.get("bit_rate")),
    )
