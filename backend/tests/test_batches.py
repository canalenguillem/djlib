"""Tandas de descarga que el servidor hace solo, sin el navegador abierto."""

from fastapi.testclient import TestClient

from app.models.batch import BatchItemStatus, DownloadBatchItem
from app.services import batch_service
from app.services.downloader import DownloadError
from tests.conftest import (
    ADMIN_PASSWORD,
    USER_PASSWORD,
    TestingSessionLocal,
    auth_headers,
    login,
)

URL = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"


def headers(client: TestClient) -> dict[str, str]:
    return auth_headers(login(client, "enguillem", ADMIN_PASSWORD)["access_token"])


def crear_crate(client: TestClient, h: dict, nombre: str = "Spotify") -> int:
    return client.post("/crates", json={"name": nombre}, headers=h).json()["id"]


def crear_tanda(client: TestClient, h: dict, crate_id: int | None, canciones=None) -> dict:
    respuesta = client.post(
        "/batches",
        json={
            "name": "Spotify: Warm-up",
            "crate_id": crate_id,
            "songs": canciones or [{"title": "Song 2", "artist": "Blur"}],
        },
        headers=h,
    )
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()


def trabajar() -> int:
    """Lo que hacen los hilos del servidor, aqui de una vez y sin hilos."""
    hechas = 0
    while batch_service.process_next(TestingSessionLocal):
        hechas += 1
    return hechas


def test_descarga_y_mete_en_el_crate_sin_el_navegador(
    client: TestClient, admin_user, fake_downloader
) -> None:
    h = headers(client)
    crate = crear_crate(client, h)
    tanda = crear_tanda(client, h, crate)
    assert tanda["status"] == "active"
    assert tanda["counts"] == {"pending": 1}

    assert trabajar() == 1

    tanda = client.get(f"/batches/{tanda['id']}", headers=h).json()
    assert tanda["status"] == "done"
    item = tanda["items"][0]
    assert item["status"] == "done"
    # Se salta el mix de 42 minutos que YouTube da primero
    assert item["video_title"] == "Blur - Song 2 (Official Music Video)"
    detalle = client.get(f"/crates/{crate}", headers=h).json()
    assert [t["id"] for t in detalle["tracks"]] == [item["track_id"]]
    assert detalle["tracks"][0]["status"] == "ready"


def test_la_que_ya_estaba_solo_entra_en_el_crate(
    client: TestClient, admin_user, fake_downloader
) -> None:
    h = headers(client)
    client.post("/tracks/from-url", json={"url": URL}, headers=h)
    descargas = len(fake_downloader.downloaded_queries)
    crate = crear_crate(client, h)
    tanda = crear_tanda(client, h, crate)

    trabajar()

    item = client.get(f"/batches/{tanda['id']}", headers=h).json()["items"][0]
    assert item["status"] == "already"
    assert len(fake_downloader.downloaded_queries) == descargas  # no la vuelve a bajar
    assert len(client.get(f"/crates/{crate}", headers=h).json()["tracks"]) == 1


def test_sin_resultado_valido_y_con_error_sigue_con_las_demas(
    client: TestClient, admin_user, fake_downloader
) -> None:
    h = headers(client)
    fake_downloader.results = fake_downloader.results[:1]  # solo el mix largo
    tanda = crear_tanda(
        client, h, None, [{"title": "Rara", "artist": None}, {"title": "Otra", "artist": "X"}]
    )
    trabajar()
    datos = client.get(f"/batches/{tanda['id']}", headers=h).json()
    assert [i["status"] for i in datos["items"]] == ["not_found", "not_found"]
    assert datos["status"] == "done"

    fake_downloader.error = DownloadError("YouTube no responde.")
    tanda = crear_tanda(client, h, None)
    trabajar()
    item = client.get(f"/batches/{tanda['id']}", headers=h).json()["items"][0]
    assert item["status"] == "error"
    assert item["message"] == "YouTube no responde."


def test_cancelar_deja_sin_hacer_lo_pendiente(
    client: TestClient, admin_user, fake_downloader
) -> None:
    h = headers(client)
    tanda = crear_tanda(client, h, None, [{"title": "Song 2", "artist": "Blur"}] * 3)
    datos = client.post(f"/batches/{tanda['id']}/cancel", headers=h).json()
    assert datos["status"] == "cancelled"
    assert datos["counts"] == {"cancelled": 3}
    assert trabajar() == 0


def test_un_reinicio_devuelve_a_la_cola_lo_que_estaba_en_curso(
    client: TestClient, admin_user, fake_downloader
) -> None:
    h = headers(client)
    tanda = crear_tanda(client, h, None)
    # Como si el servidor se hubiera parado buscandola
    assert batch_service._reclamar(TestingSessionLocal) is not None
    # Mientras, el listado dice cual esta en curso
    resumen = client.get("/batches", headers=h).json()[0]
    assert resumen["current"] == ["Blur - Song 2"]
    with TestingSessionLocal() as db:
        assert batch_service.recover(db) == 1
        item = db.get(DownloadBatchItem, tanda["items"][0]["id"])
        assert item.status == BatchItemStatus.pending

    trabajar()
    assert client.get(f"/batches/{tanda['id']}", headers=h).json()["status"] == "done"


def test_las_tandas_son_de_quien_las_crea(
    client: TestClient, admin_user, normal_user, fake_downloader
) -> None:
    tanda = crear_tanda(client, headers(client), None)
    otro = auth_headers(login(client, "dj_pepe", USER_PASSWORD)["access_token"])
    assert client.get(f"/batches/{tanda['id']}", headers=otro).status_code == 404
    assert client.get("/batches", headers=otro).json() == []
    assert [t["id"] for t in client.get("/batches", headers=headers(client)).json()] == [tanda["id"]]


def test_crate_inexistente_se_rechaza(client: TestClient, admin_user) -> None:
    respuesta = client.post(
        "/batches",
        json={"name": "x", "crate_id": 999, "songs": [{"title": "a"}]},
        headers=headers(client),
    )
    assert respuesta.status_code == 404
