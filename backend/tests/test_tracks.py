from pathlib import Path

from fastapi.testclient import TestClient

from app.services.downloader import DownloadError
from tests.conftest import ADMIN_PASSWORD, USER_PASSWORD, auth_headers, login

URL = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"


def headers(client: TestClient) -> dict[str, str]:
    return auth_headers(login(client, "enguillem", ADMIN_PASSWORD)["access_token"])


def add_url(client: TestClient, h: dict[str, str], url: str = URL):
    return client.post("/tracks/from-url", json={"url": url}, headers=h)


# --- Acceso -----------------------------------------------------------------


def test_biblioteca_requiere_sesion(client: TestClient) -> None:
    assert client.get("/tracks").status_code == 401
    assert client.post("/tracks/from-url", json={"url": URL}).status_code == 401


def test_cualquier_usuario_autenticado_puede_anadir(
    client: TestClient, normal_user, fake_downloader
) -> None:
    h = auth_headers(login(client, "dj_pepe", USER_PASSWORD)["access_token"])
    assert add_url(client, h).status_code == 202


# --- Alta por URL -----------------------------------------------------------


def test_alta_por_url_descarga_y_queda_lista(
    client: TestClient, admin_user, fake_downloader, music_dir: Path
) -> None:
    h = headers(client)
    respuesta = add_url(client, h)
    assert respuesta.status_code == 202
    track_id = respuesta.json()["id"]

    # TestClient ejecuta la tarea de fondo antes de devolver el control,
    # asi que al consultar ya esta descargada.
    track = client.get(f"/tracks/{track_id}", headers=h).json()
    assert track["status"] == "ready"
    assert track["title"] == "Song 2"
    assert track["artist_text"] == "Blur"
    assert track["duration_seconds"] == 121
    assert track["source_video_id"] == "dQw4w9WgXcQ"
    assert (music_dir / "dQw4w9WgXcQ.mp3").exists()


def test_url_invalida_da_400(client: TestClient, admin_user, fake_downloader) -> None:
    respuesta = add_url(client, headers(client), url="esto no es una url")
    assert respuesta.status_code == 400


def test_misma_url_dos_veces_da_conflicto(
    client: TestClient, admin_user, fake_downloader
) -> None:
    h = headers(client)
    assert add_url(client, h).status_code == 202
    repetida = add_url(client, h)
    assert repetida.status_code == 409
    assert "ya esta en la biblioteca" in repetida.json()["detail"].lower()


def test_error_de_ytdlp_deja_el_track_en_error(
    client: TestClient, admin_user, fake_downloader
) -> None:
    fake_downloader.error = DownloadError("El video es privado.")
    h = headers(client)
    track_id = add_url(client, h).json()["id"]

    track = client.get(f"/tracks/{track_id}", headers=h).json()
    assert track["status"] == "error"
    assert track["error_message"] == "El video es privado."


def test_video_demasiado_largo_se_rechaza(
    client: TestClient, admin_user, fake_downloader, monkeypatch
) -> None:
    from app.core.config import settings

    monkeypatch.setattr(settings, "max_track_duration_seconds", 60)
    h = headers(client)
    track_id = add_url(client, h).json()["id"]

    track = client.get(f"/tracks/{track_id}", headers=h).json()
    assert track["status"] == "error"
    assert "demasiado" in track["error_message"]
    assert fake_downloader.downloaded_queries == []  # no se gasto la descarga


def test_reintentar_una_descarga_fallida(
    client: TestClient, admin_user, fake_downloader
) -> None:
    fake_downloader.error = DownloadError("Fallo temporal.")
    h = headers(client)
    track_id = add_url(client, h).json()["id"]
    assert client.get(f"/tracks/{track_id}", headers=h).json()["status"] == "error"

    fake_downloader.error = None
    reintento = client.post(f"/tracks/{track_id}/retry", headers=h)
    assert reintento.status_code == 202
    assert client.get(f"/tracks/{track_id}", headers=h).json()["status"] == "ready"


