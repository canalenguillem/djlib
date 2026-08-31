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
class SearchResult:
    """Un candidato del listado de YouTube, para que el usuario elija.

    Se queda con el titulo tal cual lo muestra YouTube (sin limpiar) porque es
    asi como el usuario reconoce el video que busca.
    """

    video_id: str
    title: str
    channel: str | None
    duration_seconds: int | None
    url: str
    thumbnail_url: str | None


@dataclass(frozen=True)
class ChannelInfo:
    """Quien subio el video. Para los mashups, edits y transiciones es la unica
    documentacion que existe del que los hizo: no estan en MusicBrainz ni en
    Wikipedia, pero su canal si esta ahi."""

    name: str
    url: str
    avatar_url: str | None
    description: str | None
    follower_count: int | None


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


def search_query(title: str | None, artist: str | None) -> str:
    """Consulta para yt-dlp. Se piden varios resultados, no uno: el primero
    suele ser un mix largo cuando la consulta no es exacta.

    Sin titulo se esta explorando a un artista, asi que se piden mas.
    """
    terms = " ".join(part.strip() for part in (artist, title) if part and part.strip())
    cuantos = (
        settings.search_candidates
        if (title or "").strip()
        else settings.search_artist_candidates
    )
    return f"ytsearch{cuantos}:{terms}"


def search_query_for_request(request_query: str) -> str:
    """Reproduce la busqueda tal y como la escribio el usuario.

    Se parte de lo que pidio y no del titulo del track, que para una busqueda
    solo por artista es el propio nombre del artista (y saldria repetido) y que
    ademas cambia en cuanto la primera resolucion lo sobrescribe.
    """
    return f"ytsearch{settings.search_candidates}:{request_query.strip()}"


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


def _candidates(payload: str) -> list[dict]:
    """yt-dlp escribe un objeto JSON POR LINEA, uno por video encontrado. Con
    --flat-playlist devuelve en cambio un unico objeto de tipo "playlist" con
    sus entradas dentro. Se admiten las dos formas."""
    found: list[dict] = []
    for line in payload.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        data = json.loads(line)
        if data.get("_type") == "playlist":
            found.extend(entry for entry in (data.get("entries") or []) if entry)
        else:
            found.append(data)
    return found


def _parse_info(payload: str) -> MediaInfo:
    found = _candidates(payload)
    if not found:
        raise DownloadError("La busqueda no ha encontrado ningun resultado.")

    # Una URL concreta devuelve un solo candidato y se respeta tal cual; solo
    # se elige cuando hay varios, es decir, cuando venimos de una busqueda.
    data = found[0] if len(found) == 1 else _pick_song(found)

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


def _pick_song(entries: list[dict]) -> dict:
    """Elige el primer resultado con duracion de cancion.

    Buscar "Bad Bunny Nueva Yirky" devuelve como primer resultado un mix de 42
    minutos: coger ciegamente el primero llena la biblioteca de recopilatorios.
    """
    limit = settings.max_song_duration_seconds
    for entry in entries:
        duration = entry.get("duration")
        if duration and duration <= limit:
            return entry

    duraciones = ", ".join(
        f"{int(e['duration']) // 60} min" for e in entries[:3] if e.get("duration")
    )
    raise DownloadError(
        "Todos los resultados son demasiado largos para ser una cancion"
        + (f" ({duraciones})" if duraciones else "")
        + ". Afina el titulo o pega la URL exacta del video."
    )


def _thumbnail(data: dict) -> str | None:
    """La miniatura mas grande que siga siendo razonable para un listado."""
    thumbnails = [t for t in (data.get("thumbnails") or []) if t.get("url")]
    if not thumbnails:
        return None
    utiles = [t for t in thumbnails if (t.get("width") or 0) <= 640]
    return (utiles or thumbnails)[-1]["url"]


def _video_url(data: dict) -> str:
    return (
        data.get("webpage_url")
        or data.get("url")
        or f"https://www.youtube.com/watch?v={data.get('id')}"
    )


def search(title: str | None, artist: str | None) -> list[SearchResult]:
    """Lista los candidatos de una busqueda sin descargar nada.

    Usa --flat-playlist: pedir los metadatos completos de cinco videos tarda
    unos diez segundos, mientras que el listado tarda menos de dos, y trae ya
    titulo, duracion, canal y miniatura, que es todo lo que hace falta para
    elegir.
    """
    payload = _run(
        _base_args() + ["--flat-playlist", "--dump-json", search_query(title, artist)]
    )
    resultados = []
    for data in _candidates(payload):
        video_id = str(data.get("id") or "")
        if not video_id:
            continue
        duration = data.get("duration")
        resultados.append(
            SearchResult(
                video_id=video_id,
                title=(data.get("title") or "").strip() or "Sin titulo",
                channel=(data.get("channel") or data.get("uploader") or None),
                duration_seconds=int(duration) if duration else None,
                url=_video_url(data),
                thumbnail_url=_thumbnail(data),
            )
        )
    return resultados


