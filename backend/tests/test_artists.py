from fastapi.testclient import TestClient

from app.services.enrichment import EnrichmentError
from tests.conftest import ADMIN_PASSWORD, auth_headers, login

URL = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"


def headers(client: TestClient) -> dict[str, str]:
    return auth_headers(login(client, "enguillem", ADMIN_PASSWORD)["access_token"])


def add_track(client: TestClient, h: dict[str, str]) -> dict:
    respuesta = client.post("/tracks/from-url", json={"url": URL}, headers=h)
    return client.get(f"/tracks/{respuesta.json()['id']}", headers=h).json()


# --- Acceso -----------------------------------------------------------------


def test_artistas_requiere_sesion(client: TestClient) -> None:
    assert client.get("/artists").status_code == 401


# --- Alta automatica al descargar -------------------------------------------


def test_descargar_una_cancion_crea_la_ficha_del_artista(
    client: TestClient, admin_user, fake_downloader, fake_enrichment
) -> None:
    h = headers(client)
    track = add_track(client, h)
    assert [a["name"] for a in track["artists"]] == ["Blur"]

    artistas = client.get("/artists", headers=h).json()
    assert artistas["total"] == 1
    ficha = artistas["items"][0]
    assert ficha["name"] == "Blur"
    assert ficha["track_count"] == 1


def test_la_ficha_se_rellena_desde_las_fuentes_externas(
    client: TestClient, admin_user, fake_downloader, fake_enrichment
) -> None:
    h = headers(client)
    add_track(client, h)

    ficha = client.get("/artists", headers=h).json()["items"][0]
    assert ficha["enrichment_status"] == "ok"
    assert ficha["country"] == "GB"
    assert ficha["begin_year"] == 1988
    assert "grupo britanico" in ficha["bio"]
    assert ficha["wikipedia_url"] == "https://es.wikipedia.org/wiki/Blur"
    assert {r["related_name"] for r in ficha["relations"]} == {"Damon Albarn", "Gorillaz"}


def test_si_las_bases_musicales_no_lo_conocen_se_mira_su_canal(
    client: TestClient, admin_user, fake_downloader, fake_enrichment
) -> None:
    """Los mashups, edits y transiciones no estan en MusicBrainz ni en
    Wikipedia, pero el canal de quien los monta si existe."""
    fake_enrichment.facts = {}  # MusicBrainz no lo encuentra
    h = headers(client)
    add_track(client, h)

    ficha = client.get("/artists", headers=h).json()["items"][0]
    assert ficha["enrichment_status"] == "youtube"
    assert ficha["image_url"] == "https://yt3.googleusercontent.com/avatar.jpg"
    assert ficha["channel_url"] == "https://www.youtube.com/@djnardini"
    assert ficha["follower_count"] == 1920
    assert ficha["bio"] == "Edits y transiciones para pista."


def test_si_tampoco_hay_canal_queda_como_no_encontrado(
    client: TestClient, admin_user, fake_downloader, fake_enrichment
) -> None:
    fake_enrichment.facts = {}
    fake_downloader.channel = None
    h = headers(client)
    add_track(client, h)

    ficha = client.get("/artists", headers=h).json()["items"][0]
    assert ficha["enrichment_status"] == "not_found"
    assert ficha["bio"] is None


def test_si_no_falta_nada_no_se_consulta_el_canal(
    client: TestClient, admin_user, fake_downloader, fake_enrichment
) -> None:
    """Consultar el canal cuesta dos llamadas a yt-dlp: solo se hace cuando
    hace falta tapar un hueco."""
    h = headers(client)
    add_track(client, h)  # Blur, que esta en las fuentes y con foto

    ficha = client.get("/artists", headers=h).json()["items"][0]
    assert ficha["enrichment_status"] == "ok"
    assert ficha["image_url"] == "https://upload.wikimedia.org/blur.jpg"
    assert ficha["channel_url"] is None
    assert fake_downloader.channel_queries == []


def test_si_falla_la_red_la_cancion_sigue_estando_lista(
    client: TestClient, admin_user, fake_downloader, fake_enrichment
) -> None:
    fake_enrichment.error = EnrichmentError("MusicBrainz no responde.")
    h = headers(client)
    track = add_track(client, h)

    assert track["status"] == "ready"  # la descarga no depende de la biografia
    ficha = client.get("/artists", headers=h).json()["items"][0]
    assert ficha["enrichment_status"] == "error"
    assert "MusicBrainz" in ficha["enrichment_error"]


