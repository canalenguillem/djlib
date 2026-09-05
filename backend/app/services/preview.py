"""Fragmentos de audio para decidir si una version es la buena antes de bajarla.

Se descarga solo un trozo del medio de la cancion, que es donde suele estar el
estribillo o el drop, y se guarda en cache: pinchar dos veces el mismo candidato
no vuelve a salir a la red.
"""

from __future__ import annotations

import logging
import subprocess
import time
from pathlib import Path

from app.core.config import settings
from app.services.downloader import DownloadError, _base_args, _run, extract_youtube_id

logger = logging.getLogger(__name__)


def cache_dir() -> Path:
    ruta = Path(settings.music_dir) / "previews"
    ruta.mkdir(parents=True, exist_ok=True)
    return ruta


def _limpiar_cache() -> None:
    """Deja como mucho PREVIEW_CACHE_FILES, borrando los mas antiguos.

    Son fragmentos desechables: no merecen crecer sin limite en el mismo disco
    donde vive la biblioteca de verdad.
    """
    ficheros = sorted(cache_dir().glob("*.m4a"), key=lambda f: f.stat().st_mtime)
    sobran = len(ficheros) - settings.preview_cache_files
    for fichero in ficheros[: max(0, sobran)]:
        fichero.unlink(missing_ok=True)


def build(url: str) -> Path:
    """Devuelve la ruta del fragmento, descargandolo si no estaba en cache."""
    video_id = extract_youtube_id(url)
    if not video_id:
        raise DownloadError("Solo se pueden escuchar fragmentos de videos de YouTube.")

    destino = cache_dir() / f"{video_id}.m4a"
    if destino.exists():
        # Se marca como reciente para que la limpieza no se lo lleve
        destino.touch()
        return destino

    inicio = settings.preview_start_seconds
    fin = inicio + settings.preview_seconds
    temporal = destino.with_suffix(".parcial.m4a")
    temporal.unlink(missing_ok=True)

    _run(
        _base_args()
        + [
            "--format",
            settings.ytdlp_format,
            # Solo ese tramo: bajar el tema entero para escuchar medio minuto
            # seria absurdo, y ademas tardaria.
            "--download-sections",
            f"*{inicio}-{fin}",
            "--force-keyframes-at-cuts",
            "--output",
            str(temporal),
            url,
        ]
    )

    resultado = next(iter(sorted(temporal.parent.glob(f"{video_id}.parcial*"))), None)
    if resultado is None or not resultado.exists():
        raise DownloadError("No se pudo preparar el fragmento.")
    resultado.rename(destino)

    _limpiar_cache()
    return destino


def touch_time(path: Path) -> float:
    return path.stat().st_mtime if path.exists() else time.time()
