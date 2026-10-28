"""Top 100 de Beatport, general y por genero.

Beatport no tiene una API publica abierta, pero sus paginas traen el listado
entero en el JSON que Next.js deja en `__NEXT_DATA__`. Se lee de ahi, con
cache: el top cambia una vez al dia, no hace falta pedirlo en cada visita.

Si un dia cambian la pagina, falla con BeatportError y la pestaña lo dice; el
resto de la aplicacion no se entera.
"""

from __future__ import annotations

import json
import re
import threading
import time
from dataclasses import dataclass

import httpx

from app.core.config import settings

BASE = "https://www.beatport.com"
# Con el agente por defecto de httpx Beatport devuelve otra pagina
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0 Safari/537.36"
)
CACHE_SEGUNDOS = 3600
_NEXT_DATA = re.compile(
    r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', re.S
)

# (id, nombre, slug). Beatport no publica la lista; se saco recorriendo sus
# paginas de genero (octubre de 2026). Si aparece uno nuevo, se anade aqui.
GENEROS: list[tuple[int, str, str]] = [
    (106, "Latin", "latin"),
    (111, "Latin Electronic", "latin-electronic"),
    (107, "Pop", "pop"),
    (105, "Hip-Hop", "hip-hop"),
    (108, "R&B", "rb"),
    (39, "Dance / Pop", "dance-pop"),
    (5, "House", "house"),
    (11, "Tech House", "tech-house"),
    (12, "Deep House", "deep-house"),
    (81, "Funky House", "funky-house"),
    (97, "Jackin House", "jackin-house"),
    (50, "Nu Disco / Disco", "nu-disco-disco"),
    (89, "Afro House", "afro-house"),
    (93, "Organic House", "organic-house"),
    (15, "Progressive House", "progressive-house"),
    (90, "Melodic House & Techno", "melodic-house-techno"),
    (91, "Bass House", "bass-house"),
    (14, "Minimal / Deep Tech", "minimal-deep-tech"),
    (37, "Indie Dance", "indie-dance"),
    (112, "Indie Tech", "indie-tech"),
    (6, "Techno (Peak Time / Driving)", "techno-peak-time-driving"),
    (92, "Techno (Raw / Deep / Hypnotic)", "techno-raw-deep-hypnotic"),
    (2, "Hard Techno", "hard-techno"),
    (7, "Trance (Main Floor)", "trance-main-floor"),
    (99, "Trance (Raw / Deep / Hypnotic)", "trance-raw-deep-hypnotic"),
    (13, "Psy-Trance", "psy-trance"),
    (96, "Mainstage", "mainstage"),
    (85, "Bass / Club", "bass-club"),
    (86, "UK Garage / Bassline", "uk-garage-bassline"),
    (1, "Drum & Bass", "drum-bass"),
    (18, "Dubstep", "dubstep"),
    (95, "140 / Deep Dubstep / Grime", "140-deep-dubstep-grime"),
    (38, "Trap / Future Bass", "trap-future-bass"),
    (9, "Breaks / Breakbeat / UK Bass", "breaks-breakbeat-uk-bass"),
    (94, "Electro (Classic / Detroit / Modern)", "electro-classic-detroit-modern"),
    (8, "Hard Dance / Hardcore / Neo Rave", "hard-dance-hardcore-neo-rave"),
    (98, "Amapiano", "amapiano"),
    (101, "Brazilian Funk", "brazilian-funk"),
    (102, "African", "african"),
    (103, "Caribbean", "caribbean"),
    (3, "Electronica", "electronica"),
    (63, "Downtempo", "downtempo"),
    (100, "Ambient / Experimental", "ambient-experimental"),
    (16, "DJ Tools / Acapellas", "dj-tools-acapellas"),
    (104, "Country", "country"),
    (109, "Rock", "rock"),
]
_POR_ID = {g[0]: g for g in GENEROS}


class BeatportError(RuntimeError):
    pass


