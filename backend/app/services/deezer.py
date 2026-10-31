"""Tops por pais y listas de genero de Deezer.

Spotify ya no deja leer sus listas editoriales (Top 50 España y compañia) a
aplicaciones como esta, pero Deezer publica las suyas en una API abierta, sin
cuenta ni clave: las de la cuenta "Deezer Charts", que se actualizan a diario.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass

import httpx

from app.core.config import settings

API = "https://api.deezer.com"
CACHE_SEGUNDOS = 3600

# (clave, nombre, id de la lista). Los paises de los que viene la gente que
# sale de fiesta en Mallorca. Para otro, se busca "Top <Pais> 100" de la
# cuenta "Deezer Charts" y se anade aqui.
TOPS: list[tuple[str, str, int]] = [
    ("es", "España", 1116190041),
    ("world", "Mundo", 3155776842),
    ("uk", "Reino Unido", 1111142221),
    ("de", "Alemania", 1111143121),
    ("fr", "Francia", 1109890291),
    ("it", "Italia", 1116187241),
    ("nl", "Países Bajos", 1266971851),
]

# (clave, nombre, id de la lista). Las de reggaeton de los editores latinos de
# Deezer ("Camojada - Deezer Latin Editor"): Beatport no tiene reggaeton y en
# los tops de pais va mezclado con todo lo demas.
REGGAETON: list[tuple[str, str, int]] = [
    ("perreo", "Club Perreo", 10777825362),
    ("reggaeton-hits", "Reggaeton Hits", 1273315391),
    ("fuego-latino", "Fuego Latino", 178699142),
    ("new-reggaeton", "New Reggaeton", 11120289724),
    ("reggaeton-classics", "Reggaeton Classics", 789123393),
    ("bombon", "Bombón", 10759132562),
    ("sol-y-playa", "Sol y Playa", 254227453),
]
_POR_CLAVE = {clave: (nombre, lista) for clave, nombre, lista in TOPS + REGGAETON}


class DeezerError(RuntimeError):
    pass


@dataclass(frozen=True)
class DeezerTrack:
    position: int
    title: str
    artist: str
    duration_seconds: int | None
    image_url: str | None
    sample_url: str | None
    deezer_url: str


_cache: dict[str, tuple[float, list[DeezerTrack]]] = {}
_cache_lock = threading.Lock()


def _pista(posicion: int, t: dict) -> DeezerTrack:
    return DeezerTrack(
        position=posicion,
        title=(t.get("title") or "").strip(),
        artist=((t.get("artist") or {}).get("name") or "").strip(),
        duration_seconds=t.get("duration") or None,
        image_url=(t.get("album") or {}).get("cover_medium"),
        sample_url=t.get("preview") or None,
        deezer_url=t.get("link") or f"https://www.deezer.com/track/{t.get('id')}",
    )


def parse(datos: dict) -> list[DeezerTrack]:
    # Deezer contesta 200 con {"error": ...} cuando algo va mal
    if "error" in datos:
        raise DeezerError("Deezer no ha devuelto la lista.")
    pistas = ((datos.get("tracks") or {}).get("data")) or []
    return [_pista(i, t) for i, t in enumerate(pistas, start=1)]


def top(pais: str) -> list[DeezerTrack]:
    """Las 100 primeras de un top de pais o de una lista de REGGAETON.
    LookupError si no esta en ninguna de las dos."""
    if pais not in _POR_CLAVE:
        raise LookupError("Esa lista no existe en Deezer.")
    with _cache_lock:
        guardado = _cache.get(pais)
        if guardado and time.monotonic() - guardado[0] < CACHE_SEGUNDOS:
            return guardado[1]
    try:
        respuesta = httpx.get(
            f"{API}/playlist/{_POR_CLAVE[pais][1]}",
            params={"limit": 100},
            timeout=settings.spotify_timeout_seconds,
        )
        respuesta.raise_for_status()
        datos = respuesta.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise DeezerError("No se pudo consultar Deezer. Prueba dentro de un rato.") from exc
    pistas = parse(datos)
    with _cache_lock:
        _cache[pais] = (time.monotonic(), pistas)
    return pistas
