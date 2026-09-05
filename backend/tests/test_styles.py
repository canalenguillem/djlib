"""Clasificacion automatica por estilo con los generos de MusicBrainz."""

from fastapi.testclient import TestClient

from tests.conftest import ADMIN_PASSWORD, auth_headers, login

URL = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"


def headers(client: TestClient) -> dict[str, str]:
    return auth_headers(login(client, "enguillem", ADMIN_PASSWORD)["access_token"])


def add_track(client: TestClient, h: dict) -> dict:
    respuesta = client.post("/tracks/from-url", json={"url": URL}, headers=h)
    return client.get(f"/tracks/{respuesta.json()['id']}", headers=h).json()


def estilos(track: dict) -> list[str]:
    return sorted(t["name"] for t in track["tags"] if t["kind"] == "style")


def test_al_descargar_se_etiqueta_con_el_estilo_del_artista(
    client: TestClient, admin_user, fake_downloader, fake_enrichment
) -> None:
    h = headers(client)
    track = add_track(client, h)
    # Los tres generos mas votados, capitalizados como cualquier otra etiqueta
    assert estilos(track) == ["Alternative Rock", "Britpop", "Indie Rock"]


def test_los_generos_quedan_en_la_ficha_del_artista(
    client: TestClient, admin_user, fake_downloader, fake_enrichment
) -> None:
    h = headers(client)
    add_track(client, h)
    ficha = client.get("/artists", headers=h).json()["items"][0]
    assert ficha["genres"] == ["britpop", "alternative rock", "indie rock", "art rock"]


def test_solo_se_toman_los_primeros_generos(
    client: TestClient, admin_user, fake_downloader, fake_enrichment, monkeypatch
) -> None:
    """Mas de tres empieza a ser ruido."""
    from app.core.config import settings

    monkeypatch.setattr(settings, "max_genres_per_artist", 1)
    track = add_track(client, headers(client))
    assert estilos(track) == ["Britpop"]


def test_dos_canciones_del_mismo_estilo_comparten_etiqueta(
    client: TestClient, admin_user, fake_downloader, fake_enrichment
) -> None:
    """El catalogo es cerrado: no se duplican etiquetas equivalentes."""
    h = headers(client)
    add_track(client, h)
    fake_downloader.info = fake_downloader.info.__class__(
        video_id="abcdefghijk", title="Parklife", artist="Blur", duration_seconds=180,
        webpage_url="https://www.youtube.com/watch?v=abcdefghijk", site="youtube",
    )
    client.post(
        "/tracks/from-url",
        json={"url": "https://www.youtube.com/watch?v=abcdefghijk"},
        headers=h,
    )

    catalogo = client.get("/tags?kind=style", headers=h).json()
    assert sorted(t["name"] for t in catalogo) == [
        "Alternative Rock", "Britpop", "Indie Rock",
    ]


def test_no_se_pisan_los_estilos_que_ha_puesto_el_usuario(
    client: TestClient, admin_user, fake_downloader, fake_enrichment
) -> None:
    """Lo que decide el usuario manda sobre lo que diga MusicBrainz."""
    from app.db.session import SessionLocal
    from app.models.track import Track
    from app.services import artist_service

    h = headers(client)
    track = add_track(client, h)
    mio = client.post("/tags", json={"kind": "style", "name": "Britanico noventero"}, headers=h).json()
    client.put(f"/tracks/{track['id']}/tags", json={"tag_ids": [mio["id"]]}, headers=h)

    with SessionLocal() as db:
        artist_service.apply_style_tags(db, db.get(Track, track["id"]))
        db.commit()

    actual = client.get(f"/tracks/{track['id']}", headers=h).json()
    assert estilos(actual) == ["Britanico noventero"]


def test_un_artista_sin_generos_no_deja_etiquetas(
    client: TestClient, admin_user, fake_downloader, fake_enrichment
) -> None:
    fake_enrichment.facts["Blur"] = fake_enrichment.facts["Blur"].__class__(
        name="Blur", genres=[]
    )
    track = add_track(client, headers(client))
    assert estilos(track) == []


def test_las_siglas_no_quedan_ridiculas(
    client: TestClient, admin_user, fake_downloader, fake_enrichment
) -> None:
    """.capitalize() dejaba "Edm" y "R&b"."""
    from app.services.artist_service import genre_label

    assert genre_label("edm") == "EDM"
    assert genre_label("r&b") == "R&B"
    assert genre_label("electro house") == "Electro House"
    assert genre_label("contemporary r&b") == "Contemporary R&B"
    assert genre_label("trap latino") == "Trap Latino"


def test_una_cancion_no_acumula_estilos_de_todos_sus_artistas(
    client: TestClient, admin_user, fake_downloader, fake_enrichment
) -> None:
    """Con varios artistas se juntaban seis etiquetas, que ya no clasifican."""
    facts = fake_enrichment.facts["Blur"].__class__
    fake_enrichment.facts["Blur"] = facts(name="Blur", genres=["britpop", "indie rock"])
    fake_enrichment.facts["Damon Albarn"] = facts(
        name="Damon Albarn", genres=["alternative rock", "art pop", "trip hop"]
    )
    fake_downloader.info = fake_downloader.info.__class__(
        video_id="dQw4w9WgXcQ", title="Tema", artist="Blur feat. Damon Albarn",
        duration_seconds=180, webpage_url=URL, site="youtube",
    )
    track = add_track(client, headers(client))
    assert len(estilos(track)) == 3
