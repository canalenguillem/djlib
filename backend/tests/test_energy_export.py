"""Energia de 1 a 5 y exportacion de un crate a un zip."""

import io
import zipfile

from fastapi.testclient import TestClient

from tests.conftest import ADMIN_PASSWORD, auth_headers, login


def headers(client: TestClient) -> dict[str, str]:
    return auth_headers(login(client, "enguillem", ADMIN_PASSWORD)["access_token"])


def crear_track(client: TestClient, h: dict, video_id: str, titulo: str, fake_downloader) -> int:
    fake_downloader.info = fake_downloader.info.__class__(
        video_id=video_id,
        title=titulo,
        artist="Blur",
        duration_seconds=180,
        webpage_url=f"https://www.youtube.com/watch?v={video_id}",
        site="youtube",
    )
    return client.post(
        "/tracks/from-url",
        json={"url": f"https://www.youtube.com/watch?v={video_id}"},
        headers=h,
    ).json()["id"]


# --- Energia ----------------------------------------------------------------


def test_asignar_energia(client: TestClient, admin_user, fake_downloader) -> None:
    h = headers(client)
    track_id = crear_track(client, h, "aaaaaaaaaaa", "Tranquila", fake_downloader)

    respuesta = client.patch(f"/tracks/{track_id}", json={"energy": 2}, headers=h)
    assert respuesta.status_code == 200
    assert respuesta.json()["energy"] == 2


def test_la_energia_va_de_1_a_5(client: TestClient, admin_user, fake_downloader) -> None:
    h = headers(client)
    track_id = crear_track(client, h, "aaaaaaaaaaa", "Tema", fake_downloader)
    for valor in (0, 6, -1):
        assert client.patch(f"/tracks/{track_id}", json={"energy": valor}, headers=h).status_code == 422


def test_filtrar_por_energia(client: TestClient, admin_user, fake_downloader) -> None:
    """El caso real: dame los temas de pico para el final de la noche."""
    h = headers(client)
    suave = crear_track(client, h, "aaaaaaaaaaa", "Warm up", fake_downloader)
    medio = crear_track(client, h, "bbbbbbbbbbb", "Medio", fake_downloader)
    pico = crear_track(client, h, "ccccccccccc", "Pico", fake_downloader)
    client.patch(f"/tracks/{suave}", json={"energy": 1}, headers=h)
    client.patch(f"/tracks/{medio}", json={"energy": 3}, headers=h)
    client.patch(f"/tracks/{pico}", json={"energy": 5}, headers=h)

    solo_pico = client.get("/tracks?energy_min=4", headers=h).json()
    assert [t["title"] for t in solo_pico["items"]] == ["Pico"]

    intermedios = client.get("/tracks?energy_min=2&energy_max=4", headers=h).json()
    assert [t["title"] for t in intermedios["items"]] == ["Medio"]


def test_ordenar_por_energia(client: TestClient, admin_user, fake_downloader) -> None:
    """Para montar la curva de la noche: de menos a mas."""
    h = headers(client)
    a = crear_track(client, h, "aaaaaaaaaaa", "Cinco", fake_downloader)
    b = crear_track(client, h, "bbbbbbbbbbb", "Uno", fake_downloader)
    c = crear_track(client, h, "ccccccccccc", "Tres", fake_downloader)
    client.patch(f"/tracks/{a}", json={"energy": 5}, headers=h)
    client.patch(f"/tracks/{b}", json={"energy": 1}, headers=h)
    client.patch(f"/tracks/{c}", json={"energy": 3}, headers=h)

    ascendente = client.get("/tracks?sort=energy_asc", headers=h).json()
    assert [t["title"] for t in ascendente["items"]] == ["Uno", "Tres", "Cinco"]

    descendente = client.get("/tracks?sort=energy", headers=h).json()
    assert [t["title"] for t in descendente["items"]] == ["Cinco", "Tres", "Uno"]


def test_las_canciones_sin_energia_van_al_final(
    client: TestClient, admin_user, fake_downloader
) -> None:
    h = headers(client)
    con = crear_track(client, h, "aaaaaaaaaaa", "Con energia", fake_downloader)
    crear_track(client, h, "bbbbbbbbbbb", "Sin energia", fake_downloader)
    client.patch(f"/tracks/{con}", json={"energy": 3}, headers=h)

    ordenados = client.get("/tracks?sort=energy", headers=h).json()
    assert [t["title"] for t in ordenados["items"]] == ["Con energia", "Sin energia"]


# --- Exportar un crate ------------------------------------------------------


def test_exportar_un_crate_a_zip(client: TestClient, admin_user, fake_downloader) -> None:
    h = headers(client)
    ids = [
        crear_track(client, h, "aaaaaaaaaaa", "Primera", fake_downloader),
        crear_track(client, h, "bbbbbbbbbbb", "Segunda", fake_downloader),
    ]
    crate_id = client.post(
        "/crates", json={"name": "Sabado", "track_ids": ids}, headers=h
    ).json()["id"]

    respuesta = client.get(f"/crates/{crate_id}/export", headers=h)
    assert respuesta.status_code == 200
    assert respuesta.headers["content-type"] == "application/zip"
    assert "Sabado.zip" in respuesta.headers["content-disposition"]

    with zipfile.ZipFile(io.BytesIO(respuesta.content)) as zf:
        nombres = zf.namelist()
        # Numerados en el orden del set, para que el USB los muestre asi
        assert nombres == ["01 - Blur - Primera.m4a", "02 - Blur - Segunda.m4a"]
        assert zf.read(nombres[0]) != b""


def test_el_zip_respeta_el_orden_del_crate(
    client: TestClient, admin_user, fake_downloader
) -> None:
    h = headers(client)
    ids = [
        crear_track(client, h, "aaaaaaaaaaa", "Primera", fake_downloader),
        crear_track(client, h, "bbbbbbbbbbb", "Segunda", fake_downloader),
    ]
    crate_id = client.post(
        "/crates", json={"name": "Sabado", "track_ids": ids}, headers=h
    ).json()["id"]
    client.put(f"/crates/{crate_id}/order", json={"track_ids": [ids[1], ids[0]]}, headers=h)

    respuesta = client.get(f"/crates/{crate_id}/export", headers=h)
    with zipfile.ZipFile(io.BytesIO(respuesta.content)) as zf:
        assert zf.namelist() == ["01 - Blur - Segunda.m4a", "02 - Blur - Primera.m4a"]


def test_exportar_un_crate_vacio_da_404(client: TestClient, admin_user) -> None:
    h = headers(client)
    crate_id = client.post("/crates", json={"name": "Vacio"}, headers=h).json()["id"]
    assert client.get(f"/crates/{crate_id}/export", headers=h).status_code == 404


def test_exportar_requiere_sesion(client: TestClient) -> None:
    assert client.get("/crates/1/export").status_code == 401
