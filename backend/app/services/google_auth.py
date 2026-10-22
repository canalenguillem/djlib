"""Entrar con Google: el boton del navegador devuelve un ID token firmado por
Google y aqui se comprueba la firma y para quien es. Solo sirve para entrar
con un usuario que ya existe; no da de alta a nadie."""

from typing import Any

import jwt

from app.core.config import settings

GOOGLE_CERTS_URL = "https://www.googleapis.com/oauth2/v3/certs"
GOOGLE_ISSUERS = ("accounts.google.com", "https://accounts.google.com")

# Guarda las claves publicas de Google entre peticiones; cambian cada pocos dias
_jwks: jwt.PyJWKClient | None = None


class GoogleAuthError(Exception):
    pass


def _client() -> jwt.PyJWKClient:
    global _jwks
    if _jwks is None:
        _jwks = jwt.PyJWKClient(GOOGLE_CERTS_URL, timeout=settings.google_timeout_seconds)
    return _jwks


def verify_id_token(credential: str) -> str:
    """Devuelve el correo verificado del token, o GoogleAuthError."""
    if not settings.google_client_id:
        raise GoogleAuthError("Entrar con Google no esta configurado.")
    try:
        clave = _client().get_signing_key_from_jwt(credential)
        datos: dict[str, Any] = jwt.decode(
            credential,
            clave.key,
            algorithms=["RS256"],
            audience=settings.google_client_id,
            options={"require": ["exp", "iat", "iss", "aud", "email"]},
        )
    except (jwt.PyJWTError, jwt.PyJWKClientError) as exc:
        raise GoogleAuthError("La respuesta de Google no es valida.") from exc
    if datos.get("iss") not in GOOGLE_ISSUERS:
        raise GoogleAuthError("La respuesta de Google no es valida.")
    # Sin verificar, cualquiera podria poner el correo de otro en su cuenta
    if datos.get("email_verified") is not True:
        raise GoogleAuthError("Google no ha verificado ese correo.")
    return str(datos["email"])
