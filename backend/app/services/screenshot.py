"""Lectura de capturas de pantalla con un modelo de vision: el de OpenAI,
Anthropic o Grok que haya elegido cada usuario, con su propia clave.

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
from app.services import screenshot_anthropic
from app.services.ai_keys import BASES_COMPATIBLES, AiConfig

logger = logging.getLogger(__name__)

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


def _mensaje_error(nombre: str, modelo: str, payload: dict, status_code: int) -> str:
    error = (payload or {}).get("error") or {}
    if isinstance(error, str):
        error = {"message": error}
    codigo = error.get("code") or ""
    mensaje = error.get("message") or ""

    if status_code in (401, 403):
        return f"{nombre} no acepta tu clave. Revísala en Mi cuenta."
    if status_code == 429 or codigo == "insufficient_quota":
        return f"{nombre} ha rechazado la petición por cuota o límite de uso. Revisa el saldo de tu cuenta."
    if codigo == "model_not_found" or status_code == 404:
        return f"Tu cuenta de {nombre} no tiene el modelo «{modelo}». Cámbialo en Mi cuenta."
    return f"{nombre} ha devuelto un error ({status_code}): {str(mensaje)[:160]}"


def _compatible_openai(image: bytes, mime_type: str, conf: AiConfig) -> dict:
    """OpenAI y Grok: la misma API de chat, con la imagen como data URL."""
    data_url = f"data:{mime_type};base64,{base64.b64encode(image).decode('ascii')}"
    cuerpo = {
        "model": conf.model,
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
            f"{BASES_COMPATIBLES[conf.provider]}/chat/completions",
            headers={"Authorization": f"Bearer {conf.api_key}"},
            json=cuerpo,
            timeout=settings.openai_timeout_seconds,
        )
    except httpx.HTTPError as exc:
        raise ScreenshotError(f"No se pudo contactar con {conf.nombre}.") from exc

    try:
        payload = respuesta.json() if respuesta.content else {}
    except ValueError:
        payload = {}
    if respuesta.status_code >= 400:
        raise ScreenshotError(_mensaje_error(conf.nombre, conf.model, payload, respuesta.status_code))
    try:
        return json.loads(payload["choices"][0]["message"]["content"])
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise ScreenshotError(f"{conf.nombre} no ha devuelto un resultado legible.") from exc


def extract_songs(image: bytes, mime_type: str, conf: AiConfig | None) -> list[DetectedSong]:
    """Devuelve las canciones que se leen en la imagen, en su orden, con la
    clave y el proveedor de IA del usuario."""
    if conf is None:
        raise ScreenshotNotConfigured(
            "Para leer capturas pon tu clave de OpenAI, Anthropic o Grok en Mi cuenta."
        )
    if conf.provider == "anthropic":
        try:
            datos = screenshot_anthropic.extraer(image, mime_type, conf.api_key, conf.model, INSTRUCCIONES)
        except screenshot_anthropic.ClaudeError as exc:
            raise ScreenshotError(str(exc)) from exc
    else:
        datos = _compatible_openai(image, mime_type, conf)

    canciones: list[DetectedSong] = []
    vistas: set[tuple[str, str]] = set()
    for entrada in (datos or {}).get("songs") or []:
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
