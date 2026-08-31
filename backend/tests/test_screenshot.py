"""Leer canciones de una captura de pantalla.

El caso real: Shazam identifica solo durante la noche y al dia siguiente se
sube la captura de la lista, en vez de teclear diez canciones a mano.
"""

from fastapi.testclient import TestClient

from app.services.screenshot import ScreenshotError
from tests.conftest import ADMIN_PASSWORD, auth_headers, login

PNG = b"\x89PNG\r\n\x1a\n" + b"captura-de-mentira" * 50


def headers(client: TestClient) -> dict[str, str]:
    return auth_headers(login(client, "enguillem", ADMIN_PASSWORD)["access_token"])


def enviar(client: TestClient, h: dict, contenido: bytes = PNG, tipo: str = "image/png"):
    return client.post(
        "/recognize/screenshot",
        files={"image": ("captura.png", contenido, tipo)},
        headers=h,
    )


def test_requiere_sesion(client: TestClient) -> None:
    assert client.post("/recognize/screenshot", files={"image": ("a.png", PNG)}).status_code == 401


def test_el_estado_dice_si_se_pueden_leer_capturas(
    client: TestClient, admin_user, fake_screenshot
) -> None:
    estado = client.get("/recognize/status", headers=headers(client)).json()
    assert estado["screenshot_enabled"] is True


def test_sin_clave_de_openai_se_avisa(client: TestClient, admin_user, monkeypatch) -> None:
    from app.core.config import settings

    monkeypatch.setattr(settings, "openai_api_key", "")
    h = headers(client)

    assert client.get("/recognize/status", headers=h).json()["screenshot_enabled"] is False
    respuesta = enviar(client, h)
    assert respuesta.status_code == 503
    assert "no esta configurada" in respuesta.json()["detail"]


def test_devuelve_las_canciones_en_orden(
    client: TestClient, admin_user, fake_screenshot
) -> None:
    respuesta = enviar(client, headers(client))
    assert respuesta.status_code == 200
    canciones = respuesta.json()["songs"]

    assert [(c["title"], c["artist"]) for c in canciones] == [
        ("Song 2", "Blur"),
        ("Parklife", "Blur"),
        ("Sin artista", None),
    ]
    # La imagen llega entera y con su tipo
    assert fake_screenshot.recibido == [(len(PNG), "image/png")]


def test_captura_sin_canciones(client: TestClient, admin_user, fake_screenshot) -> None:
    fake_screenshot.songs = []
    assert enviar(client, headers(client)).json()["songs"] == []


def test_formato_de_imagen_no_admitido(
    client: TestClient, admin_user, fake_screenshot
) -> None:
    respuesta = enviar(client, headers(client), tipo="application/pdf")
    assert respuesta.status_code == 400
    assert "no admitido" in respuesta.json()["detail"]
    assert fake_screenshot.recibido == []  # no se gasta una llamada al modelo


def test_imagen_vacia(client: TestClient, admin_user, fake_screenshot) -> None:
    assert enviar(client, headers(client), contenido=b"").status_code == 400


def test_imagen_demasiado_grande(
    client: TestClient, admin_user, fake_screenshot, monkeypatch
) -> None:
    from app.core.config import settings

    monkeypatch.setattr(settings, "screenshot_max_bytes", 100)
    respuesta = enviar(client, headers(client), contenido=b"x" * 500)
    assert respuesta.status_code == 413
    assert fake_screenshot.recibido == []


def test_si_openai_falla_se_explica(
    client: TestClient, admin_user, fake_screenshot
) -> None:
    fake_screenshot.error = ScreenshotError("La clave de OpenAI no es valida.")
    respuesta = enviar(client, headers(client))
    assert respuesta.status_code == 502
    assert "clave de OpenAI" in respuesta.json()["detail"]


def test_de_la_captura_a_la_biblioteca(
    client: TestClient, admin_user, fake_screenshot, fake_downloader
) -> None:
    """El flujo entero: leer la captura y descargar una de las canciones."""
    h = headers(client)
    canciones = enviar(client, h).json()["songs"]
    primera = canciones[0]

    candidatos = client.post(
        "/tracks/search/preview",
        json={"title": primera["title"], "artist": primera["artist"]},
        headers=h,
    ).json()["candidates"]
    elegido = next(c for c in candidatos if not c["too_long"])

    alta = client.post("/tracks/from-url", json={"url": elegido["url"]}, headers=h)
    assert alta.status_code == 202
    assert client.get(f"/tracks/{alta.json()['id']}", headers=h).json()["status"] == "ready"