def test_dos_canciones_del_mismo_artista_comparten_ficha(
    client: TestClient, admin_user, fake_downloader, fake_enrichment
) -> None:
    h = headers(client)
    add_track(client, h)
    fake_downloader.info = fake_downloader.info.__class__(
        video_id="abcdefghijk",
        title="Parklife",
        artist="blur ",  # otra grafia: mismo artista
        duration_seconds=180,
        webpage_url="https://www.youtube.com/watch?v=abcdefghijk",
        site="youtube",
    )
    client.post(
        "/tracks/from-url",
        json={"url": "https://www.youtube.com/watch?v=abcdefghijk"},
        headers=h,
    )

    artistas = client.get("/artists", headers=h).json()
    assert artistas["total"] == 1
    assert artistas["items"][0]["track_count"] == 2
    # Y solo se consulto a las fuentes externas una vez
    assert fake_enrichment.lookups == ["Blur"]


def test_las_canciones_del_artista(
    client: TestClient, admin_user, fake_downloader, fake_enrichment
) -> None:
    h = headers(client)
    add_track(client, h)
    artist_id = client.get("/artists", headers=h).json()["items"][0]["id"]

    canciones = client.get(f"/artists/{artist_id}/tracks", headers=h).json()
    assert [t["title"] for t in canciones] == ["Song 2"]


# --- Colaboraciones ---------------------------------------------------------


def test_se_separa_por_feat_pero_no_por_ampersand(
    client: TestClient, admin_user, fake_downloader, fake_enrichment
) -> None:
    h = headers(client)
    fake_downloader.info = fake_downloader.info.__class__(
        video_id="colab000000",
        title="Tema",
        artist="Simon & Garfunkel feat. Aretha Franklin",
        duration_seconds=200,
        webpage_url="https://www.youtube.com/watch?v=colab000000",
        site="youtube",
    )
    track = client.post(
        "/tracks/from-url",
        json={"url": "https://www.youtube.com/watch?v=colab000000"},
        headers=h,
    ).json()
    track = client.get(f"/tracks/{track['id']}", headers=h).json()

    # "&" NO parte: "Simon & Garfunkel" es un solo grupo. "feat." si.
    assert [a["name"] for a in track["artists"]] == [
        "Simon & Garfunkel",
        "Aretha Franklin",
    ]


def test_corregir_los_artistas_de_una_cancion(
    client: TestClient, admin_user, fake_downloader, fake_enrichment
) -> None:
    h = headers(client)
    track = add_track(client, h)

    corregida = client.put(
        f"/tracks/{track['id']}/artists",
        json={"names": ["Blur", "Damon Albarn"]},
        headers=h,
    )
    assert corregida.status_code == 200
    assert [a["name"] for a in corregida.json()["artists"]] == ["Blur", "Damon Albarn"]
    assert corregida.json()["artist_text"] == "Blur, Damon Albarn"


# --- Ficha manual -----------------------------------------------------------


def test_alta_manual_de_artista(client: TestClient, admin_user, fake_enrichment) -> None:
    h = headers(client)
    creado = client.post("/artists", json={"name": "Blur"}, headers=h)
    assert creado.status_code == 201
    assert creado.json()["name"] == "Blur"

    repetido = client.post("/artists", json={"name": " blur "}, headers=h)
    assert repetido.status_code == 409


def test_edicion_manual_protege_la_ficha_del_enriquecido(
    client: TestClient, admin_user, fake_downloader, fake_enrichment
) -> None:
    h = headers(client)
    add_track(client, h)
    artist_id = client.get("/artists", headers=h).json()["items"][0]["id"]

    editado = client.patch(
        f"/artists/{artist_id}",
        json={"bio": "Lo que yo se de ellos, que es bastante.", "country": "Reino Unido"},
        headers=h,
    )
    assert editado.status_code == 200
    assert editado.json()["enrichment_status"] == "manual"

    # Volver a enriquecer no pisa lo escrito a mano...
    sin_forzar = client.post(f"/artists/{artist_id}/enrich", headers=h).json()
    assert sin_forzar["bio"] == "Lo que yo se de ellos, que es bastante."
    assert sin_forzar["country"] == "Reino Unido"

    # ...salvo que se pida expresamente
    forzado = client.post(f"/artists/{artist_id}/enrich?force=true", headers=h).json()
    assert forzado["enrichment_status"] == "ok"


def test_renombrar_a_un_nombre_ya_usado_da_conflicto(
    client: TestClient, admin_user, fake_enrichment
) -> None:
    h = headers(client)
    client.post("/artists", json={"name": "Blur"}, headers=h)
    otro = client.post("/artists", json={"name": "Oasis"}, headers=h).json()

    respuesta = client.patch(f"/artists/{otro['id']}", json={"name": "blur"}, headers=h)
    assert respuesta.status_code == 409


