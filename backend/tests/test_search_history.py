"""Historial de busquedas en YouTube."""

from fastapi.testclient import TestClient

from tests.conftest import USER_PASSWORD, auth_headers, login
from tests.test_batches import headers


def buscar(client: TestClient, h: dict, **cuerpo) -> None:
    assert client.post("/tracks/search/preview", json=cuerpo, headers=h).status_code == 200


def test_guarda_las_busquedas_sin_repetir(client: TestClient, admin_user, normal_user, fake_downloader) -> None:
    h = headers(client)
    buscar(client, h, title="Song 2", artist="Blur")
    buscar(client, h, artist="Kennan", version="mashup")
    buscar(client, h, title="Song 2 ", artist="Blur")

    historial = client.get("/tracks/search/history", headers=h).json()
    assert [(b["title"], b["artist"], b["version"]) for b in historial] == [
        ("Song 2", "Blur", None),
        (None, "Kennan", "mashup"),
    ]
    assert historial[0]["results"] == 2

    # Cada uno ve las suyas
    otro = auth_headers(login(client, "dj_pepe", USER_PASSWORD)["access_token"])
    assert client.get("/tracks/search/history", headers=otro).json() == []

    assert client.delete("/tracks/search/history", headers=h).status_code == 204
    assert client.get("/tracks/search/history", headers=h).json() == []


def test_soundcloud_busca_alli_y_va_aparte(client: TestClient, admin_user, fake_downloader) -> None:
    h = headers(client)
    buscar(client, h, artist="Charly Chaser", source="soundcloud")
    buscar(client, h, title="Song 2", artist="Blur")
    assert fake_downloader.sitios == ["soundcloud", "youtube"]

    solo_sc = client.get("/tracks/search/history", params={"source": "soundcloud"}, headers=h).json()
    assert [(b["artist"], b["source"]) for b in solo_sc] == [("Charly Chaser", "soundcloud")]
    assert len(client.get("/tracks/search/history", headers=h).json()) == 2


def test_enlace_lista_lo_que_hay(client: TestClient, admin_user, fake_downloader, monkeypatch) -> None:
    from app.services import downloader

    pedidos: list[str] = []

    def list_link(url: str):
        pedidos.append(url)
        return fake_downloader.results

    monkeypatch.setattr(downloader, "list_link", list_link)
    r = client.post(
        "/tracks/link/preview", json={"url": "https://soundcloud.com/x/sets/pack"}, headers=headers(client)
    )
    assert r.status_code == 200
    datos = r.json()
    assert pedidos == ["https://soundcloud.com/x/sets/pack"]
    assert [c["too_long"] for c in datos["candidates"]] == [True, False]
