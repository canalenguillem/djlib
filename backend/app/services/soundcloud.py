"""Datos de un tema de SoundCloud sin bajarlo.

Los temas de las discograficas estan protegidos con DRM: yt-dlp no da ni el
titulo. El oEmbed publico de SoundCloud si, y con eso se puede buscar el mismo
tema en otro sitio.
"""

from __future__ import annotations

import re

import httpx

from app.core.config import settings


def titulo_y_artista(url: str) -> tuple[str, str | None] | None:
    """("Cry for Love (Extended Mix)", "Riordan"), o None si no se sabe."""
    try:
        respuesta = httpx.get(
            "https://soundcloud.com/oembed",
            params={"url": url, "format": "json"},
            follow_redirects=True,
            timeout=settings.spotify_timeout_seconds,
        )
        respuesta.raise_for_status()
        datos = respuesta.json()
    except (httpx.HTTPError, ValueError):
        return None
    autor = (datos.get("author_name") or "").strip() or None
    titulo = (datos.get("title") or "").strip()
    # El oEmbed lo da como "Cry for Love - Extended Mix by Riordan"
    if autor and titulo.lower().endswith(f" by {autor.lower()}"):
        titulo = titulo[: -len(autor) - 4].strip()
    # "Tema - Extended Mix" es como lo escribe Beatport: "Tema (Extended Mix)"
    titulo = re.sub(r"\s+-\s+((?:extended|original|radio|club)\b.*(?:mix|edit|version))$", r" (\1)", titulo, flags=re.I)
    if not titulo:
        return None
    return titulo, autor
