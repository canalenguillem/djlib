"""Escuchas: lo que suena en el reproductor y lo que se pincha en el mezclador,
contado por separado."""

from datetime import timedelta

from fastapi.testclient import TestClient

from app.core.time import utcnow
from app.models.listen import Listen
from tests.conftest import ADMIN_PASSWORD, USER_PASSWORD, auth_headers, login
from tests.test_crates import crear_track


def escuchar(client: TestClient, h: dict, track_id: int, source: str) -> None:
    r = client.post("/listens", json={"track_id": track_id, "source": source}, headers=h)
    assert r.status_code == 204, r.text


def test_cuenta_por_usuario_y_separa_reproductor_de_mezclas(
    client: TestClient, admin_user, normal_user, fake_downloader, db
) -> None:
    admin = auth_headers(login(client, "enguillem", ADMIN_PASSWORD)["access_token"])
    pepe = auth_headers(login(client, "dj_pepe", USER_PASSWORD)["access_token"])
    uno = crear_track(client, admin, "aaaaaaaaaaa", "Primera", fake_downloader)
    dos = crear_track(client, admin, "bbbbbbbbbbb", "Segunda", fake_downloader)

    for _ in range(3):
        escuchar(client, pepe, uno, "player")
    escuchar(client, pepe, dos, "mixer")
    escuchar(client, pepe, dos, "mixer")
    escuchar(client, admin, uno, "mixer")

    # Una escucha de hace un mes no entra en la ultima semana
    vieja = Listen(user_id=normal_user.id, track_id=dos, source="player")
    vieja.created_at = utcnow() - timedelta(days=30)
    db.add(vieja)
    db.commit()

    stats = client.get("/listens/stats", headers=admin).json()
    usuarios = {u["username"]: u for u in stats["users"]}
    assert usuarios["dj_pepe"]["total"] == {"player": 4, "mixer": 2}
    assert usuarios["dj_pepe"]["last_7_days"] == {"player": 3, "mixer": 2}
    assert usuarios["enguillem"]["total"] == {"player": 0, "mixer": 1}
    # El que mas escucha va primero
    assert stats["users"][0]["username"] == "dj_pepe"

    top = stats["top_tracks"]
    assert [t["title"] for t in top] == ["Primera", "Segunda"]
    assert top[0]["player"] == 3 and top[0]["mixer"] == 1


def test_solo_el_admin_ve_las_estadisticas(client: TestClient, normal_user) -> None:
    pepe = auth_headers(login(client, "dj_pepe", USER_PASSWORD)["access_token"])
    assert client.get("/listens/stats", headers=pepe).status_code == 403


def test_cancion_que_no_existe_o_origen_raro(client: TestClient, admin_user, fake_downloader) -> None:
    h = auth_headers(login(client, "enguillem", ADMIN_PASSWORD)["access_token"])
    assert client.post("/listens", json={"track_id": 999, "source": "player"}, headers=h).status_code == 404
    uno = crear_track(client, h, "aaaaaaaaaaa", "Primera", fake_downloader)
    assert client.post("/listens", json={"track_id": uno, "source": "radio"}, headers=h).status_code == 422
    assert client.post("/listens", json={"track_id": uno, "source": "player"}).status_code == 401
