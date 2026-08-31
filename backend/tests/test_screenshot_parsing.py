"""Interpretacion de lo que devuelve el modelo de vision."""

import json

import httpx
import pytest

from app.core.config import settings
from app.services import screenshot
from app.services.screenshot import ScreenshotError, ScreenshotNotConfigured


@pytest.fixture(autouse=True)
def con_clave(monkeypatch):
    monkeypatch.setattr(settings, "openai_api_key", "clave")
    monkeypatch.setattr(settings, "openai_model", "gpt-4o-mini")


def responder(monkeypatch, *, contenido=None, status_code=200, payload=None):
    cuerpo = payload if payload is not None else {
        "choices": [{"message": {"content": contenido}}]
    }

    def fake_post(*args, **kwargs):
        return httpx.Response(
            status_code, json=cuerpo, request=httpx.Request("POST", screenshot.OPENAI_ENDPOINT)
        )

    monkeypatch.setattr(httpx, "post", fake_post)


def test_lee_las_canciones(monkeypatch) -> None:
    responder(monkeypatch, contenido=json.dumps({"songs": [
        {"title": "Song 2", "artist": "Blur"},
        {"title": "Parklife", "artist": ""},
    ]}))
    canciones = screenshot.extract_songs(b"imagen")
    assert [(c.title, c.artist) for c in canciones] == [("Song 2", "Blur"), ("Parklife", None)]


def test_descarta_repetidas_y_sin_titulo(monkeypatch) -> None:
    """Una captura puede mostrar la misma cancion dos veces."""
    responder(monkeypatch, contenido=json.dumps({"songs": [
        {"title": "Song 2", "artist": "Blur"},
        {"title": "song 2", "artist": "BLUR"},
        {"title": "", "artist": "Nadie"},
        {"title": "  Parklife  ", "artist": "  Blur  "},
    ]}))
    canciones = screenshot.extract_songs(b"imagen")
    assert [(c.title, c.artist) for c in canciones] == [("Song 2", "Blur"), ("Parklife", "Blur")]


def test_captura_sin_canciones(monkeypatch) -> None:
    responder(monkeypatch, contenido=json.dumps({"songs": []}))
    assert screenshot.extract_songs(b"imagen") == []


def test_respuesta_ilegible(monkeypatch) -> None:
    responder(monkeypatch, contenido="esto no es json")
    with pytest.raises(ScreenshotError, match="legible"):
        screenshot.extract_songs(b"imagen")


@pytest.mark.parametrize(
    ("status_code", "payload", "esperado"),
    [
        (401, {"error": {"message": "bad key"}}, "clave de OpenAI no es valida"),
        (429, {"error": {"code": "insufficient_quota", "message": "x"}}, "cuota"),
        (404, {"error": {"code": "model_not_found", "message": "x"}}, "OPENAI_MODEL"),
    ],
)
def test_los_errores_de_openai_se_traducen(monkeypatch, status_code, payload, esperado) -> None:
    responder(monkeypatch, status_code=status_code, payload=payload)
    with pytest.raises(ScreenshotError, match=esperado):
        screenshot.extract_songs(b"imagen")


def test_sin_clave_configurada(monkeypatch) -> None:
    monkeypatch.setattr(settings, "openai_api_key", "")
    with pytest.raises(ScreenshotNotConfigured):
        screenshot.extract_songs(b"imagen")
