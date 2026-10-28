"""Top 100 de Beatport: se lee del JSON de su pagina, sin salir a la red."""

import json

import pytest
from fastapi.testclient import TestClient

from app.services import beatport
from tests.conftest import ADMIN_PASSWORD, USER_PASSWORD, auth_headers, login
from tests.test_crates import crear_track


def pista(id_: int, nombre: str, mezcla: str, artista: str) -> dict:
    return {
        "id": id_,
        "slug": nombre.lower().replace(" ", "-"),
        "name": nombre,
        "mix_name": mezcla,
        "artists": [{"name": artista}],
        "remixers": [],
        "bpm": 128,
        "key": {"camelot_number": 8, "camelot_letter": "A", "name": "A Minor"},
        "genre": {"name": "Tech House"},
        "length": "6:12",
        "publish_date": "2026-10-23",
        "release": {
            "label": {"name": "Toolroom"},
            "image": {"dynamic_uri": "https://geo-media.beatport.com/image_size/{w}x{h}/x.jpg"},
        },
        "sample_url": "https://geo-samples.beatport.com/track/x.LOFI.mp3",
    }


def pagina(pistas: list[dict]) -> str:
    datos = {
        "props": {
            "pageProps": {
                "dehydratedState": {
                    "queries": [
                        {"queryKey": ["genre-11"], "state": {"data": {"name": "Tech House"}}},
                        {
                            "queryKey": ["genre-11-top-100-tracks-per_page=100"],
                            "state": {"data": {"results": pistas}},
                        },
                    ]
                }
            }
        }
    }
    return (
        '<html><script id="__NEXT_DATA__" type="application/json">'
        + json.dumps(datos)
        + "</script></html>"
    )


def test_lee_el_top_de_la_pagina() -> None:
    pistas = beatport.parse(pagina([pista(1, "Zoolander", "Extended Mix", "Beave")]))
    assert len(pistas) == 1
    p = pistas[0]
    assert (p.position, p.title, p.mix, p.artist) == (1, "Zoolander", "Extended Mix", "Beave")
    assert p.key == "8A · A Minor"
    assert p.label == "Toolroom"
    assert p.image_url == "https://geo-media.beatport.com/image_size/250x250/x.jpg"
    assert p.beatport_url == "https://www.beatport.com/track/zoolander/1"


def test_si_cambia_la_pagina_lo_dice() -> None:
    with pytest.raises(beatport.BeatportError):
        beatport.parse("<html>nada</html>")


@pytest.fixture
def top_falso(monkeypatch) -> None:
    pistas = beatport.parse(
        pagina(
            [
                pista(1, "Primera", "Extended Mix", "Blur"),
                pista(2, "Otra", "Original Mix", "Nadie"),
            ]
        )
    )
    monkeypatch.setattr(beatport, "top100", lambda genero=None: pistas)


def test_el_top_marca_lo_que_ya_esta(
    client: TestClient, admin_user, fake_downloader, top_falso
) -> None:
    h = auth_headers(login(client, "enguillem", ADMIN_PASSWORD)["access_token"])
    crear_track(client, h, "aaaaaaaaaaa", "Primera", fake_downloader)

    datos = client.get("/beatport/top-100", params={"genre": 11}, headers=h).json()
    assert datos["genre"] == {"id": 11, "name": "Tech House"}
    primera, otra = datos["items"]
    # Se busca con la mezcla, pero cuenta como la que ya estaba
    assert primera["title"] == "Primera (Extended Mix)"
    assert primera["already_in_library"] is True
    assert otra["already_in_library"] is False


def test_generos(client: TestClient, admin_user) -> None:
    h = auth_headers(login(client, "enguillem", ADMIN_PASSWORD)["access_token"])
    generos = client.get("/beatport/genres", headers=h).json()
    assert {"id": 106, "name": "Latin"} in generos


def test_sin_el_menu_no_se_puede(client: TestClient, admin_user, normal_user, db) -> None:
    normal_user.menus = ["library"]
    db.add(normal_user)
    db.commit()
    h = auth_headers(login(client, "dj_pepe", USER_PASSWORD)["access_token"])
    assert client.get("/beatport/genres", headers=h).status_code == 403
