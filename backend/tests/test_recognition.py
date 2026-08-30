"""Reconocimiento de audio: el flujo de grabar en un bar e identificar el tema."""

from fastapi.testclient import TestClient

from app.services.recognition import RecognitionError
from tests.conftest import ADMIN_PASSWORD, auth_headers, login

FRAGMENTO = b"\x1aE\xdf\xa3" + b"audio-de-mentira" * 100


def headers(client: TestClient) -> dict[str, str]:
    return auth_headers(login(client, "enguillem", ADMIN_PASSWORD)["access_token"])


def enviar(client: TestClient, h: dict[str, str], contenido: bytes = FRAGMENTO):
    return client.post(
        "/recognize",
        files={"audio": ("fragmento.webm", contenido, "audio/webm")},
        headers=h,
    )


# --- Acceso y disponibilidad ------------------------------------------------


def test_reconocer_requiere_sesion(client: TestClient) -> None:
    assert client.post("/recognize", files={"audio": ("a.webm", b"x")}).status_code == 401


def test_el_estado_dice_si_esta_configurado(
    client: TestClient, admin_user, fake_recognition
) -> None:
    respuesta = client.get("/recognize/status", headers=headers(client))
    assert respuesta.json() == {"enabled": True, "provider": "audd"}


def test_sin_clave_configurada_se_avisa(client: TestClient, admin_user, monkeypatch) -> None:
    from app.core.config import settings

    monkeypatch.setattr(settings, "recognition_provider", "")
    monkeypatch.setattr(settings, "recognition_api_key", "")
    h = headers(client)

    assert client.get("/recognize/status", headers=h).json()["enabled"] is False
    # Y el endpoint lo dice claro en vez de fallar de forma generica
    respuesta = enviar(client, h)
    assert respuesta.status_code == 503
    assert "no esta configurado" in respuesta.json()["detail"]


# --- Identificacion ---------------------------------------------------------


def test_cancion_reconocida_devuelve_datos_y_candidatos(
    client: TestClient, admin_user, fake_recognition, fake_downloader
) -> None:
    respuesta = enviar(client, headers(client))
    assert respuesta.status_code == 200
    datos = respuesta.json()

    assert datos["recognized"] is True
    assert datos["artist"] == "Blur"
    assert datos["title"] == "Song 2"
    assert datos["album"] == "Blur"
    # Se busca en YouTube en la misma llamada: en el movil ahorra una vuelta
    assert fake_downloader.searched == [("Song 2", "Blur")]
    assert len(datos["candidates"]) == 2
    assert datos["candidates"][0]["too_long"] is True


def test_cancion_no_reconocida(
    client: TestClient, admin_user, fake_recognition, fake_downloader
) -> None:
    fake_recognition.track = None
    datos = enviar(client, headers(client)).json()
    assert datos["recognized"] is False
    assert datos["candidates"] == []
    assert fake_downloader.searched == []  # no se busca lo que no se conoce


def test_el_fragmento_llega_entero_al_proveedor(
    client: TestClient, admin_user, fake_recognition, fake_downloader
) -> None:
    enviar(client, headers(client))
    assert fake_recognition.recibido == [len(FRAGMENTO)]


def test_si_audd_falla_se_distingue_de_no_reconocida(
    client: TestClient, admin_user, fake_recognition, fake_downloader
) -> None:
    """Volver a grabar arregla lo primero pero no lo segundo, asi que el
    usuario tiene que poder distinguirlos."""
    fake_recognition.error = RecognitionError(
        "Se han agotado las peticiones de AudD. Amplia el plan en dashboard.audd.io."
    )
    respuesta = enviar(client, headers(client))
    assert respuesta.status_code == 502
    assert "agotado" in respuesta.json()["detail"]


def test_si_youtube_falla_la_identificacion_sigue_valiendo(
    client: TestClient, admin_user, fake_recognition, fake_downloader
) -> None:
    from app.services.downloader import DownloadError

    fake_downloader.error = DownloadError("YouTube pide verificacion.")
    datos = enviar(client, headers(client)).json()
    assert datos["recognized"] is True
    assert datos["title"] == "Song 2"
    assert datos["candidates"] == []


# --- Limites ----------------------------------------------------------------


def test_audio_vacio(client: TestClient, admin_user, fake_recognition) -> None:
    respuesta = enviar(client, headers(client), contenido=b"")
    assert respuesta.status_code == 400


def test_audio_demasiado_grande(
    client: TestClient, admin_user, fake_recognition, monkeypatch
) -> None:
    from app.core.config import settings

    monkeypatch.setattr(settings, "recognition_max_upload_bytes", 100)
    respuesta = enviar(client, headers(client), contenido=b"x" * 500)
    assert respuesta.status_code == 413
    assert fake_recognition.recibido == []  # no se gasta una peticion de AudD


def test_de_reconocida_a_la_biblioteca(
    client: TestClient, admin_user, fake_recognition, fake_downloader
) -> None:
    """El flujo completo: grabar, identificar, elegir y descargar."""
    h = headers(client)
    candidatos = enviar(client, h).json()["candidates"]
    elegido = next(c for c in candidatos if not c["too_long"])

    alta = client.post("/tracks/from-url", json={"url": elegido["url"]}, headers=h)
    assert alta.status_code == 202
    track = client.get(f"/tracks/{alta.json()['id']}", headers=h).json()
    assert track["status"] == "ready"
    assert track["title"] == "Song 2"
