"""Tops de Deezer y Beatport cruzados en una sola lista."""

import pytest
from fastapi.testclient import TestClient

from app.services import beatport, deezer
from app.services.beatport import BeatportTrack
from app.services.deezer import DeezerTrack

from tests.conftest import ADMIN_PASSWORD, USER_PASSWORD, auth_headers, login
from tests.test_energy_export import crear_track


def bp(posicion: int, nombre: str, artista: str, mezcla: str = "Extended Mix") -> BeatportTrack:
    return BeatportTrack(
        position=posicion, title=nombre, mix=mezcla, artist=artista, remixers=None,
        bpm=126, key="8A", genre="House", label=None, length="6:00", release_date=None,
        image_url=None, sample_url=None, beatport_url=f"https://beatport/{posicion}",
    )


def dz(posicion: int, titulo: str, artista: str) -> DeezerTrack:
    return DeezerTrack(
        position=posicion, title=titulo, artist=artista, duration_seconds=200,
        image_url=None, sample_url=None, deezer_url=f"https://deezer/{posicion}",
    )


@pytest.fixture
def tops(monkeypatch) -> None:
    beatport_tops = {
        None: [bp(1, "Primera", "Blur, Oasis"), bp(2, "Solo Club", "Nadie")],
    }
    deezer_tops = {
        "es": [dz(1, "Solo Radio", "Alguien"), dz(2, "Primera", "Blur")],
        "uk": [dz(1, "Primera (feat. Pulp)", "Blur")],
    }
    monkeypatch.setattr(beatport, "top100", lambda genero=None: beatport_tops[genero])

    def top(pais: str):
        if pais == "de":
            raise deezer.DeezerError("Deezer no contesta.")
        return deezer_tops[pais]

    monkeypatch.setattr(deezer, "top", top)


def headers(client: TestClient) -> dict[str, str]:
    return auth_headers(login(client, "enguillem", ADMIN_PASSWORD)["access_token"])


def test_cruza_sin_repetir_y_ordena_por_presencia(client: TestClient, admin_user, tops) -> None:
    datos = client.get(
        "/charts/combined",
        params=[("source", "deezer:es"), ("source", "deezer:uk"), ("source", "beatport:top")],
        headers=headers(client),
    ).json()
    titulos = [i["title"] for i in datos["items"]]
    # "Primera" esta en las tres listas: va la primera, una sola vez y en su
    # version de DJ, aunque Beatport ponga a dos artistas y Deezer a uno
    assert titulos[0] == "Primera (Extended Mix)"
    assert titulos.count("Primera (Extended Mix)") == 1
    assert len(titulos) == 3
    assert {p["source"] for p in datos["items"][0]["positions"]} == {
        "deezer:es", "deezer:uk", "beatport:top",
    }
    assert datos["items"][0]["groups"] == ["Beatport", "Deezer"]
    # Despues, por el mejor puesto: el 1 de Deezer antes que el 2 de Beatport
    assert titulos[1:] == ["Solo Radio", "Solo Club (Extended Mix)"]
    assert datos["summary"] == {"total": 3, "both": 1, "several": 1}


def test_muchos_paises_no_entierran_lo_de_cabina(monkeypatch, client: TestClient, admin_user) -> None:
    """Cuatro tops de pais casi iguales no deben tapar el 1 de un genero."""
    monkeypatch.setattr(beatport, "top100", lambda genero=None: [bp(1, "Club", "DJ")])
    monkeypatch.setattr(deezer, "top", lambda pais: [dz(30, "Pop", "Estrella")])
    datos = client.get(
        "/charts/combined",
        params=[("source", f"deezer:{p}") for p in ("es", "uk", "de", "world")] + [("source", "beatport:89")],
        headers=headers(client),
    ).json()
    assert [i["title"] for i in datos["items"]] == ["Club (Extended Mix)", "Pop"]


def test_marca_lo_que_ya_esta(client: TestClient, admin_user, fake_downloader, tops) -> None:
    h = headers(client)
    crear_track(client, h, "aaaaaaaaaaa", "Primera", fake_downloader)
    datos = client.get("/charts/combined", params={"source": "deezer:es"}, headers=h).json()
    en_biblioteca = {i["title"]: i["already_in_library"] for i in datos["items"]}
    assert en_biblioteca == {"Solo Radio": False, "Primera": True}


def test_una_lista_que_falla_no_tumba_las_demas(client: TestClient, admin_user, tops) -> None:
    datos = client.get(
        "/charts/combined",
        params=[("source", "deezer:de"), ("source", "deezer:es")],
        headers=headers(client),
    ).json()
    assert len(datos["items"]) == 2
    assert datos["errors"] == [{"source": "deezer:de", "message": "Deezer no contesta."}]


def test_si_fallan_todas_lo_dice(client: TestClient, admin_user, tops) -> None:
    r = client.get("/charts/combined", params={"source": "deezer:de"}, headers=headers(client))
    assert r.status_code == 502


def test_listas_que_no_existen(client: TestClient, admin_user, tops) -> None:
    h = headers(client)
    assert client.get("/charts/combined", headers=h).status_code == 400
    r = client.get("/charts/combined", params={"source": "deezer:marte"}, headers=h)
    assert r.status_code == 400


def test_fuentes(client: TestClient, admin_user) -> None:
    fuentes = client.get("/charts/sources", headers=headers(client)).json()
    assert {"id": "deezer:es", "name": "Top España", "group": "Deezer"} in fuentes
    assert {"id": "beatport:11", "name": "Tech House", "group": "Beatport"} in fuentes


def test_lee_la_lista_de_deezer() -> None:
    pistas = deezer.parse(
        {"tracks": {"data": [{"id": 7, "title": "Tema", "artist": {"name": "Blur"}, "duration": 180,
                              "preview": "https://p", "link": "https://deezer.com/track/7",
                              "album": {"cover_medium": "https://c"}}]}}
    )
    assert pistas == [DeezerTrack(1, "Tema", "Blur", 180, "https://c", "https://p", "https://deezer.com/track/7")]
    with pytest.raises(deezer.DeezerError):
        deezer.parse({"error": {"message": "no"}})


def test_sin_el_menu_no_se_puede(client: TestClient, admin_user, normal_user, db) -> None:
    normal_user.menus = ["library"]
    db.add(normal_user)
    db.commit()
    h = auth_headers(login(client, "dj_pepe", USER_PASSWORD)["access_token"])
    assert client.get("/charts/sources", headers=h).status_code == 403
