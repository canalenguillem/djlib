"""Cliente de Spotify.

Dos niveles de acceso, con usos distintos:

- **Credenciales de aplicacion**: sirven para consultar el catalogo publico, y
  con eso se sacan los generos de un artista. No hace falta que nadie inicie
  sesion.
- **Autorizacion del usuario**: hace falta para leer lo que ha escuchado, que es
  informacion suya. Se guarda el refresh token para no volver a pedirle permiso.

Nota sobre lo que NO se puede: `audio-features` (danceability, energy, tempo)
quedo restringido para las apps registradas desde noviembre de 2024, asi que el
tempo lo seguimos midiendo nosotros con soundstretch.
"""

from __future__ import annotations

import base64
import logging
import secrets
import threading
import time
from dataclasses import dataclass
from datetime import timedelta
from urllib.parse import urlencode

import httpx

from app.core.config import settings
from app.core.time import utcnow

logger = logging.getLogger(__name__)

CUENTAS = "https://accounts.spotify.com"
API = "https://api.spotify.com/v1"

# Lo minimo para leer lo escuchado. Cuantos menos permisos se pidan, menos
# reparos al autorizar.
SCOPES = "user-read-recently-played user-top-read"


class SpotifyError(RuntimeError):
    pass


class SpotifyNotConfigured(SpotifyError):
    pass


@dataclass(frozen=True)
class Tokens:
    access_token: str
    refresh_token: str | None
    expires_in: int
    scope: str | None


@dataclass(frozen=True)
class PlayedTrack:
    title: str
    artist: str
    album: str | None
    played_at: str | None
    spotify_url: str | None
    image_url: str | None

    @property
    def search_terms(self) -> str:
        return f"{self.artist} {self.title}".strip()


def is_enabled() -> bool:
    return bool(
        settings.spotify_client_id
        and settings.spotify_client_secret
        and settings.spotify_redirect_uri
    )


def _check() -> None:
    if not is_enabled():
        raise SpotifyNotConfigured(
            "Spotify no esta configurado. Faltan SPOTIFY_CLIENT_ID, "
            "SPOTIFY_CLIENT_SECRET o SPOTIFY_REDIRECT_URI."
        )


def _basic() -> str:
    par = f"{settings.spotify_client_id}:{settings.spotify_client_secret}"
    return base64.b64encode(par.encode()).decode()


def _post_token(datos: dict) -> dict:
    try:
        respuesta = httpx.post(
            f"{CUENTAS}/api/token",
            data=datos,
            headers={"Authorization": f"Basic {_basic()}"},
            timeout=settings.spotify_timeout_seconds,
        )
    except httpx.HTTPError as exc:
        raise SpotifyError(f"No se pudo contactar con Spotify: {exc}") from exc

    payload = respuesta.json() if respuesta.content else {}
    if respuesta.status_code >= 400:
        descripcion = payload.get("error_description") or payload.get("error") or ""
        if respuesta.status_code == 400 and "redirect_uri" in str(descripcion):
            raise SpotifyError(
                "Spotify rechaza la redirect URI. Tiene que estar registrada en el "
                "panel de la app exactamente igual que SPOTIFY_REDIRECT_URI."
            )
        raise SpotifyError(f"Spotify ha devuelto un error: {descripcion or respuesta.status_code}")
    return payload


# --- Autorizacion del usuario -----------------------------------------------


def authorize_url(state: str) -> str:
    _check()
    parametros = {
        "client_id": settings.spotify_client_id,
        "response_type": "code",
        "redirect_uri": settings.spotify_redirect_uri,
        "scope": SCOPES,
        "state": state,
        # Fuerza la pantalla de permisos: si no, reconectar no hace nada visible
        "show_dialog": "true",
    }
    return f"{CUENTAS}/authorize?{urlencode(parametros)}"


def exchange_code(code: str) -> Tokens:
    _check()
    payload = _post_token(
        {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": settings.spotify_redirect_uri,
        }
    )
    return Tokens(
        access_token=payload["access_token"],
        refresh_token=payload.get("refresh_token"),
        expires_in=int(payload.get("expires_in") or 3600),
        scope=payload.get("scope"),
    )


def refresh_tokens(refresh_token: str) -> Tokens:
    _check()
    payload = _post_token({"grant_type": "refresh_token", "refresh_token": refresh_token})
    return Tokens(
        access_token=payload["access_token"],
        # Spotify no siempre devuelve uno nuevo: se conserva el que ya habia
        refresh_token=payload.get("refresh_token") or refresh_token,
        expires_in=int(payload.get("expires_in") or 3600),
        scope=payload.get("scope"),
    )


def expires_at(expires_in: int):
    return utcnow() + timedelta(seconds=expires_in)


# --- Credenciales de aplicacion ---------------------------------------------

_app_token: tuple[str, float] | None = None
_app_lock = threading.Lock()


