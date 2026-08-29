"""Envoltorio sobre yt-dlp.

Todo el contacto con el exterior vive aqui, en dos funciones puras de efectos
(`resolve` y `download`), para que el resto del codigo no sepa de subprocesos
y para que los tests puedan sustituirlas sin tocar la red.
"""

from __future__ import annotations

import json
import logging
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from app.core.config import settings
from app.core.text import split_artist_title

logger = logging.getLogger(__name__)

YOUTUBE_ID_PATTERNS = (
    re.compile(r"(?:youtube\.com/watch\?(?:.*&)?v=)([A-Za-z0-9_-]{11})"),
    re.compile(r"(?:youtu\.be/)([A-Za-z0-9_-]{11})"),
    re.compile(r"(?:youtube\.com/(?:shorts|embed|live)/)([A-Za-z0-9_-]{11})"),
)


class DownloadError(RuntimeError):
    """Fallo recuperable y explicable al usuario (video privado, borrado...)."""


@dataclass(frozen=True)
class MediaInfo:
    video_id: str
    title: str
    artist: str | None
    duration_seconds: int | None
    webpage_url: str
    site: str


def extract_youtube_id(url: str) -> str | None:
    for pattern in YOUTUBE_ID_PATTERNS:
        match = pattern.search(url)
        if match:
            return match.group(1)
    return None


def is_supported_url(value: str) -> bool:
    return value.startswith("http://") or value.startswith("https://")


def search_query(title: str, artist: str | None) -> str:
    """Consulta para yt-dlp: pide el primer resultado de YouTube."""
    terms = " ".join(part.strip() for part in (artist, title) if part and part.strip())
    return f"ytsearch1:{terms}"


def _binary() -> str:
    path = shutil.which("yt-dlp")
    if path is None:  # pragma: no cover - solo si la imagen esta mal construida
        raise DownloadError("yt-dlp no esta instalado en el backend.")
    return path


def _base_args() -> list[str]:
    args = [
        _binary(),
        "--no-playlist",
        "--no-warnings",
        "--no-progress",
        "--socket-timeout",
        "15",
        "--retries",
        "3",
    ]
    if settings.ytdlp_cookies_file:
        args += ["--cookies", settings.ytdlp_cookies_file]
    return args


def _run(args: list[str]) -> str:
    try:
        completed = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=settings.download_timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise DownloadError("La descarga ha tardado demasiado y se ha cancelado.") from exc

    if completed.returncode != 0:
        raise DownloadError(_explain(completed.stderr))
    return completed.stdout


def _explain(stderr: str) -> str:
    """Traduce el ruido de yt-dlp a algo que el usuario pueda entender."""
    text = (stderr or "").strip()
    lowered = text.lower()
    if "private video" in lowered:
        return "El video es privado."
    if "video unavailable" in lowered or "has been removed" in lowered:
        return "El video ya no esta disponible."
    if "not available in your country" in lowered or "geo" in lowered and "block" in lowered:
        return "El video esta bloqueado geograficamente."
    if "sign in to confirm" in lowered or "bot" in lowered and "confirm" in lowered:
        return (
            "YouTube pide verificacion. Exporta las cookies del navegador y "
            "configura YTDLP_COOKIES_FILE."
        )
    if "unsupported url" in lowered:
        return "Esa URL no esta soportada."
    last_line = text.splitlines()[-1] if text else ""
    return last_line[:400] or "yt-dlp ha fallado sin dar detalles."


def _parse_info(payload: str) -> MediaInfo:
    line = next((ln for ln in payload.splitlines() if ln.strip().startswith("{")), None)
    if line is None:
        raise DownloadError("yt-dlp no ha devuelto informacion del video.")
    data = json.loads(line)

    if data.get("_type") == "playlist":  # ytsearch devuelve una lista
        entries = data.get("entries") or []
        if not entries:
            raise DownloadError("La busqueda no ha encontrado ningun resultado.")
        data = entries[0]

    duration = data.get("duration")

    # YouTube Music trae "track"/"artist" ya limpios; el resto de videos hay que
    # deducirlos del titulo, que suele venir como "Artista - Titulo (Official...)".
    track_name = (data.get("track") or "").strip()
    artist_name = (data.get("artist") or "").strip()
    if track_name and artist_name:
        title, artist = track_name, artist_name
    else:
        artist, title = split_artist_title(
            data.get("title") or "", data.get("uploader") or data.get("channel")
        )

    return MediaInfo(
        video_id=str(data.get("id") or ""),
        title=title or "Sin titulo",
        artist=artist or None,
        duration_seconds=int(duration) if duration else None,
        webpage_url=data.get("webpage_url") or data.get("original_url") or "",
        site=(data.get("extractor_key") or data.get("extractor") or "").lower()[:50],
    )


def resolve(query: str) -> MediaInfo:
    """Consulta metadatos sin descargar nada. Barato y sirve para deduplicar
    antes de gastar ancho de banda."""
    return _parse_info(_run(_base_args() + ["--dump-json", "--skip-download", query]))


def download(query: str, destination_dir: Path, video_id: str) -> Path:
    """Descarga el audio y lo deja como <destination_dir>/<video_id>.mp3.

    El nombre de fichero es el id del video, no el titulo: sin acentos, sin
    mayusculas ni caracteres raros, y sin dos canciones peleandose por el mismo
    nombre. El titulo bonito se aplica al descargar desde el frontend.
    """
    destination_dir.mkdir(parents=True, exist_ok=True)
    output_template = str(destination_dir / f"{video_id}.%(ext)s")

    _run(
        _base_args()
        + [
            "--extract-audio",
            "--audio-format",
            "mp3",
            "--audio-quality",
            settings.ytdlp_audio_quality,
            "--embed-metadata",
            "--output",
            output_template,
            query,
        ]
    )

    result = destination_dir / f"{video_id}.mp3"
    if not result.exists():
        raise DownloadError("La descarga termino pero no se encontro el mp3 resultante.")
    return result
