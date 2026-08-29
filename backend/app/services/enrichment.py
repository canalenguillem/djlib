"""Datos de artistas desde MusicBrainz y Wikipedia.

MusicBrainz aporta datos estructurados (pais, anos de actividad y, sobre todo,
relaciones entre artistas: "Robbie Williams fue miembro de Take That").
Wikipedia aporta la biografia en prosa. Se llega a ella a traves del enlace a
Wikidata que MusicBrainz ya guarda, que es mas fiable que buscar por nombre.

Igual que con yt-dlp, todo el trafico de red vive aqui para que los tests
puedan sustituir una sola funcion.
"""

from __future__ import annotations

import logging
import threading
import time
from urllib.parse import quote
from dataclasses import dataclass, field

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

# MusicBrainz pide como mucho una peticion por segundo y un User-Agent que
# identifique a la aplicacion. Incumplirlo lleva a bloqueo por IP.
_MB_MIN_INTERVAL = 1.1
_throttle_lock = threading.Lock()
_last_call = 0.0

RELATION_LABELS = {
    "member of band": "miembro de",
    "collaboration": "colaboracion",
    "founder": "fundador de",
    "supporting musician": "musico de apoyo",
    "conductor position": "director",
    "subgroup": "subgrupo de",
    "artistic director": "director artistico",
    "tribute": "tributo a",
    "voice actor": "voz de",
    "married": "casado con",
    "sibling": "hermano de",
    "parent": "familiar de",
    "teacher": "profesor de",
    "is person": "es",
    "involved with": "pareja de",
    "artist rename": "antes conocido como",
    "founder": "fundador de",
    "composer": "compositor de",
    "producer": "productor de",
}

# Que relaciones interesan primero: de donde sale el artista y con quien toca.
# "Robbie Williams -> miembro de Take That" es justo el caso del briefing.
_RELATION_PRIORITY = {
    "miembro de": 0,
    "miembros": 1,
    "fundador de": 2,
    "subgrupo de": 3,
    "antes conocido como": 4,
    "colaboracion": 5,
}


class EnrichmentError(RuntimeError):
    """Fallo consultando las fuentes externas. No es culpa del artista."""


@dataclass(frozen=True)
class RelationFact:
    name: str
    relation_type: str
    musicbrainz_id: str | None = None


@dataclass(frozen=True)
class ArtistFacts:
    name: str
    musicbrainz_id: str | None = None
    country: str | None = None
    begin_year: int | None = None
    end_year: int | None = None
    artist_type: str | None = None
    bio: str | None = None
    wikipedia_url: str | None = None
    relations: list[RelationFact] = field(default_factory=list)


def _throttle() -> None:
    global _last_call
    with _throttle_lock:
        wait = _MB_MIN_INTERVAL - (time.monotonic() - _last_call)
        if wait > 0:
            time.sleep(wait)
        _last_call = time.monotonic()


def _get_json(url: str, params: dict | None = None, *, throttle: bool = False) -> dict:
    """GET que devuelve JSON. Reintenta ante el 503 "servidor ocupado" que
    MusicBrainz devuelve a menudo, sobre todo en su buscador."""
    headers = {"User-Agent": settings.enrichment_user_agent, "Accept": "application/json"}
    last_error = ""

    for intento in range(3):
        if throttle:
            _throttle()
        try:
            response = httpx.get(
                url,
                params=params,
                headers=headers,
                timeout=settings.enrichment_timeout_seconds,
                follow_redirects=True,
            )
        except httpx.HTTPError as exc:
            last_error = f"no se pudo contactar ({exc})"
            time.sleep(1 + intento)
            continue

        if response.status_code == 404:
            return {}
        if response.status_code in (503, 502, 429):
            last_error = f"respondio {response.status_code}"
            time.sleep(1 + intento * 2)
            continue
        if response.status_code >= 400:
            raise EnrichmentError(f"{url} respondio {response.status_code}.")
        try:
            return response.json()
        except ValueError as exc:
            raise EnrichmentError(f"{url} no devolvio JSON valido.") from exc

    raise EnrichmentError(f"{url} {last_error} tras 3 intentos.")


def _year(value: str | None) -> int | None:
    if not value:
        return None
    try:
        return int(str(value)[:4])
    except ValueError:
        return None


def _search_musicbrainz(name: str) -> dict | None:
    data = _get_json(
        f"{settings.musicbrainz_base_url}/artist",
        {"query": f'artist:"{name}"', "fmt": "json", "limit": "5"},
        throttle=True,
    )
    candidates = data.get("artists") or []
    if not candidates:
        return None

    # La API devuelve una puntuacion de 0 a 100; por debajo de 80 suelen ser
    # coincidencias parciales de otro artista distinto.
    best = candidates[0]
    if int(best.get("score") or 0) < 80:
        lowered = name.strip().lower()
        exact = next((c for c in candidates if (c.get("name") or "").lower() == lowered), None)
        if exact is None:
            return None
        best = exact
    return best


def _artist_details(mbid: str) -> dict:
    return _get_json(
        f"{settings.musicbrainz_base_url}/artist/{mbid}",
        {"inc": "artist-rels url-rels", "fmt": "json"},
        throttle=True,
    )


