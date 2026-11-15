"""Interpretacion de lo que devuelve el modelo de vision de cada proveedor."""

import json
from types import SimpleNamespace

import httpx
import pytest

from app.services import screenshot, screenshot_anthropic
from app.services.ai_keys import AiConfig
from app.services.screenshot import ScreenshotError, ScreenshotNotConfigured

OPENAI = AiConfig("openai", "sk-clave", "gpt-4o-mini")
GROK = AiConfig("grok", "xai-clave", "grok-4")


def responder(monkeypatch, *, contenido=None, status_code=200, payload=None):
    cuerpo = payload if payload is not None else {"choices": [{"message": {"content": contenido}}]}
    pedidas: list[tuple[str, dict]] = []

    def fake_post(url, **kwargs):
        pedidas.append((url, kwargs))
        return httpx.Response(status_code, json=cuerpo, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", fake_post)
    return pedidas


def test_lee_las_canciones(monkeypatch) -> None:
    pedidas = responder(monkeypatch, contenido=json.dumps({"songs": [
        {"title": "Song 2", "artist": "Blur"},
        {"title": "Parklife", "artist": ""},
    ]}))
    canciones = screenshot.extract_songs(b"imagen", "image/png", OPENAI)
    assert [(c.title, c.artist) for c in canciones] == [("Song 2", "Blur"), ("Parklife", None)]
    url, peticion = pedidas[0]
    assert url == "https://api.openai.com/v1/chat/completions"
    assert peticion["headers"]["Authorization"] == "Bearer sk-clave"
    assert peticion["json"]["model"] == "gpt-4o-mini"


def test_grok_va_a_xai_con_su_clave(monkeypatch) -> None:
    pedidas = responder(monkeypatch, contenido=json.dumps({"songs": [{"title": "A", "artist": "B"}]}))
    assert len(screenshot.extract_songs(b"imagen", "image/jpeg", GROK)) == 1
    url, peticion = pedidas[0]
    assert url == "https://api.x.ai/v1/chat/completions"
    assert peticion["headers"]["Authorization"] == "Bearer xai-clave"
    assert peticion["json"]["model"] == "grok-4"


def test_descarta_repetidas_y_sin_titulo(monkeypatch) -> None:
    """Una captura puede mostrar la misma cancion dos veces."""
    responder(monkeypatch, contenido=json.dumps({"songs": [
        {"title": "Song 2", "artist": "Blur"},
        {"title": "song 2", "artist": "BLUR"},
        {"title": "", "artist": "Nadie"},
        {"title": "  Parklife  ", "artist": "  Blur  "},
    ]}))
    canciones = screenshot.extract_songs(b"imagen", "image/png", OPENAI)
    assert [(c.title, c.artist) for c in canciones] == [("Song 2", "Blur"), ("Parklife", "Blur")]


def test_captura_sin_canciones(monkeypatch) -> None:
    responder(monkeypatch, contenido=json.dumps({"songs": []}))
    assert screenshot.extract_songs(b"imagen", "image/png", OPENAI) == []


def test_respuesta_ilegible(monkeypatch) -> None:
    responder(monkeypatch, contenido="esto no es json")
    with pytest.raises(ScreenshotError, match="legible"):
        screenshot.extract_songs(b"imagen", "image/png", OPENAI)


@pytest.mark.parametrize(
    ("status_code", "payload", "esperado"),
    [
        (401, {"error": {"message": "bad key"}}, "no acepta tu clave"),
        (429, {"error": {"code": "insufficient_quota", "message": "x"}}, "cuota"),
        (404, {"error": {"code": "model_not_found", "message": "x"}}, "no tiene el modelo"),
    ],
)
def test_los_errores_se_traducen(monkeypatch, status_code, payload, esperado) -> None:
    responder(monkeypatch, status_code=status_code, payload=payload)
    with pytest.raises(ScreenshotError, match=esperado):
        screenshot.extract_songs(b"imagen", "image/png", OPENAI)


def test_sin_clave(monkeypatch) -> None:
    with pytest.raises(ScreenshotNotConfigured, match="Mi cuenta"):
        screenshot.extract_songs(b"imagen", "image/png", None)


class ClienteFalso:
    """Lo minimo del cliente del SDK de Anthropic que se usa."""

    def __init__(self, texto: str, stop_reason: str = "end_turn") -> None:
        self.peticiones: list[tuple[str, dict]] = []
        respuesta = SimpleNamespace(
            stop_reason=stop_reason, content=[SimpleNamespace(type="text", text=texto)]
        )

        def crear(nombre):
            def create(**params):
                self.peticiones.append((nombre, params))
                return respuesta
            return create

        self.messages = SimpleNamespace(create=crear("normal"))
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=crear("beta")))


def con_claude(monkeypatch, cliente: ClienteFalso, claves: list[str]) -> None:
    def fabricar(api_key, **kwargs):
        claves.append(api_key)
        return cliente

    monkeypatch.setattr(screenshot_anthropic.anthropic, "Anthropic", fabricar)


def test_anthropic_con_el_sdk(monkeypatch) -> None:
    cliente = ClienteFalso(json.dumps({"songs": [{"title": "Song 2", "artist": "Blur"}]}))
    claves: list[str] = []
    con_claude(monkeypatch, cliente, claves)

    conf = AiConfig("anthropic", "sk-ant-clave", "claude-opus-5-5")
    canciones = screenshot.extract_songs(b"imagen", "image/webp", conf)

    assert [(c.title, c.artist) for c in canciones] == [("Song 2", "Blur")]
    assert claves == ["sk-ant-clave"]
    via, params = cliente.peticiones[0]
    # Con Opus 5.5 se pide que otro modelo la haga si este la rechaza
    assert via == "beta"
    assert params["fallbacks"] == "default"
    assert params["model"] == "claude-opus-5-5"
    imagen = params["messages"][0]["content"][0]
    assert imagen["type"] == "image" and imagen["source"]["media_type"] == "image/webp"
    assert params["output_config"]["format"]["type"] == "json_schema"
    assert params["output_config"]["effort"] == "low"


def test_anthropic_rechazo(monkeypatch) -> None:
    con_claude(monkeypatch, ClienteFalso("", stop_reason="refusal"), [])
    conf = AiConfig("anthropic", "sk-ant-clave", "claude-haiku-4-5")
    with pytest.raises(ScreenshotError, match="no ha querido"):
        screenshot.extract_songs(b"imagen", "image/png", conf)