def test_no_se_reintenta_una_descarga_correcta(
    client: TestClient, admin_user, fake_downloader
) -> None:
    h = headers(client)
    track_id = add_url(client, h).json()["id"]
    assert client.post(f"/tracks/{track_id}/retry", headers=h).status_code == 400


# --- Alta por busqueda ------------------------------------------------------


def test_alta_por_titulo_y_artista(client: TestClient, admin_user, fake_downloader) -> None:
    h = headers(client)
    respuesta = client.post(
        "/tracks/search", json={"title": "Song 2", "artist": "Blur"}, headers=h
    )
    assert respuesta.status_code == 202
    # Se piden varios candidatos, no solo el primero, y se busca lo que se pidio
    assert fake_downloader.resolved_queries == ["ytsearch5:Blur - Song 2"]
    assert client.get(f"/tracks/{respuesta.json()['id']}", headers=h).json()["status"] == "ready"


def test_se_descarga_la_url_resuelta_no_la_consulta(
    client: TestClient, admin_user, fake_downloader
) -> None:
    """Repetir la busqueda al descargar podria dar otro resultado distinto del
    que se comprobo, y con varios candidatos bajaria todos."""
    h = headers(client)
    client.post("/tracks/search", json={"title": "Song 2", "artist": "Blur"}, headers=h)
    assert fake_downloader.downloaded_queries == [
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    ]


def test_busqueda_que_apunta_a_un_video_ya_descargado_no_duplica(
    client: TestClient, admin_user, fake_downloader
) -> None:
    h = headers(client)
    add_url(client, h)  # ya tenemos dQw4w9WgXcQ por URL

    # La busqueda resuelve al mismo video: se detecta al conocer el id real.
    respuesta = client.post(
        "/tracks/search", json={"title": "Song Two", "artist": "Blurr"}, headers=h
    )
    track = client.get(f"/tracks/{respuesta.json()['id']}", headers=h).json()
    assert track["status"] == "error"
    assert "ya esta en la biblioteca" in track["error_message"].lower()


def test_busqueda_equivalente_se_deduplica_por_nombre(
    client: TestClient, admin_user, fake_downloader
) -> None:
    h = headers(client)
    client.post("/tracks/search", json={"title": "Song 2", "artist": "Blur"}, headers=h)
    repetida = client.post(
        "/tracks/search", json={"title": "  song  2 ", "artist": "BLUR"}, headers=h
    )
    assert repetida.status_code == 409


# --- Listado y filtros ------------------------------------------------------


def test_listado_con_busqueda_y_filtro_por_etiquetas(
    client: TestClient, admin_user, fake_downloader
) -> None:
    h = headers(client)
    primera = add_url(client, h).json()["id"]

    fake_downloader.info = fake_downloader.info.__class__(
        video_id="abcdefghijk",
        title="Parklife",
        artist="Blur",
        duration_seconds=180,
        webpage_url="https://www.youtube.com/watch?v=abcdefghijk",
        site="youtube",
    )
    segunda = add_url(client, h, url="https://www.youtube.com/watch?v=abcdefghijk").json()["id"]

    chill = client.post("/tags", json={"kind": "mood", "name": "Chill"}, headers=h).json()
    warmup = client.post("/tags", json={"kind": "moment", "name": "Warm-up"}, headers=h).json()

    client.put(f"/tracks/{primera}/tags", json={"tag_ids": [chill["id"], warmup["id"]]}, headers=h)
    client.put(f"/tracks/{segunda}/tags", json={"tag_ids": [chill["id"]]}, headers=h)

    todas = client.get("/tracks", headers=h).json()
    assert todas["total"] == 2

    por_texto = client.get("/tracks?search=parklife", headers=h).json()
    assert [t["id"] for t in por_texto["items"]] == [segunda]

    # Filtro combinado: pide las dos etiquetas a la vez
    combinado = client.get(
        f"/tracks?tag_id={chill['id']}&tag_id={warmup['id']}", headers=h
    ).json()
    assert [t["id"] for t in combinado["items"]] == [primera]

    solo_chill = client.get(f"/tracks?tag_id={chill['id']}", headers=h).json()
    assert solo_chill["total"] == 2


