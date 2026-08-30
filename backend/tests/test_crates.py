"""Crates: selecciones con nombre y orden propio.

Lo que los diferencia de un filtro es que no cambian solos y que el orden lo
decide el usuario, asi que casi todo lo que se prueba aqui es el orden.
"""

from fastapi.testclient import TestClient

from tests.conftest import ADMIN_PASSWORD, USER_PASSWORD, auth_headers, login


def headers(client: TestClient) -> dict[str, str]:
    return auth_headers(login(client, "enguillem", ADMIN_PASSWORD)["access_token"])


def crear_track(client: TestClient, h: dict, video_id: str, titulo: str, fake_downloader) -> int:
    """Descarga una cancion de mentira y devuelve su id."""
    fake_downloader.info = fake_downloader.info.__class__(
        video_id=video_id,
        title=titulo,
        artist="Blur",
        duration_seconds=180,
        webpage_url=f"https://www.youtube.com/watch?v={video_id}",
        site="youtube",
    )
    respuesta = client.post(
        "/tracks/from-url",
        json={"url": f"https://www.youtube.com/watch?v={video_id}"},
        headers=h,
    )
    return respuesta.json()["id"]


def tres_canciones(client: TestClient, h: dict, fake_downloader) -> list[int]:
    return [
        crear_track(client, h, "aaaaaaaaaaa", "Primera", fake_downloader),
        crear_track(client, h, "bbbbbbbbbbb", "Segunda", fake_downloader),
        crear_track(client, h, "ccccccccccc", "Tercera", fake_downloader),
    ]


def titulos(crate: dict) -> list[str]:
    return [t["title"] for t in crate["tracks"]]


# --- Acceso -----------------------------------------------------------------


def test_crates_requiere_sesion(client: TestClient) -> None:
    assert client.get("/crates").status_code == 401


def test_cualquier_usuario_autenticado_los_usa(
    client: TestClient, normal_user, fake_downloader
) -> None:
    h = auth_headers(login(client, "dj_pepe", USER_PASSWORD)["access_token"])
    assert client.post("/crates", json={"name": "Warm-up"}, headers=h).status_code == 201


# --- Alta -------------------------------------------------------------------


def test_crear_crate_vacio(client: TestClient, admin_user) -> None:
    respuesta = client.post(
        "/crates",
        json={"name": "Warm-up britanico", "description": "Para empezar la noche"},
        headers=headers(client),
    )
    assert respuesta.status_code == 201
    crate = respuesta.json()
    assert crate["name"] == "Warm-up britanico"
    assert crate["slug"] == "warm-up-britanico"
    assert crate["track_count"] == 0
    assert crate["total_seconds"] == 0


def test_crear_crate_con_lo_que_hay_filtrado(
    client: TestClient, admin_user, fake_downloader
) -> None:
    """El caso principal: filtras en la biblioteca y guardas el resultado."""
    h = headers(client)
    ids = tres_canciones(client, h, fake_downloader)

    crate = client.post(
        "/crates", json={"name": "Sabado", "track_ids": ids}, headers=h
    ).json()
    assert titulos(crate) == ["Primera", "Segunda", "Tercera"]
    assert crate["track_count"] == 3
    assert crate["total_seconds"] == 540  # tres de tres minutos


def test_nombres_equivalentes_dan_conflicto(client: TestClient, admin_user) -> None:
    h = headers(client)
    client.post("/crates", json={"name": "Warm-up"}, headers=h)
    repetido = client.post("/crates", json={"name": "  WARM-UP "}, headers=h)
    assert repetido.status_code == 409


def test_una_cancion_a_medio_descargar_no_entra(
    client: TestClient, admin_user, fake_downloader
) -> None:
    """Un crate con descargas a medias no sirve para pinchar."""
    from app.services.downloader import DownloadError

    h = headers(client)
    buena = crear_track(client, h, "aaaaaaaaaaa", "Buena", fake_downloader)
    fake_downloader.error = DownloadError("Video privado.")
    fallida = crear_track(client, h, "zzzzzzzzzzz", "Fallida", fake_downloader)

    crate = client.post(
        "/crates", json={"name": "Sabado", "track_ids": [buena, fallida]}, headers=h
    ).json()
    assert titulos(crate) == ["Buena"]


# --- Contenido y orden ------------------------------------------------------


def test_anadir_y_quitar_canciones(client: TestClient, admin_user, fake_downloader) -> None:
    h = headers(client)
    ids = tres_canciones(client, h, fake_downloader)
    crate_id = client.post("/crates", json={"name": "Sabado"}, headers=h).json()["id"]

    for track_id in ids:
        client.post(f"/crates/{crate_id}/tracks", json={"track_id": track_id}, headers=h)
    crate = client.get(f"/crates/{crate_id}", headers=h).json()
    assert titulos(crate) == ["Primera", "Segunda", "Tercera"]

    quitada = client.delete(f"/crates/{crate_id}/tracks/{ids[1]}", headers=h)
    assert quitada.status_code == 200
    assert titulos(quitada.json()) == ["Primera", "Tercera"]


def test_no_se_repite_una_cancion_en_el_mismo_crate(
    client: TestClient, admin_user, fake_downloader
) -> None:
    h = headers(client)
    ids = tres_canciones(client, h, fake_downloader)
    crate_id = client.post(
        "/crates", json={"name": "Sabado", "track_ids": ids[:1]}, headers=h
    ).json()["id"]

    repetida = client.post(
        f"/crates/{crate_id}/tracks", json={"track_id": ids[0]}, headers=h
    )
    assert repetida.status_code == 409


