"""Las claves de IA de cada usuario: OpenAI, Anthropic o Grok.

Antes habia una sola clave de OpenAI en el .env y la pagaba el servidor. Ahora
cada usuario pone la suya (o las de varios proveedores) y elige cual se usa.

Las claves se guardan cifradas con una clave derivada del secreto del
servidor: una copia de la base de datos sola no basta para gastar con ellas.
Si el secreto cambia, las claves guardadas dejan de poder leerse y hay que
volver a ponerlas.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass

import httpx
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.ai import AiKey
from app.models.user import User


@dataclass(frozen=True)
class Proveedor:
    id: str
    nombre: str
    modelo: str
    # Donde se saca la clave, para ponerlo en la pantalla
    consola: str


PROVEEDORES: dict[str, Proveedor] = {
    p.id: p
    for p in (
        Proveedor("openai", "OpenAI", settings.openai_model, "https://platform.openai.com/api-keys"),
        Proveedor("anthropic", "Anthropic", "claude-opus-5-5", "https://platform.claude.com/settings/keys"),
        Proveedor("grok", "Grok (xAI)", "grok-4", "https://console.x.ai"),
    )
}

# OpenAI y Grok hablan la misma API
BASES_COMPATIBLES = {"openai": "https://api.openai.com/v1", "grok": "https://api.x.ai/v1"}


class AiKeyError(RuntimeError):
    """Algo que el usuario tiene que corregir: proveedor que no existe, clave
    vacia, clave que no se puede leer."""


@dataclass(frozen=True)
class AiConfig:
    provider: str
    api_key: str
    model: str

    @property
    def nombre(self) -> str:
        return PROVEEDORES[self.provider].nombre


def _fernet() -> Fernet:
    clave = HKDF(
        algorithm=hashes.SHA256(), length=32, salt=None, info=b"djwill-ai-keys"
    ).derive(settings.jwt_secret_key.encode())
    return Fernet(base64.urlsafe_b64encode(clave))


def _cifrar(texto: str) -> str:
    return _fernet().encrypt(texto.encode()).decode()


def _descifrar(texto: str) -> str | None:
    try:
        return _fernet().decrypt(texto.encode()).decode()
    except InvalidToken:
        return None


def _comprobar(provider: str) -> Proveedor:
    if provider not in PROVEEDORES:
        raise AiKeyError("Ese proveedor de IA no existe.")
    return PROVEEDORES[provider]


def claves(db: Session, user: User) -> dict[str, AiKey]:
    return {k.provider: k for k in db.scalars(select(AiKey).where(AiKey.user_id == user.id))}


def guardar(db: Session, user: User, provider: str, api_key: str | None, model: str | None) -> AiKey:
    """Pone o cambia la clave y el modelo. Sin clave, solo cambia el modelo
    de una que ya estaba. La primera que se pone queda elegida."""
    _comprobar(provider)
    existente = claves(db, user).get(provider)
    api_key = (api_key or "").strip()
    model = (model or "").strip() or None
    if existente is None and not api_key:
        raise AiKeyError("Pega la clave del proveedor.")
    if existente is None:
        existente = AiKey(user_id=user.id, provider=provider)
        db.add(existente)
    if api_key:
        existente.api_key_cifrada = _cifrar(api_key)
        existente.pista = api_key[-4:]
    existente.model = model
    if not user.ai_provider:
        user.ai_provider = provider
    db.flush()
    return existente


def borrar(db: Session, user: User, provider: str) -> None:
    _comprobar(provider)
    existente = claves(db, user).get(provider)
    if existente is not None:
        db.delete(existente)
    if user.ai_provider == provider:
        # Pasa a otra que tenga, si hay alguna
        otras = [p for p in claves(db, user) if p != provider]
        user.ai_provider = otras[0] if otras else None
    db.flush()


def elegir(db: Session, user: User, provider: str) -> None:
    _comprobar(provider)
    if provider not in claves(db, user):
        raise AiKeyError("Primero pon la clave de ese proveedor.")
    user.ai_provider = provider
    db.flush()


def config(db: Session, user: User, provider: str | None = None) -> AiConfig | None:
    """La clave con la que trabajar: la del proveedor elegido, o la del que se
    pida. None si no hay. AiKeyError si esta pero no se puede leer."""
    provider = provider or user.ai_provider
    if not provider or provider not in PROVEEDORES:
        return None
    guardada = claves(db, user).get(provider)
    if guardada is None:
        return None
    api_key = _descifrar(guardada.api_key_cifrada)
    if api_key is None:
        raise AiKeyError(
            f"La clave de {PROVEEDORES[provider].nombre} no se puede leer (ha cambiado el "
            "secreto del servidor). Vuelve a ponerla en Mi cuenta."
        )
    return AiConfig(provider, api_key, guardada.model or PROVEEDORES[provider].modelo)


def probar(conf: AiConfig) -> str:
    """Comprueba la clave y el modelo sin gastar: pide la ficha del modelo.
    Devuelve un texto para el usuario; AiKeyError si falla."""
    if conf.provider == "anthropic":
        from app.services import screenshot_anthropic

        try:
            screenshot_anthropic.comprobar(conf.api_key, conf.model)
        except screenshot_anthropic.ClaudeError as exc:
            raise AiKeyError(str(exc)) from exc
        return f"La clave de Anthropic funciona y tiene acceso a {conf.model}."

    base = BASES_COMPATIBLES[conf.provider]
    try:
        respuesta = httpx.get(
            f"{base}/models/{conf.model}",
            headers={"Authorization": f"Bearer {conf.api_key}"},
            timeout=20,
        )
    except httpx.HTTPError as exc:
        raise AiKeyError(f"No se pudo contactar con {conf.nombre}.") from exc
    if respuesta.status_code in (401, 403):
        raise AiKeyError(f"{conf.nombre} no acepta esta clave.")
    if respuesta.status_code == 404:
        raise AiKeyError(f"La clave vale, pero {conf.nombre} no tiene el modelo «{conf.model}».")
    if respuesta.status_code >= 400:
        raise AiKeyError(f"{conf.nombre} ha devuelto un error ({respuesta.status_code}).")
    return f"La clave de {conf.nombre} funciona y tiene acceso a {conf.model}."