def test_asignar_etiqueta_inexistente_da_400(
    client: TestClient, admin_user, fake_downloader
) -> None:
    h = headers(client)
    track_id = add_url(client, h).json()["id"]
    respuesta = client.put(f"/tracks/{track_id}/tags", json={"tag_ids": [999]}, headers=h)
    assert respuesta.status_code == 400


def test_borrar_una_etiqueta_la_quita_de_las_canciones(
    client: TestClient, admin_user, fake_downloader
) -> None:
    h = headers(client)
    track_id = add_url(client, h).json()["id"]
    tag = client.post("/tags", json={"kind": "mood", "name": "Chill"}, headers=h).json()
    client.put(f"/tracks/{track_id}/tags", json={"tag_ids": [tag["id"]]}, headers=h)

    client.delete(f"/tags/{tag['id']}", headers=h)
    assert client.get(f"/tracks/{track_id}", headers=h).json()["tags"] == []


# --- Fichero, edicion y borrado ---------------------------------------------


def test_descargar_el_mp3(client: TestClient, admin_user, fake_downloader) -> None:
    h = headers(client)
    track_id = add_url(client, h).json()["id"]

    fichero = client.get(f"/tracks/{track_id}/file", headers=h)
    assert fichero.status_code == 200
    assert fichero.headers["content-type"] == "audio/mpeg"
    assert fichero.content == b"ID3fake-mp3-para-tests"


def test_el_fichero_de_una_descarga_fallida_da_409(
    client: TestClient, admin_user, fake_downloader
) -> None:
    fake_downloader.error = DownloadError("El video es privado.")
    h = headers(client)
    track_id = add_url(client, h).json()["id"]
    assert client.get(f"/tracks/{track_id}/file", headers=h).status_code == 409


def test_corregir_titulo_y_artista(client: TestClient, admin_user, fake_downloader) -> None:
    h = headers(client)
    track_id = add_url(client, h).json()["id"]
    respuesta = client.patch(
        f"/tracks/{track_id}", json={"title": "Song 2", "artist_text": "Blur (UK)"}, headers=h
    )
    assert respuesta.status_code == 200
    assert respuesta.json()["artist_text"] == "Blur (UK)"


def test_borrar_una_cancion_borra_tambien_el_fichero(
    client: TestClient, admin_user, fake_downloader, music_dir: Path
) -> None:
    h = headers(client)
    track_id = add_url(client, h).json()["id"]
    fichero = music_dir / "dQw4w9WgXcQ.mp3"
    assert fichero.exists()

    assert client.delete(f"/tracks/{track_id}", headers=h).status_code == 204
    assert not fichero.exists()
    assert client.get(f"/tracks/{track_id}", headers=h).status_code == 404
    assert client.get("/tracks", headers=h).json()["total"] == 0


def test_tras_borrarla_se_puede_volver_a_anadir(
    client: TestClient, admin_user, fake_downloader
) -> None:
    h = headers(client)
    track_id = add_url(client, h).json()["id"]
    client.delete(f"/tracks/{track_id}", headers=h)
    assert add_url(client, h).status_code == 202


# --- Vista previa de la busqueda --------------------------------------------


def test_la_busqueda_muestra_los_candidatos(
    client: TestClient, admin_user, fake_downloader
) -> None:
    h = headers(client)
    respuesta = client.post(
        "/tracks/search/preview", json={"title": "Song 2", "artist": "Blur"}, headers=h
    )
    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert fake_downloader.searched == [("Song 2", "Blur")]
    assert [c["title"] for c in datos["candidates"]] == [
        "Puro Perreo Vol.37 Mix (Bad Bunny, Karol G, etc)",
        "Blur - Song 2 (Official Music Video)",
    ]
    # Se conserva el orden de YouTube y se avisa de cual es un mix
    assert datos["candidates"][0]["too_long"] is True
    assert datos["candidates"][1]["too_long"] is False
    assert datos["candidates"][0]["duration_seconds"] == 2527
    assert datos["candidates"][1]["channel"] == "Blur"