def test_reordenar(client: TestClient, admin_user, fake_downloader) -> None:
    h = headers(client)
    ids = tres_canciones(client, h, fake_downloader)
    crate_id = client.post(
        "/crates", json={"name": "Sabado", "track_ids": ids}, headers=h
    ).json()["id"]

    # La tercera pasa a abrir el set
    nuevo_orden = [ids[2], ids[0], ids[1]]
    respuesta = client.put(f"/crates/{crate_id}/order", json={"track_ids": nuevo_orden}, headers=h)
    assert respuesta.status_code == 200
    assert titulos(respuesta.json()) == ["Tercera", "Primera", "Segunda"]

    # Y se queda asi
    assert titulos(client.get(f"/crates/{crate_id}", headers=h).json()) == [
        "Tercera", "Primera", "Segunda",
    ]


def test_reordenar_exige_la_lista_completa(
    client: TestClient, admin_user, fake_downloader
) -> None:
    """Se manda la lista entera, no movimientos sueltos: si falta alguna se
    rechaza en vez de dejar el orden a medias."""
    h = headers(client)
    ids = tres_canciones(client, h, fake_downloader)
    crate_id = client.post(
        "/crates", json={"name": "Sabado", "track_ids": ids}, headers=h
    ).json()["id"]

    incompleta = client.put(f"/crates/{crate_id}/order", json={"track_ids": ids[:2]}, headers=h)
    assert incompleta.status_code == 400
    assert "Falta indicar la posicion" in incompleta.json()["detail"]

    intrusa = client.put(
        f"/crates/{crate_id}/order", json={"track_ids": [*ids, 9999]}, headers=h
    )
    assert intrusa.status_code == 400

    # El orden original sigue intacto tras los dos intentos fallidos
    assert titulos(client.get(f"/crates/{crate_id}", headers=h).json()) == [
        "Primera", "Segunda", "Tercera",
    ]


def test_al_quitar_una_cancion_las_posiciones_no_dejan_huecos(
    client: TestClient, admin_user, fake_downloader
) -> None:
    h = headers(client)
    ids = tres_canciones(client, h, fake_downloader)
    crate_id = client.post(
        "/crates", json={"name": "Sabado", "track_ids": ids}, headers=h
    ).json()["id"]

    client.delete(f"/crates/{crate_id}/tracks/{ids[0]}", headers=h)
    # Reordenar despues tiene que seguir funcionando, que es donde se notaria
    # un hueco o un empate en las posiciones
    respuesta = client.put(
        f"/crates/{crate_id}/order", json={"track_ids": [ids[2], ids[1]]}, headers=h
    )
    assert respuesta.status_code == 200
    assert titulos(respuesta.json()) == ["Tercera", "Segunda"]


# --- Independencia del filtro y de la biblioteca ----------------------------


def test_el_crate_no_cambia_al_cambiar_las_etiquetas(
    client: TestClient, admin_user, fake_downloader
) -> None:
    """Es la diferencia con un filtro: una vez guardado, es tuyo."""
    h = headers(client)
    ids = tres_canciones(client, h, fake_downloader)
    tag = client.post("/tags", json={"kind": "mood", "name": "Chill"}, headers=h).json()
    client.put(f"/tracks/{ids[0]}/tags", json={"tag_ids": [tag["id"]]}, headers=h)

    crate_id = client.post(
        "/crates", json={"name": "Sabado", "track_ids": ids}, headers=h
    ).json()["id"]

    client.put(f"/tracks/{ids[0]}/tags", json={"tag_ids": []}, headers=h)
    client.delete(f"/tags/{tag['id']}", headers=h)

    assert titulos(client.get(f"/crates/{crate_id}", headers=h).json()) == [
        "Primera", "Segunda", "Tercera",
    ]


def test_borrar_una_cancion_la_saca_de_los_crates(
    client: TestClient, admin_user, fake_downloader
) -> None:
    h = headers(client)
    ids = tres_canciones(client, h, fake_downloader)
    crate_id = client.post(
        "/crates", json={"name": "Sabado", "track_ids": ids}, headers=h
    ).json()["id"]

    client.delete(f"/tracks/{ids[1]}", headers=h)
    crate = client.get(f"/crates/{crate_id}", headers=h).json()
    assert titulos(crate) == ["Primera", "Tercera"]
    assert crate["track_count"] == 2


def test_borrar_un_crate_no_toca_las_canciones(
    client: TestClient, admin_user, fake_downloader
) -> None:
    h = headers(client)
    ids = tres_canciones(client, h, fake_downloader)
    crate_id = client.post(
        "/crates", json={"name": "Sabado", "track_ids": ids}, headers=h
    ).json()["id"]

    assert client.delete(f"/crates/{crate_id}", headers=h).status_code == 204
    assert client.get(f"/crates/{crate_id}", headers=h).status_code == 404
    assert client.get("/tracks", headers=h).json()["total"] == 3


def test_renombrar_crate(client: TestClient, admin_user) -> None:
    h = headers(client)
    crate_id = client.post("/crates", json={"name": "Sabdo"}, headers=h).json()["id"]
    respuesta = client.patch(f"/crates/{crate_id}", json={"name": "Sabado"}, headers=h)
    assert respuesta.status_code == 200
    assert respuesta.json()["slug"] == "sabado"


def test_listado_de_crates(client: TestClient, admin_user, fake_downloader) -> None:
    h = headers(client)
    ids = tres_canciones(client, h, fake_downloader)
    client.post("/crates", json={"name": "Cierre"}, headers=h)
    client.post("/crates", json={"name": "Apertura", "track_ids": ids}, headers=h)

    listado = client.get("/crates", headers=h).json()
    assert [c["name"] for c in listado] == ["Apertura", "Cierre"]
    assert listado[0]["track_count"] == 3
    assert listado[0]["total_seconds"] == 540