def _avatar(thumbnails: list[dict]) -> str | None:
    """El avatar es la miniatura cuadrada; las demas son el banner, que es
    ancho y no sirve como foto de ficha."""
    cuadradas = [
        t
        for t in thumbnails
        if t.get("url") and t.get("width") and t.get("height")
        and abs(int(t["width"]) - int(t["height"])) <= 2
    ]
    if not cuadradas:
        return None
    return max(cuadradas, key=lambda t: int(t["width"]))["url"]


def channel_info(video_url: str) -> ChannelInfo | None:
    """Datos del canal que subio un video: nombre, avatar y suscriptores."""
    datos = _candidates(_run(_base_args() + ["--dump-json", "--skip-download", video_url]))
    if not datos:
        return None
    video = datos[0]

    canal_url = video.get("channel_url") or video.get("uploader_url")
    nombre = (video.get("channel") or video.get("uploader") or "").strip()
    if not canal_url or not nombre:
        return None

    # El avatar y la descripcion no vienen en el JSON del video: hay que pedir
    # el canal. --playlist-items 0 trae solo su ficha, sin listar los videos.
    avatar = None
    descripcion = None
    seguidores = video.get("channel_follower_count")
    try:
        # -J (un unico objeto) y no --dump-json (una linea por video): lo que
        # interesa son los datos del canal, y con --playlist-items 0 no hay
        # ningun video que listar.
        salida = _run(
            _base_args()
            + ["-J", "--flat-playlist", "--playlist-items", "0", canal_url]
        )
        canal = json.loads(salida) if salida.strip() else {}
        avatar = _avatar(canal.get("thumbnails") or [])
        descripcion = (canal.get("description") or "").strip() or None
        seguidores = canal.get("channel_follower_count") or seguidores
    except (DownloadError, ValueError) as exc:
        logger.info("No se pudo leer el canal %s: %s", canal_url, exc)

    return ChannelInfo(
        name=nombre,
        url=video.get("uploader_url") or canal_url,
        avatar_url=avatar,
        description=descripcion,
        follower_count=int(seguidores) if seguidores else None,
    )


def resolve(query: str) -> MediaInfo:
    """Consulta metadatos sin descargar nada. Barato y sirve para deduplicar
    antes de gastar ancho de banda."""
    return _parse_info(_run(_base_args() + ["--dump-json", "--skip-download", query]))


# Extensiones que puede tener el flujo descargado, por orden de preferencia.
AUDIO_EXTENSIONS = ("m4a", "mp3", "opus", "webm", "ogg", "aac", "flac", "wav")


def find_audio_file(destination_dir: Path, video_id: str) -> Path | None:
    """El fichero se llama <video_id>.<lo que fuera>, porque la extension
    depende del flujo que sirva YouTube."""
    for extension in AUDIO_EXTENSIONS:
        candidato = destination_dir / f"{video_id}.{extension}"
        if candidato.exists():
            return candidato
    return next(iter(sorted(destination_dir.glob(f"{video_id}.*"))), None)


def download(query: str, destination_dir: Path, video_id: str) -> Path:
    """Descarga el audio a <destination_dir>/<video_id>.<ext>, sin recodificar.

    YouTube sirve como mucho unos 130 kbps con perdida; recodificar eso a mp3
    320 no anade informacion, anade una segunda perdida y triplica el tamano.
    Se guarda el flujo tal y como viene.

    El nombre de fichero es el id del video, no el titulo: sin acentos, sin
    caracteres raros y sin dos canciones peleandose por el mismo nombre. El
    titulo bonito se aplica al descargar desde el frontend.
    """
    destination_dir.mkdir(parents=True, exist_ok=True)

    _run(
        _base_args()
        + [
            "--format",
            settings.ytdlp_format,
            "--embed-metadata",
            "--output",
            str(destination_dir / f"{video_id}.%(ext)s"),
            query,
        ]
    )

    result = find_audio_file(destination_dir, video_id)
    if result is None:
        raise DownloadError("La descarga termino pero no se encontro el fichero de audio.")
    return result
