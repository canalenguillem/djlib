"""Leer una captura con Claude, de Anthropic, con la clave del usuario.

Va con el SDK oficial de Anthropic. La salida se pide con un esquema JSON
(structured outputs), asi que la respuesta siempre se puede leer.
"""

from __future__ import annotations

import base64
import json

import anthropic

from app.core.config import settings

# Modelos con los que se pide, ademas, que si uno rechaza la peticion la haga
# otro (fallbacks del servidor): con los demas se manda la peticion normal
CON_FALLBACK = {"claude-opus-5-5", "claude-opus-5", "claude-fable-5-2", "claude-fable-5-1", "claude-sonnet-5-5"}
# Los que aceptan el nivel de esfuerzo; leer una lista no pide mas que "low"
CON_ESFUERZO = ("claude-opus-5", "claude-sonnet-5", "claude-fable-5", "claude-haiku-5", "claude-opus-4")

ESQUEMA = {
    "type": "object",
    "properties": {
        "songs": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"title": {"type": "string"}, "artist": {"type": "string"}},
                "required": ["title", "artist"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["songs"],
    "additionalProperties": False,
}


class ClaudeError(RuntimeError):
    """Un fallo que se le puede explicar al usuario."""


def _cliente(api_key: str) -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=api_key, timeout=settings.openai_timeout_seconds, max_retries=1)


def _explicar(exc: anthropic.APIError, modelo: str) -> ClaudeError:
    if isinstance(exc, anthropic.AuthenticationError):
        return ClaudeError("Anthropic no acepta tu clave. Revísala en Mi cuenta.")
    if isinstance(exc, anthropic.PermissionDeniedError):
        return ClaudeError("Tu clave de Anthropic no tiene permiso para esto.")
    if isinstance(exc, anthropic.NotFoundError):
        return ClaudeError(f"Tu cuenta de Anthropic no tiene el modelo «{modelo}». Cámbialo en Mi cuenta.")
    if isinstance(exc, anthropic.RateLimitError):
        return ClaudeError("Anthropic ha rechazado la petición por límite de uso. Prueba dentro de un rato.")
    if isinstance(exc, anthropic.BadRequestError):
        # Aqui llega, por ejemplo, el saldo agotado
        return ClaudeError(f"Anthropic ha rechazado la petición: {exc.message[:200]}")
    if isinstance(exc, anthropic.APIStatusError):
        return ClaudeError(f"Anthropic ha devuelto un error ({exc.status_code}). Prueba dentro de un rato.")
    if isinstance(exc, anthropic.APIConnectionError):
        return ClaudeError("No se pudo contactar con Anthropic.")
    return ClaudeError("Anthropic ha fallado.")


def comprobar(api_key: str, modelo: str) -> None:
    """Que la clave vale y tiene el modelo, sin gastar nada."""
    try:
        _cliente(api_key).models.retrieve(modelo)
    except anthropic.APIError as exc:
        raise _explicar(exc, modelo) from exc


def extraer(imagen: bytes, mime_type: str, api_key: str, modelo: str, instrucciones: str) -> dict:
    """Devuelve el JSON {"songs": [...]} que lee Claude en la imagen."""
    params: dict = {
        "model": modelo,
        "max_tokens": 16000,
        "system": instrucciones,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": mime_type,
                            "data": base64.standard_b64encode(imagen).decode("ascii"),
                        },
                    },
                    {"type": "text", "text": "Extrae las canciones de esta captura."},
                ],
            }
        ],
    }
    salida: dict = {"format": {"type": "json_schema", "schema": ESQUEMA}}
    if modelo.startswith(CON_ESFUERZO):
        salida["effort"] = "low"
    params["output_config"] = salida

    cliente = _cliente(api_key)
    try:
        if modelo in CON_FALLBACK:
            respuesta = cliente.beta.messages.create(
                betas=["server-side-fallback-2026-07-01"], fallbacks="default", **params
            )
        else:
            respuesta = cliente.messages.create(**params)
    except anthropic.APIError as exc:
        raise _explicar(exc, modelo) from exc

    if respuesta.stop_reason == "refusal":
        raise ClaudeError("Claude no ha querido leer esta captura.")
    if respuesta.stop_reason == "max_tokens":
        raise ClaudeError("La captura tiene demasiadas canciones para leerlas de una vez.")
    texto = next((b.text for b in respuesta.content if b.type == "text"), "")
    try:
        return json.loads(texto)
    except ValueError as exc:
        raise ClaudeError("Claude no ha devuelto un resultado legible.") from exc