def test_buscar_y_borrar_artistas(client: TestClient, admin_user, fake_enrichment) -> None:
    h = headers(client)
    client.post("/artists", json={"name": "Blur"}, headers=h)
    oasis = client.post("/artists", json={"name": "Oasis"}, headers=h).json()

    encontrados = client.get("/artists?search=oas", headers=h).json()
    assert [a["name"] for a in encontrados["items"]] == ["Oasis"]

    assert client.delete(f"/artists/{oasis['id']}", headers=h).status_code == 204
    assert client.get("/artists", headers=h).json()["total"] == 1


def test_borrar_un_artista_no_borra_sus_canciones(
    client: TestClient, admin_user, fake_downloader, fake_enrichment
) -> None:
    h = headers(client)
    track = add_track(client, h)
    artist_id = track["artists"][0]["id"]

    client.delete(f"/artists/{artist_id}", headers=h)
    sigue = client.get(f"/tracks/{track['id']}", headers=h).json()
    assert sigue["status"] == "ready"
    assert sigue["artists"] == []


# --- Grafo de relaciones ----------------------------------------------------


def test_una_relacion_se_enlaza_cuando_el_otro_artista_aparece_despues(
    client: TestClient, admin_user, fake_enrichment
) -> None:
    """El caso del briefing: Robbie Williams <-> Take That."""
    h = headers(client)
    robbie = client.post("/artists", json={"name": "Robbie Williams"}, headers=h).json()

    # Take That aun no esta en la biblioteca: la relacion existe pero sin enlace
    relacion = client.get(f"/artists/{robbie['id']}", headers=h).json()["relations"][0]
    assert relacion["related_name"] == "Take That"
    assert relacion["related_artist_id"] is None

    take_that = client.post("/artists", json={"name": "Take That"}, headers=h).json()

    # Ahora la ficha de Robbie enlaza con la de Take That, y al reves
    relacion = client.get(f"/artists/{robbie['id']}", headers=h).json()["relations"][0]
    assert relacion["related_artist_id"] == take_that["id"]

    de_vuelta = client.get(f"/artists/{take_that['id']}", headers=h).json()["relations"]
    assert any(r["related_artist_id"] == robbie["id"] for r in de_vuelta)


def test_el_canal_tapa_el_hueco_de_la_foto(
    client: TestClient, admin_user, fake_downloader, fake_enrichment
) -> None:
    """MusicBrainz conoce a muchos artistas de los que Wikipedia no tiene
    articulo, y por tanto tampoco foto. El canal si la tiene."""
    fake_enrichment.facts = {
        "Blur": fake_enrichment.facts["Blur"].__class__(
            name="Blur", country="GB", begin_year=1988, bio="Grupo britanico.",
        )  # encontrado, pero sin imagen
    }
    h = headers(client)
    add_track(client, h)

    ficha = client.get("/artists", headers=h).json()["items"][0]
    # Los datos siguen siendo de MusicBrainz...
    assert ficha["enrichment_status"] == "ok"
    assert ficha["bio"] == "Grupo britanico."
    # ...pero la foto la pone el canal
    assert ficha["image_url"] == "https://yt3.googleusercontent.com/avatar.jpg"
    assert ficha["follower_count"] == 1920


def test_se_guardan_los_enlaces_para_descubrir_mas_musica(
    client: TestClient, admin_user, fake_downloader, fake_enrichment
) -> None:
    """MusicBrainz devuelve veinte enlaces por artista; solo interesan los que
    llevan a mas musica suya o a comprarsela."""
    h = headers(client)
    add_track(client, h)

    ficha = client.get("/artists", headers=h).json()["items"][0]
    assert ficha["links"] == {
        "bandcamp": "https://blur.bandcamp.com/",
        "official homepage": "https://blur.co.uk/",
    }


def test_los_enlaces_se_suman_sin_perder_los_anteriores(
    client: TestClient, admin_user, fake_downloader, fake_enrichment
) -> None:
    h = headers(client)
    add_track(client, h)
    artist_id = client.get("/artists", headers=h).json()["items"][0]["id"]

    # Una consulta posterior descubre un enlace nuevo
    fake_enrichment.facts["Blur"] = fake_enrichment.facts["Blur"].__class__(
        name="Blur", links={"soundcloud": "https://soundcloud.com/blur"}
    )
    ficha = client.post(f"/artists/{artist_id}/enrich?force=true", headers=h).json()
    assert set(ficha["links"]) == {"bandcamp", "official homepage", "soundcloud"}
