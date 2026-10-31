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
