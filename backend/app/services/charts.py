"""Varios tops cruzados en una sola lista.

Para saber que pide la gente hay que mirar mas de un sitio: Beatport dice que
suena en las cabinas y Deezer que escucha el publico de cada pais. Aqui se
juntan, sin repetir, y sale antes lo que esta en mas listas y mas arriba.
"""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

from app.core.text import normalize_key
from app.services import beatport, deezer

# Mas no aporta y tarda: cada lista nueva es una consulta a otro sitio
MAX_FUENTES = 12


class ChartError(RuntimeError):
    pass


@dataclass(frozen=True)
class Fuente:
    id: str
    name: str
    group: str


@dataclass(frozen=True)
class Entrada:
    """Una cancion de una lista, con lo que tengan en comun Beatport y Deezer."""

    position: int
    name: str
    mix: str | None
    artist: str
    bpm: int | None = None
    key: str | None = None
    duration_seconds: int | None = None
    image_url: str | None = None
    sample_url: str | None = None
    url: str | None = None


@dataclass
class Combinada:
    entrada: Entrada
    # (id de la fuente, posicion en ella)
    posiciones: list[tuple[str, int]] = field(default_factory=list)
    # Todas las formas en que viene escrita, para buscarla en la biblioteca
    claves: set[str] = field(default_factory=set)

    @property
    def score(self) -> float:
        # Un numero 1 vale 1; un 100, casi nada. Sumado entre listas: estar en
        # tres a media tabla pesa mas que ser el 1 de una sola
        return sum((101 - posicion) / 100 for _, posicion in self.posiciones)


def fuentes() -> list[Fuente]:
    lista = [Fuente(f"deezer:{clave}", f"Top {nombre}", "Deezer") for clave, nombre, _ in deezer.TOPS]
    lista.append(Fuente("beatport:top", "Top 100 general", "Beatport"))
    lista += [Fuente(f"beatport:{i}", nombre, "Beatport") for i, nombre, _ in beatport.GENEROS]
    return lista


def _leer(fuente: str) -> list[Entrada]:
    tipo, _, valor = fuente.partition(":")
    if tipo == "deezer":
        return [
            Entrada(
                position=p.position,
                name=p.title,
                mix=None,
                artist=p.artist,
                duration_seconds=p.duration_seconds,
                image_url=p.image_url,
                sample_url=p.sample_url,
                url=p.deezer_url,
            )
            for p in deezer.top(valor)
        ]
    if tipo == "beatport":
        genero = None if valor == "top" else int(valor) if valor.isdigit() else -1
        return [
            Entrada(
                position=p.position,
                name=p.title,
                mix=p.mix,
                artist=p.artist,
                bpm=p.bpm,
                key=p.key,
                image_url=p.image_url,
                sample_url=p.sample_url,
                url=p.beatport_url,
            )
            for p in beatport.top100(genero)
        ]
    raise LookupError("Esa lista no existe.")


_SEPARA_ARTISTAS = re.compile(r"\s*(?:,|&|\bfeat\b\.?|\bft\b\.?|\bx\b|\bwith\b)\s*", re.I)


def _clave(entrada: Entrada) -> str:
    # Beatport pone a todos ("Kettama, Prospa") y Deezer solo al principal:
    # con el primero basta para saber que es la misma
    primero = _SEPARA_ARTISTAS.split(entrada.artist, maxsplit=1)[0] or entrada.artist
    return normalize_key(primero, entrada.name)


def leer(ids: list[str]) -> tuple[dict[str, list[Entrada]], dict[str, str]]:
    """Las listas pedidas, en paralelo. Una que falle no tumba las demas: va
    en el segundo diccionario con el motivo."""
    conocidas = {f.id for f in fuentes()}
    pedidas = list(dict.fromkeys(ids))
    if not pedidas:
        raise ChartError("Elige al menos una lista.")
    if len(pedidas) > MAX_FUENTES:
        raise ChartError(f"Como mucho {MAX_FUENTES} listas a la vez.")
    desconocidas = [i for i in pedidas if i not in conocidas]
    if desconocidas:
        raise ChartError(f"No existe la lista {desconocidas[0]}.")

    listas: dict[str, list[Entrada]] = {}
    errores: dict[str, str] = {}

    def una(fuente: str) -> None:
        try:
            listas[fuente] = _leer(fuente)
        except (beatport.BeatportError, deezer.DeezerError, LookupError) as exc:
            errores[fuente] = str(exc)

    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(una, pedidas))
    return listas, errores


def combinar(listas: dict[str, list[Entrada]], orden: list[str]) -> list[Combinada]:
    """Junta las listas sin repetir. De cada cancion se queda con la primera
    version que encuentra, y Beatport va antes: su version es la de DJ
    ("Extended Mix"), que es la que conviene buscar."""
    primero_beatport = sorted(orden, key=lambda f: not f.startswith("beatport:"))
    por_clave: dict[str, Combinada] = {}
    for fuente in primero_beatport:
        for entrada in listas.get(fuente, []):
            clave = _clave(entrada)
            combinada = por_clave.setdefault(clave, Combinada(entrada))
            combinada.posiciones.append((fuente, entrada.position))
            combinada.claves.add(normalize_key(entrada.artist, entrada.name))
    return sorted(
        por_clave.values(),
        key=lambda c: (-c.score, min(p for _, p in c.posiciones)),
    )