def app_token() -> str:
    """Token de aplicacion, cacheado hasta que caduca."""
    global _app_token
    _check()
    with _app_lock:
        if _app_token and _app_token[1] > time.monotonic() + 60:
            return _app_token[0]
        payload = _post_token({"grant_type": "client_credentials"})
        token = payload["access_token"]
        _app_token = (token, time.monotonic() + int(payload.get("expires_in") or 3600))
        return token


# --- Llamadas a la API ------------------------------------------------------


def _get(ruta: str, token: str, params: dict | None = None) -> dict:
    try:
        respuesta = httpx.get(
            f"{API}{ruta}",
            headers={"Authorization": f"Bearer {token}"},
            params=params,
            timeout=settings.spotify_timeout_seconds,
        )
    except httpx.HTTPError as exc:
        raise SpotifyError(f"No se pudo contactar con Spotify: {exc}") from exc

    if respuesta.status_code == 401:
        raise SpotifyError("El permiso de Spotify ha caducado. Vuelve a conectar la cuenta.")
    if respuesta.status_code == 403:
        raise SpotifyError(
            "Spotify ha denegado el acceso. Puede que el permiso pedido no este "
            "concedido para esta cuenta."
        )
    if respuesta.status_code == 429:
        raise SpotifyError("Spotify esta limitando las peticiones. Prueba en un minuto.")
    if respuesta.status_code >= 400:
        raise SpotifyError(f"Spotify ha devuelto un error ({respuesta.status_code}).")
    return respuesta.json() if respuesta.content else {}


def _artistas(item: dict) -> str:
    nombres = [a.get("name") for a in (item.get("artists") or []) if a.get("name")]
    return ", ".join(nombres)


def _portada(item: dict) -> str | None:
    imagenes = ((item.get("album") or {}).get("images") or [])
    if not imagenes:
        return None
    # La mas pequena vale: es para una lista, no para una portada grande
    return min(imagenes, key=lambda i: i.get("width") or 999)["url"]


def recently_played(token: str, limit: int | None = None) -> list[PlayedTrack]:
    """Lo ultimo que ha sonado en la cuenta, de mas reciente a mas antiguo."""
    datos = _get(
        "/me/player/recently-played",
        token,
        {"limit": min(limit or settings.spotify_recent_limit, 50)},
    )
    canciones: list[PlayedTrack] = []
    vistas: set[str] = set()
    for entrada in datos.get("items") or []:
        pista = entrada.get("track") or {}
        titulo = (pista.get("name") or "").strip()
        if not titulo:
            continue
        artista = _artistas(pista)
        # La misma cancion puede aparecer varias veces si se ha repetido
        clave = f"{artista.lower()}|{titulo.lower()}"
        if clave in vistas:
            continue
        vistas.add(clave)
        canciones.append(
            PlayedTrack(
                title=titulo,
                artist=artista,
                album=(pista.get("album") or {}).get("name"),
                played_at=entrada.get("played_at"),
                spotify_url=(pista.get("external_urls") or {}).get("spotify"),
                image_url=_portada(pista),
            )
        )
    return canciones


def artist_genres(nombre: str) -> list[str]:
    """Generos de un artista, buscandolo por nombre.

    Usa credenciales de aplicacion: no hace falta que nadie haya conectado su
    cuenta. Cubre a los artistas urbanos recientes que MusicBrainz no tiene.
    """
    datos = _get("/search", app_token(), {"q": nombre, "type": "artist", "limit": 5})
    candidatos = ((datos.get("artists") or {}).get("items") or [])
    if not candidatos:
        return []

    buscado = nombre.strip().lower()
    exacto = next((c for c in candidatos if (c.get("name") or "").lower() == buscado), None)
    elegido = exacto or candidatos[0]
    # Sin coincidencia exacta solo se acepta al primero si Spotify lo considera
    # muy popular; si no, es facil acabar etiquetando con el artista equivocado.
    if exacto is None and (elegido.get("popularity") or 0) < 50:
        return []
    return [g.strip().lower() for g in (elegido.get("genres") or []) if g.strip()]


# --- Estados de la autorizacion ---------------------------------------------

_estados: dict[str, tuple[int, float]] = {}
_estados_lock = threading.Lock()
_ESTADO_TTL = 600


def crear_estado(user_id: int) -> str:
    """El `state` de OAuth ata la vuelta de Spotify al usuario que la pidio.

    Hace falta porque el navegador vuelve del callback sin cabecera de
    autenticacion: es una redireccion, no una llamada de la aplicacion.
    """
    valor = secrets.token_urlsafe(24)
    ahora = time.monotonic()
    with _estados_lock:
        caducados = [k for k, (_, t) in _estados.items() if ahora - t > _ESTADO_TTL]
        for k in caducados:
            _estados.pop(k, None)
        _estados[valor] = (user_id, ahora)
    return valor


def consumir_estado(valor: str) -> int | None:
    """Devuelve el usuario y lo invalida: un estado sirve una sola vez."""
    with _estados_lock:
        entrada = _estados.pop(valor, None)
    if entrada is None:
        return None
    user_id, creado = entrada
    if time.monotonic() - creado > _ESTADO_TTL:
        return None
    return user_id