def _relations_from(details: dict) -> tuple[list[RelationFact], str | None]:
    relations: list[RelationFact] = []
    wikidata_id: str | None = None
    seen: set[tuple[str, str]] = set()

    for relation in details.get("relations") or []:
        target = relation.get("target-type")
        kind = relation.get("type") or ""

        if target == "url":
            url = (relation.get("url") or {}).get("resource") or ""
            if kind == "wikidata" and "/wiki/" in url:
                wikidata_id = url.rsplit("/wiki/", 1)[-1]
            continue

        if target != "artist":
            continue
        related = relation.get("artist") or {}
        related_name = (related.get("name") or "").strip()
        if not related_name:
            continue
        label = RELATION_LABELS.get(kind, kind)
        if relation.get("direction") == "backward" and kind == "member of band":
            label = "miembros"  # la relacion inversa: la banda listando su gente
        key = (related_name.lower(), label)
        if key in seen:
            continue
        seen.add(key)
        relations.append(
            RelationFact(
                name=related_name, relation_type=label, musicbrainz_id=related.get("id")
            )
        )

    relations.sort(key=lambda r: (_RELATION_PRIORITY.get(r.relation_type, 90), r.name))
    return relations, wikidata_id


def _resolve_via_wikidata(name: str) -> tuple[str | None, str | None]:
    """Plan B cuando el buscador de MusicBrainz no esta disponible.

    Wikidata es mucho mas estable y guarda el identificador de MusicBrainz
    (propiedad P434) de casi cualquier artista. Que un candidato tenga ese
    campo es ademas una buena senal de que es un musico y no un homonimo.
    """
    candidates: list[str] = []
    for lang in (settings.wikipedia_lang, "en"):
        data = _get_json(
            "https://www.wikidata.org/w/api.php",
            {
                "action": "wbsearchentities",
                "search": name,
                "language": lang,
                "uselang": lang,
                "type": "item",
                "limit": "7",
                "format": "json",
            },
        )
        candidates = [hit["id"] for hit in data.get("search") or [] if hit.get("id")]
        if candidates:
            break
    if not candidates:
        return None, None

    entities = _get_json(
        "https://www.wikidata.org/w/api.php",
        {
            "action": "wbgetentities",
            "ids": "|".join(candidates),
            "props": "claims",
            "format": "json",
        },
    ).get("entities") or {}

    for qid in candidates:  # se respeta el orden de relevancia de la busqueda
        claims = (entities.get(qid) or {}).get("claims") or {}
        mb_claims = claims.get("P434") or []
        if not mb_claims:
            continue
        mbid = (
            ((mb_claims[0].get("mainsnak") or {}).get("datavalue") or {}).get("value")
        )
        if mbid:
            return mbid, qid
    return None, None


def _wikipedia_from_wikidata(wikidata_id: str) -> tuple[str | None, str | None]:
    """Devuelve (extracto, url) del articulo, prefiriendo el idioma configurado."""
    data = _get_json(
        "https://www.wikidata.org/w/api.php",
        {
            "action": "wbgetentities",
            "ids": wikidata_id,
            "props": "sitelinks",
            "format": "json",
        },
    )
    sitelinks = ((data.get("entities") or {}).get(wikidata_id) or {}).get("sitelinks") or {}

    for lang in (settings.wikipedia_lang, "en"):
        entry = sitelinks.get(f"{lang}wiki")
        if not entry:
            continue
        title = entry.get("title")
        if not title:
            continue
        summary = _get_json(
            f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/"
            f"{quote(title.replace(' ', '_'), safe='')}"
        )
        extract = (summary.get("extract") or "").strip()
        url = ((summary.get("content_urls") or {}).get("desktop") or {}).get("page")
        if extract:
            return extract, url
    return None, None


def lookup(name: str) -> ArtistFacts | None:
    """Busca al artista. Devuelve None si las fuentes no lo conocen.

    Primero el buscador de MusicBrainz; si esta caido o no da con el artista,
    se resuelve por Wikidata. Los datos siempre se leen del lookup directo por
    identificador, que es la parte fiable de la API.
    """
    mbid: str | None = None
    wikidata_id: str | None = None

    try:
        match = _search_musicbrainz(name)
        mbid = (match or {}).get("id")
    except EnrichmentError as exc:
        logger.info("Buscador de MusicBrainz no disponible (%s); se prueba Wikidata", exc)

    if mbid is None:
        mbid, wikidata_id = _resolve_via_wikidata(name)
    if mbid is None:
        return None

    details = _artist_details(mbid)
    if not details:
        return None

    relations, wikidata_from_mb = _relations_from(details)
    wikidata_id = wikidata_id or wikidata_from_mb
    life_span = details.get("life-span") or {}

    bio: str | None = None
    wikipedia_url: str | None = None
    if wikidata_id:
        bio, wikipedia_url = _wikipedia_from_wikidata(wikidata_id)
    # Sin articulo de Wikipedia, la coletilla de MusicBrainz ("UK alternative
    # rock band") es mejor que dejar la ficha en blanco.
    if not bio and details.get("disambiguation"):
        bio = details["disambiguation"]

    return ArtistFacts(
        name=details.get("name") or name,
        musicbrainz_id=mbid,
        country=details.get("country") or (details.get("area") or {}).get("name"),
        begin_year=_year(life_span.get("begin")),
        end_year=_year(life_span.get("end")),
        artist_type=details.get("type"),
        bio=bio,
        wikipedia_url=wikipedia_url,
        relations=relations,
    )
