"""Lectura de capturas de pantalla con un modelo de vision.

El caso de uso: Shazam va identificando canciones solo durante la noche; al dia
siguiente se hace una captura de la lista y se sube aqui. El modelo extrae los
titulos y artistas, y de ahi entran por la misma tuberia de descarga que todo
lo demas.

Funciona con cualquier captura donde se lean canciones, no solo con Shazam:
la pantalla de un reproductor, una lista de Spotify, la foto de un cartel.
"""

from __future__ import annotations

import base64
import json
import logging
from dataclasses import dataclass

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

OPENAI_ENDPOINT = "https://api.openai.com/v1/chat/completions"

INSTRUCCIONES = """Eres un extractor de canciones a partir de capturas de pantalla.

Devuelve EXCLUSIVAMENTE un objeto JSON con esta forma:
{"songs": [{"title": "...", "artist": "..."}]}

Reglas:
- Incluye todas las canciones que se lean en la imagen, en el mismo orden en
  que aparecen de arriba abajo.
- "title" es el nombre de la cancion y "artist" el interprete. Si el artista no
  se lee, deja "artist" como cadena vacia.
- No inventes canciones que no esten en la imagen, ni completes datos que no
  se vean.
- Ignora todo lo que sea interfaz: horas, fechas, botones, nombres de la app,
  numero de reproducciones, etiquetas como "Shazams recientes".
- Si en la imagen no hay ninguna cancion, devuelve {"songs": []}.
"""


class ScreenshotError(RuntimeError):
    """Fallo al leer la captura: red, cuota o configuracion."""


class ScreenshotNotConfigured(ScreenshotError):
    pass


@dataclass(frozen=True)
class DetectedSong:
    title: str
    artist: str | None


def is_enabled() -> bool:
    return bool(settings.openai_api_key)


def _mensaje_error(payload: dict, status_code: int) -> str:
    error = (payload or {}).get("error") or {}
    codigo = error.get("code") or ""
    mensaje = error.get("message") or ""

    if status_code == 401:
        return "La clave de OpenAI no es valida. Revisa OPENAI_API_KEY."
    if status_code == 429 or codigo == "insufficient_quota":
        return (
            "OpenAI ha rechazado la peticion por cuota o limite de uso. "
            "Revisa el saldo de tu cuenta."
        )
    if codigo == "model_not_found":
        return (
            f"Tu cuenta no tiene acceso al modelo '{settings.openai_model}'. "
            "Cambia OPENAI_MODEL por uno que si tengas."
        )
    return f"OpenAI ha devuelto un error ({status_code}): {mensaje[:160]}"


def extract_songs(image: bytes, mime_type: str = "image/png") -> list[DetectedSong]:
    """Devuelve las canciones que se leen en la imagen, en su orden."""
    if not is_enabled():
        raise ScreenshotNotConfigured(
            "La lectura de capturas no esta configurada. Falta OPENAI_API_KEY."
        )

    data_url = f"data:{mime_type};base64,{base64.b64encode(image).decode('ascii')}"
    cuerpo = {
        "model": settings.openai_model,
        # Fuerza JSON valido: sin esto el modelo tiende a envolverlo en prosa.
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": INSTRUCCIONES},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Extrae las canciones de esta captura."},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            },
        ],
    }

    try:
        respuesta = httpx.post(
            OPENAI_ENDPOINT,
            headers={"Authorization": f"Bearer {settings.openai_api_key}"},
            json=cuerpo,
            timeout=settings.openai_timeout_seconds,
        )
    except httpx.HTTPError as exc:
        raise ScreenshotError(f"No se pudo contactar con OpenAI: {exc}") from exc

    payload = respuesta.json() if respuesta.content else {}
    if respuesta.status_code >= 400:
        raise ScreenshotError(_mensaje_error(payload, respuesta.status_code))

    try:
        contenido = payload["choices"][0]["message"]["content"]
        datos = json.loads(contenido)
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise ScreenshotError("OpenAI no ha devuelto un resultado legible.") from exc

    canciones: list[DetectedSong] = []
    vistas: set[tuple[str, str]] = set()
    for entrada in datos.get("songs") or []:
        if not isinstance(entrada, dict):
            continue
        titulo = str(entrada.get("title") or "").strip()
        interprete = str(entrada.get("artist") or "").strip()
        if not titulo:
            continue
        clave = (titulo.lower(), interprete.lower())
        if clave in vistas:  # una captura puede repetir la misma cancion
            continue
        vistas.add(clave)
        canciones.append(DetectedSong(title=titulo, artist=interprete or None))

    return canciones