def test_la_busqueda_marca_lo_que_ya_esta_en_la_biblioteca(
    client: TestClient, admin_user, fake_downloader
) -> None:
    h = headers(client)
    add_url(client, h)  # deja dQw4w9WgXcQ en la biblioteca

    candidatos = client.post(
        "/tracks/search/preview", json={"title": "Song 2", "artist": "Blur"}, headers=h
    ).json()["candidates"]
    marcados = {c["video_id"]: c["already_in_library"] for c in candidatos}
    assert marcados == {"mixlargo123": False, "dQw4w9WgXcQ": True}


def test_elegir_un_candidato_lo_descarga(
    client: TestClient, admin_user, fake_downloader
) -> None:
    h = headers(client)
    candidatos = client.post(
        "/tracks/search/preview", json={"title": "Song 2", "artist": "Blur"}, headers=h
    ).json()["candidates"]

    # El usuario elige el segundo, no el mix que YouTube pone primero
    elegido = candidatos[1]
    respuesta = client.post("/tracks/from-url", json={"url": elegido["url"]}, headers=h)
    assert respuesta.status_code == 202
    assert client.get(f"/tracks/{respuesta.json()['id']}", headers=h).json()["status"] == "ready"


def test_la_vista_previa_requiere_sesion(client: TestClient) -> None:
    assert client.post("/tracks/search/preview", json={"title": "x"}).status_code == 401


def test_si_youtube_falla_la_busqueda_lo_dice(
    client: TestClient, admin_user, fake_downloader
) -> None:
    fake_downloader.error = DownloadError("YouTube pide verificacion.")
    respuesta = client.post(
        "/tracks/search/preview", json={"title": "Song 2"}, headers=headers(client)
    )
    assert respuesta.status_code == 502
    assert "verificacion" in respuesta.json()["detail"]


# --- Busqueda solo por artista ----------------------------------------------


def test_solo_con_el_artista_se_piden_mas_candidatos(
    client: TestClient, admin_user, fake_downloader
) -> None:
    """Sin titulo se esta explorando a un artista, no buscando algo concreto."""
    h = headers(client)
    respuesta = client.post(
        "/tracks/search/preview", json={"artist": "Bad Bunny"}, headers=h
    )
    assert respuesta.status_code == 200
    assert respuesta.json()["query"] == "ytsearch10:Bad Bunny"
    assert fake_downloader.searched == [(None, "Bad Bunny")]


def test_solo_con_el_titulo_tambien_vale(
    client: TestClient, admin_user, fake_downloader
) -> None:
    respuesta = client.post(
        "/tracks/search/preview", json={"title": "Song 2"}, headers=headers(client)
    )
    assert respuesta.status_code == 200
    assert respuesta.json()["query"] == "ytsearch5:Song 2"


def test_buscar_sin_nada_da_error(client: TestClient, admin_user, fake_downloader) -> None:
    h = headers(client)
    for cuerpo in ({}, {"title": "", "artist": "   "}):
        respuesta = client.post("/tracks/search/preview", json=cuerpo, headers=h)
        assert respuesta.status_code == 422
        assert "titulo" in respuesta.text and "artista" in respuesta.text


def test_alta_directa_solo_con_el_artista(
    client: TestClient, admin_user, fake_downloader
) -> None:
    h = headers(client)
    respuesta = client.post("/tracks/search", json={"artist": "Blur"}, headers=h)
    assert respuesta.status_code == 202
    assert fake_downloader.resolved_queries == ["ytsearch5:Blur"]
    assert client.get(f"/tracks/{respuesta.json()['id']}", headers=h).json()["status"] == "ready"


def test_reintentar_repite_lo_que_pidio_el_usuario(
    client: TestClient, admin_user, fake_downloader
) -> None:
    """Y no el titulo ya resuelto, que para una busqueda por artista seria el
    propio nombre del artista repetido."""
    fake_downloader.error = DownloadError("Fallo temporal.")
    h = headers(client)
    track_id = client.post("/tracks/search", json={"artist": "Blur"}, headers=h).json()["id"]

    fake_downloader.error = None
    fake_downloader.resolved_queries.clear()
    client.post(f"/tracks/{track_id}/retry", headers=h)
    assert fake_downloader.resolved_queries == ["ytsearch5:Blur"]
