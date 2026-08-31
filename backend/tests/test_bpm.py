"""Deteccion de tempo: lo ultimo que pedia el briefing."""

import pytest
from fastapi.testclient import TestClient

from app.services import bpm as bpm_service
from tests.conftest import ADMIN_PASSWORD, auth_headers, login


def headers(client: TestClient) -> dict[str, str]:
    return auth_headers(login(client, "enguillem", ADMIN_PASSWORD)["access_token"])


def crear(client: TestClient, h: dict, video_id: str, titulo: str, fake_downloader) -> int:
    fake_downloader.info = fake_downloader.info.__class__(
        video_id=video_id, title=titulo, artist="Blur", duration_seconds=180,
        webpage_url=f"https://www.youtube.com/watch?v={video_id}", site="youtube",
    )
    return client.post(
        "/tracks/from-url",
        json={"url": f"https://www.youtube.com/watch?v={video_id}"},
        headers=h,
    ).json()["id"]


# --- Correccion de octava ---------------------------------------------------


@pytest.mark.parametrize(
    ("detectado", "esperado"),
    [
        (128.0, 128),   # dentro de la horquilla, se respeta
        (127.9, 128),   # se redondea
        (64.0, 128),    # mitad de tempo: se dobla
        (43.0, 86),     # mitad: se dobla una vez y ya entra en la horquilla
        (32.0, 128),    # un cuarto: se dobla dos veces
        (300.0, 150),   # doble: se parte
        (70.0, 70),     # justo en el limite inferior
        (180.0, 180),   # justo en el limite superior
    ],
)
def test_los_errores_de_octava_se_corrigen(detectado: float, esperado: int) -> None:
    """Un detector puede devolver la mitad o el doble del tempo real; se lleva
    el valor a la horquilla donde vive la musica de baile."""
    assert bpm_service.normalize(detectado) == esperado


# --- En la tuberia ----------------------------------------------------------


def test_al_descargar_se_mide_el_tempo(
    client: TestClient, admin_user, fake_downloader, fake_bpm
) -> None:
    h = headers(client)
    track_id = crear(client, h, "aaaaaaaaaaa", "Tema", fake_downloader)
    assert client.get(f"/tracks/{track_id}", headers=h).json()["bpm"] == 128
    assert len(fake_bpm.analizados) == 1


def test_si_no_se_puede_medir_se_queda_vacio(
    client: TestClient, admin_user, fake_downloader, fake_bpm
) -> None:
    fake_bpm.valor = None
    h = headers(client)
    track_id = crear(client, h, "aaaaaaaaaaa", "Tema", fake_downloader)
    assert client.get(f"/tracks/{track_id}", headers=h).json()["bpm"] is None


def test_el_bpm_corregido_a_mano_no_se_pisa(
    client: TestClient, admin_user, fake_downloader, fake_bpm
) -> None:
    """El usuario sabe mejor que ningun detector a que velocidad va su musica."""
    h = headers(client)
    track_id = crear(client, h, "aaaaaaaaaaa", "Tema", fake_downloader)
    client.patch(f"/tracks/{track_id}", json={"bpm": 174}, headers=h)

    fake_bpm.valor = 128
    fake_bpm.analizados.clear()
    from app.db.session import SessionLocal
    from app.services import track_service

    track_service.analyze_bpm(SessionLocal, track_id)  # sin forzar
    assert client.get(f"/tracks/{track_id}", headers=h).json()["bpm"] == 174


def test_volver_a_analizar_a_peticion_si_pisa(
    client: TestClient, admin_user, fake_downloader, fake_bpm
) -> None:
    h = headers(client)
    track_id = crear(client, h, "aaaaaaaaaaa", "Tema", fake_downloader)
    client.patch(f"/tracks/{track_id}", json={"bpm": 90}, headers=h)

    fake_bpm.valor = 124
    respuesta = client.post(f"/tracks/{track_id}/analyze", headers=h)
    assert respuesta.status_code == 200
    assert respuesta.json()["bpm"] == 124


def test_no_se_analiza_lo_que_no_esta_descargado(
    client: TestClient, admin_user, fake_downloader, fake_bpm
) -> None:
    from app.services.downloader import DownloadError

    fake_downloader.error = DownloadError("Video privado.")
    h = headers(client)
    track_id = crear(client, h, "zzzzzzzzzzz", "Fallida", fake_downloader)
    assert client.post(f"/tracks/{track_id}/analyze", headers=h).status_code == 409


# --- Busqueda por tempo -----------------------------------------------------


def test_filtrar_por_horquilla_de_tempo(
    client: TestClient, admin_user, fake_downloader, fake_bpm
) -> None:
    """Como se busca un tema para encajar en una mezcla: algo entre 122 y 126."""
    h = headers(client)
    for video, titulo, valor in (
        ("aaaaaaaaaaa", "Lenta", 98),
        ("bbbbbbbbbbb", "Media", 124),
        ("ccccccccccc", "Rapida", 150),
    ):
        fake_bpm.valor = valor
        crear(client, h, video, titulo, fake_downloader)

    encaja = client.get("/tracks?bpm_min=122&bpm_max=126", headers=h).json()
    assert [t["title"] for t in encaja["items"]] == ["Media"]

    rapidas = client.get("/tracks?bpm_min=140", headers=h).json()
    assert [t["title"] for t in rapidas["items"]] == ["Rapida"]


def test_ordenar_por_tempo(client: TestClient, admin_user, fake_downloader, fake_bpm) -> None:
    h = headers(client)
    for video, titulo, valor in (
        ("aaaaaaaaaaa", "Rapida", 150),
        ("bbbbbbbbbbb", "Lenta", 98),
        ("ccccccccccc", "Sin medir", None),
    ):
        fake_bpm.valor = valor
        crear(client, h, video, titulo, fake_downloader)

    ordenadas = client.get("/tracks?sort=bpm", headers=h).json()
    # De menos a mas, y las que no tienen tempo al final
    assert [t["title"] for t in ordenadas["items"]] == ["Lenta", "Rapida", "Sin medir"]
