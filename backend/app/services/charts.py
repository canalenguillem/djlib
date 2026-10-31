"""Varios tops cruzados en una sola lista.

Para saber que pide la gente hay que mirar mas de un sitio: Beatport dice que
suena en las cabinas y Deezer que escucha el publico de cada pais. Aqui se
juntan, sin repetir.

Lo que mas interesa es lo que esta en los dos lados a la vez: lo conoce el
publico y ademas suena en cabina. Eso va primero. Despues, cada lado pesa lo
mismo: los tops de Deezer se parecen mucho entre paises y los generos de
Beatport casi no comparten temas, asi que si cada lista sumara por su cuenta,
marcar cuatro paises enterraria todo lo de Beatport.
"""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

from app.core.text import normalize_key
from app.services import beatport, deezer

# Mas no aporta y tarda: cada lista nueva es una consulta a otro sitio
MAX_FUENTES = 12
# Lo que suma estar en otra lista del mismo lado: desempata, no manda
EXTRA_POR_LISTA = 0.05


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
    # Lo que vale, segun en cuantas listas de cada lado esta y en que puesto
    score: float = 0.0

    @property
    def grupos(self) -> list[str]:
        """Los lados en los que esta ("Beatport", "Deezer")."""
        return sorted({_grupo(f) for f, _ in self.posiciones})


def _grupo(fuente: str) -> str:
    return "Beatport" if fuente.startswith("beatport:") else "Deezer"


def fuentes() -> list[Fuente]:
    lista = [Fuente(f"deezer:{clave}", f"Top {nombre}", "Deezer") for clave, nombre, _ in deezer.TOPS]
    # Se ven aparte, pero cuentan como Deezer: lo que escucha el publico
    lista += [Fuente(f"deezer:{clave}", nombre, "Reggaeton") for clave, nombre, _ in deezer.REGGAETON]
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

    for c in por_clave.values():
        # Un numero 1 vale 1; un 100, casi nada. De cada lado cuenta el mejor
        # puesto, y cada lista mas de ese lado anade un poco: asi el 1 de Afro
        # House y el 1 de tres paises quedan a la par
        puestos: dict[str, list[int]] = {}
        for fuente, posicion in c.posiciones:
            puestos.setdefault(_grupo(fuente), []).append(posicion)
        c.score = sum(
            (101 - min(lista)) / 100 + EXTRA_POR_LISTA * (len(lista) - 1)
            for lista in puestos.values()
        )
    return sorted(
        por_clave.values(),
        key=lambda c: (-len(c.grupos), -c.score, min(p for _, p in c.posiciones)),
    )
