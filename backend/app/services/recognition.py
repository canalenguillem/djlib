"""Reconocimiento de audio: identificar una cancion a partir de un fragmento.

Ahora mismo habla con AudD. La interfaz (`recognize`) esta separada del
proveedor para poder anadir ACRCloud sin tocar el resto: el router y el
frontend solo conocen `RecognizedTrack`.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

AUDD_ENDPOINT = "https://api.audd.io/"

# Codigos que devuelve AudD y que conviene traducir a algo accionable.
# https://docs.audd.io/#common-errors
_AUDD_ERRORS = {
    900: "La clave de AudD no es valida. Revisa RECOGNITION_API_KEY.",
    901: "Se han agotado las peticiones de AudD. Amplia el plan en dashboard.audd.io.",
    902: "La clave de AudD ha caducado.",
    903: "AudD no ha recibido la clave. Revisa RECOGNITION_API_KEY.",
    905: "AudD ha rechazado la peticion por exceso de llamadas simultaneas.",
}


class RecognitionError(RuntimeError):
    """Fallo al identificar: red, cuota o configuracion. No es "no reconocida"."""


class RecognitionNotConfigured(RecognitionError):
    pass


@dataclass(frozen=True)
class RecognizedTrack:
    artist: str
    title: str
    album: str | None = None
    release_date: str | None = None
    song_link: str | None = None

    @property
    def search_terms(self) -> str:
        return f"{self.artist} {self.title}".strip()


def is_enabled() -> bool:
    return bool(settings.recognition_provider and settings.recognition_api_key)


def provider_name() -> str:
    return settings.recognition_provider.lower()


def recognize(audio: bytes, filename: str = "fragmento.webm") -> RecognizedTrack | None:
    """Identifica el fragmento. Devuelve None si no reconoce nada.

    Distinguir "no reconocida" de "ha fallado" importa: lo primero se resuelve
    volviendo a grabar mas cerca del altavoz; lo segundo, no.
    """
    if not is_enabled():
        raise RecognitionNotConfigured(
            "El reconocimiento no esta configurado. Falta RECOGNITION_PROVIDER o "
            "RECOGNITION_API_KEY."
        )
    if provider_name() != "audd":
        raise RecognitionNotConfigured(
            f"Proveedor de reconocimiento no soportado: {settings.recognition_provider}"
        )
    return _recognize_audd(audio, filename)


def _recognize_audd(audio: bytes, filename: str) -> RecognizedTrack | None:
    try:
        response = httpx.post(
            AUDD_ENDPOINT,
            data={"api_token": settings.recognition_api_key},
            files={"file": (filename, audio, "application/octet-stream")},
            timeout=settings.recognition_timeout_seconds,
        )
    except httpx.HTTPError as exc:
        raise RecognitionError(f"No se pudo contactar con AudD: {exc}") from exc

    if response.status_code >= 400:
        raise RecognitionError(f"AudD respondio {response.status_code}.")

    try:
        payload = response.json()
    except ValueError as exc:
        raise RecognitionError("AudD no devolvio una respuesta valida.") from exc

    if payload.get("status") == "error":
        error = payload.get("error") or {}
        codigo = error.get("error_code")
        raise RecognitionError(
            _AUDD_ERRORS.get(codigo)
            or f"AudD ha devuelto un error ({codigo}): {error.get('error_message', '')}"
        )

    result = payload.get("result")
    if not result:  # None cuando no reconoce nada
        return None

    artist = (result.get("artist") or "").strip()
    title = (result.get("title") or "").strip()
    if not artist and not title:
        return None

    return RecognizedTrack(
        artist=artist,
        title=title,
        album=(result.get("album") or None),
        release_date=(result.get("release_date") or None),
        song_link=(result.get("song_link") or None),
    )