@dataclass(frozen=True)
class BeatportTrack:
    position: int
    title: str
    mix: str | None
    artist: str
    remixers: str | None
    bpm: int | None
    key: str | None
    genre: str | None
    label: str | None
    length: str | None
    release_date: str | None
    image_url: str | None
    sample_url: str | None
    beatport_url: str


_cache: dict[int | None, tuple[float, list[BeatportTrack]]] = {}
_cache_lock = threading.Lock()


def _url(genero: int | None) -> str:
    if genero is None:
        return f"{BASE}/top-100"
    _, _, slug = _POR_ID[genero]
    return f"{BASE}/genre/{slug}/{genero}/top-100"


def _nombres(lista: list[dict] | None) -> str:
    return ", ".join(a["name"] for a in (lista or []) if a.get("name"))


def _imagen(datos: dict | None, lado: int = 250) -> str | None:
    dinamica = (datos or {}).get("dynamic_uri")
    if dinamica:
        return dinamica.replace("{w}", str(lado)).replace("{h}", str(lado))
    return (datos or {}).get("uri")


def _pista(posicion: int, t: dict) -> BeatportTrack:
    clave = t.get("key") or {}
    camelot = (
        f"{clave['camelot_number']}{clave['camelot_letter']}"
        if clave.get("camelot_number") and clave.get("camelot_letter")
        else None
    )
    release = t.get("release") or {}
    mezcla = (t.get("mix_name") or "").strip() or None
    return BeatportTrack(
        position=posicion,
        title=(t.get("name") or "").strip(),
        mix=mezcla,
        artist=_nombres(t.get("artists")),
        remixers=_nombres(t.get("remixers")) or None,
        bpm=t.get("bpm"),
        key=f"{camelot} · {clave['name']}" if camelot and clave.get("name") else camelot,
        genre=(t.get("genre") or {}).get("name"),
        label=(release.get("label") or {}).get("name"),
        length=t.get("length"),
        release_date=t.get("publish_date"),
        image_url=_imagen(release.get("image")),
        sample_url=t.get("sample_url"),
        beatport_url=f"{BASE}/track/{t.get('slug') or 'track'}/{t.get('id')}",
    )


def parse(html: str) -> list[BeatportTrack]:
    m = _NEXT_DATA.search(html)
    if not m:
        raise BeatportError("Beatport ha cambiado su pagina: no se encuentra el listado.")
    try:
        consultas = json.loads(m.group(1))["props"]["pageProps"]["dehydratedState"]["queries"]
    except (ValueError, KeyError, TypeError) as exc:
        raise BeatportError("Beatport ha cambiado su pagina: no se entiende el listado.") from exc
    for consulta in consultas:
        clave = consulta.get("queryKey") or [""]
        datos = (consulta.get("state") or {}).get("data")
        if "top-100-tracks" in str(clave[0]) and isinstance(datos, dict):
            return [_pista(i, t) for i, t in enumerate(datos.get("results") or [], start=1)]
    raise BeatportError("Beatport ha cambiado su pagina: no se encuentra el top 100.")


def top100(genero: int | None = None) -> list[BeatportTrack]:
    """El top 100, general o de un genero. LookupError si el genero no existe."""
    if genero is not None and genero not in _POR_ID:
        raise LookupError("Ese genero no existe en Beatport.")
    with _cache_lock:
        guardado = _cache.get(genero)
        if guardado and time.monotonic() - guardado[0] < CACHE_SEGUNDOS:
            return guardado[1]
    try:
        respuesta = httpx.get(
            _url(genero),
            headers={"User-Agent": USER_AGENT, "Accept-Language": "en"},
            follow_redirects=True,
            timeout=settings.spotify_timeout_seconds,
        )
        respuesta.raise_for_status()
    except httpx.HTTPError as exc:
        raise BeatportError("No se pudo consultar Beatport. Prueba dentro de un rato.") from exc
    pistas = parse(respuesta.text)
    with _cache_lock:
        _cache[genero] = (time.monotonic(), pistas)
    return pistas
