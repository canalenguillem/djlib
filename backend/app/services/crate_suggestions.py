"""A que crate podria ir una cancion.

Se compara con lo que ya hay en cada crate: si comparten artista, si el BPM y
la energia se parecen, si llevan las mismas etiquetas y si el nombre del crate
encaja con la cancion (un crate "Mashups" para un mashup, "Bad Gyal" para un
tema suyo). Cada coincidencia suma puntos y deja un motivo, que es lo que ve
el usuario: una sugerencia sin explicacion no se sabe si fiarse de ella.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from statistics import median

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.text import _strip_accents
from app.models.crate import Crate, CrateTrack
from app.models.track import Track

MAX_SUGERENCIAS = 3
MIN_PUNTOS = 3

_SEPARA = re.compile(r"\s*(?:,|&|\bx\b|\bfeat\b\.?|\bft\b\.?|\bvs\b\.?|\by\b|\bwith\b)\s*", re.I)
# Palabras del nombre de un crate que hablan del tipo de version
_VERSIONES = ("mashup", "remix", "extended", "edit", "bootleg", "acapella", "intro")


def _limpio(texto: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", _strip_accents(texto).lower()).strip()


def _artistas(track: Track) -> set[str]:
    nombres = {a.name for a in track.artists}
    if track.artist_text:
        nombres.update(_SEPARA.split(track.artist_text))
    # "Song (feat. Otro)": tambien cuenta
    for m in re.finditer(r"\((?:feat|ft)\.?\s+([^)]+)\)", track.title, re.I):
        nombres.update(_SEPARA.split(m.group(1)))
    return {n for n in (_limpio(x) for x in nombres) if len(n) > 1}


def _bpm_parecido(a: float, b: float) -> float:
    """Diferencia de BPM contando que 64 y 128 se mezclan igual."""
    return min(abs(a - b), abs(a * 2 - b), abs(a - b * 2))


@dataclass
class Sugerencia:
    crate: Crate
    puntos: float = 0.0
    motivos: list[str] = field(default_factory=list)


def suggest(db: Session, track: Track) -> list[Sugerencia]:
    ya_esta = set(track.crate_ids)
    if track.pending_crate_id:
        ya_esta.add(track.pending_crate_id)
    crates = db.scalars(
        select(Crate).options(
            selectinload(Crate.entries).selectinload(CrateTrack.track)
        )
    ).all()

    mios = _artistas(track)
    mis_tags = {t.name.lower(): t.name for t in track.tags}
    titulo = _limpio(f"{track.artist_text or ''} {track.title}")
    sugerencias = []

    for crate in crates:
        if crate.id in ya_esta:
            continue
        otras = [e.track for e in crate.entries if e.track.id != track.id]
        s = Sugerencia(crate)
        nombre = _limpio(crate.name)

        # Mismo artista que canciones del crate
        compartidos: dict[str, int] = {}
        for otra in otras:
            suyos = _artistas(otra)
            # Tambien si el nombre sale en el titulo: en YouTube muchas veces
            # el artista va ahi ("Titi Me Pregunto - Bad Bunny // DJ Sanchez")
            en_titulo = {a for a in suyos if len(a) >= 4 and re.search(rf"\b{re.escape(a)}\b", titulo)}
            for a in (mios & suyos) | en_titulo:
                compartidos[a] = compartidos.get(a, 0) + 1
        if compartidos:
            s.puntos += min(3 + sum(compartidos.values()) * 0.5, 6)
            nombres = sorted(compartidos, key=compartidos.get, reverse=True)[:2]
            s.motivos.append(f"tiene más de {', '.join(n.title() for n in nombres)}")

        # El nombre del crate es un artista suyo o el tipo de version
        if any(re.search(rf"\b{re.escape(a)}\b", nombre) for a in mios):
            s.puntos += 4
            s.motivos.append("el crate lleva el nombre del artista")
        for v in _VERSIONES:
            if re.search(rf"\b{v}", nombre) and re.search(rf"\b{v}", titulo):
                s.puntos += 3
                s.motivos.append(f"es un {v}")
                break

        # BPM: cerca de lo que suele haber en el crate
        bpms = [o.bpm for o in otras if o.bpm]
        if track.bpm and len(bpms) >= 2:
            centro = median(bpms)
            dif = _bpm_parecido(track.bpm, centro)
            if dif <= 3:
                s.puntos += 2
                s.motivos.append(f"BPM como el del crate (~{round(centro)})")
            elif dif <= 6:
                s.puntos += 1
                s.motivos.append(f"BPM cercano (~{round(centro)})")
            elif dif > 15:
                s.puntos -= 2

        # Energia parecida
        energias = [o.energy for o in otras if o.energy]
        if track.energy and len(energias) >= 2 and abs(track.energy - median(energias)) <= 1:
            s.puntos += 1
            s.motivos.append("energía parecida")

        # Etiquetas en comun
        if mis_tags and otras:
            cuenta: dict[str, int] = {}
            for otra in otras:
                for t in otra.tags:
                    if t.name.lower() in mis_tags:
                        cuenta[t.name.lower()] = cuenta.get(t.name.lower(), 0) + 1
            frecuentes = [mis_tags[t] for t, n in cuenta.items() if n / len(otras) >= 0.25]
            if frecuentes:
                s.puntos += min(len(frecuentes) * 1.5, 3)
                s.motivos.append(f"etiquetas: {', '.join(frecuentes[:3])}")

        # Solo por el BPM no basta: casi cualquier crate tiene uno parecido
        if s.puntos >= MIN_PUNTOS and s.motivos:
            sugerencias.append(s)

    sugerencias.sort(key=lambda s: -s.puntos)
    return sugerencias[:MAX_SUGERENCIAS]
