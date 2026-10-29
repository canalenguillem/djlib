"""Canciones empaquetadas en un zip, para llevarlas al USB."""

import re
import tempfile
import zipfile
from pathlib import Path

from app.models.track import Track
from app.services import mp3_service


def nombre_seguro(texto: str) -> str:
    limpio = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", texto).strip(" .")
    return limpio[:100] or "track"


def descargadas(tracks: list[Track]) -> list[Track]:
    """Las que tienen el fichero en disco: las demas no se pueden meter."""
    return [t for t in tracks if t.file_path and Path(t.file_path).exists()]


def build_zip(entradas: list[tuple[str, Track]]) -> Path:
    """Escribe el zip en un temporal y devuelve su ruta; borrarlo es cosa de
    quien lo sirve. Cada entrada lleva el prefijo de su nombre ("01 - " en un
    crate, nada en una seleccion suelta). Van en mp3, que es lo que mejor leen
    rekordbox y los CDJ; la primera vez hay que convertirlas."""
    temporal = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
    temporal.close()
    destino = Path(temporal.name)

    ficheros = mp3_service.as_mp3_many([track for _, track in entradas])

    usados: set[str] = set()
    # Sin comprimir: el audio ya viene comprimido y deflate solo gastaria CPU
    # para no ahorrar practicamente nada.
    with zipfile.ZipFile(destino, "w", zipfile.ZIP_STORED) as zip_file:
        for (prefijo, track), origen in zip(entradas, ficheros):
            partes = [p for p in (track.artist_text, track.title) if p]
            base = f"{prefijo}{nombre_seguro(' - '.join(partes) or 'track')}"
            # Dos versiones con el mismo titulo se pisarian al descomprimir
            nombre, n = f"{base}{origen.suffix}", 2
            while nombre.lower() in usados:
                nombre, n = f"{base} ({n}){origen.suffix}", n + 1
            usados.add(nombre.lower())
            zip_file.write(origen, nombre)

    return destino
