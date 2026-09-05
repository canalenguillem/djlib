"""Integracion con Spotify: generos y ultimas reproducciones."""

from fastapi.testclient import TestClient

from app.services.spotify import SpotifyError
from tests.conftest import ADMIN_PASSWORD, auth_headers, login

URL = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"


def headers(client: TestClient) -> dict[str, str]:
    return auth_headers(login(client, "enguillem", ADMIN_PASSWORD)["access_token"])


# --- Estado y acceso --------------------------------------------------------


def test_requiere_sesion(client: TestClient) -> None:
    assert client.get("/spotify/status").status_code == 401


def test_sin_configurar_no_se_ofrece(client: TestClient, admin_user) -> None:
    estado = client.get("/spotify/status", headers=headers(client)).json()
    assert estado == {"enabled": False, "connected": False, "display_name": None}


def test_configurado_pero_sin_conectar(
    client: TestClient, admin_user, fake_spotify
) -> None:
    estado = client.get("/spotify/status", headers=headers(client)).json()
    assert estado["enabled"] is True
    assert estado["connected"] is False


def test_la_url_de_autorizacion_lleva_lo_necesario(
    client: TestClient, admin_user, fake_spotify
) -> None:
    url = client.post("/spotify/authorize", headers=headers(client)).json()["url"]
    assert url.startswith("https://accounts.spotify.com/authorize?")
    assert "user-read-recently-played" in url
    assert "state=" in url  # ata la vuelta al usuario que la pidio


def test_sin_configurar_no_hay_url(client: TestClient, admin_user) -> None:
    assert client.post("/spotify/authorize", headers=headers(client)).status_code == 503


def test_un_estado_solo_sirve_una_vez(client: TestClient, admin_user, fake_spotify) -> None:
    """Es lo que impide que otro reutilice la vuelta de Spotify."""
    from app.services import spotify

    estado = spotify.crear_estado(admin_user.id)
    assert spotify.consumir_estado(estado) == admin_user.id
    assert spotify.consumir_estado(estado) is None
    assert spotify.consumir_estado("inventado") is None


def test_el_callback_rechaza_un_estado_desconocido(client: TestClient) -> None:
    respuesta = client.get(
        "/spotify/callback?code=x&state=inventado", follow_redirects=False
    )
    assert respuesta.status_code in (302, 307)
    assert "estado_no_valido" in respuesta.headers["location"]


def test_el_callback_propaga_el_error_de_spotify(client: TestClient) -> None:
    """Si el usuario deniega el permiso, se vuelve con el motivo."""
    respuesta = client.get(
        "/spotify/callback?error=access_denied", follow_redirects=False
    )
    assert "error=access_denied" in respuesta.headers["location"]


# --- Ultimas reproducciones -------------------------------------------------


def conectar(db_user_id: int, fake_spotify) -> None:
    from app.core.time import utcnow
    from datetime import timedelta
    from app.models.spotify import SpotifyAccount
    from tests.conftest import TestingSessionLocal

    with TestingSessionLocal() as db:
        db.add(
            SpotifyAccount(
                user_id=db_user_id,
                refresh_token="refresco",
                access_token="acceso",
                expires_at=utcnow() + timedelta(hours=1),
                display_name="enguillem",
            )
        )
        db.commit()


def test_sin_conectar_se_avisa(client: TestClient, admin_user, fake_spotify) -> None:
    respuesta = client.get("/spotify/recently-played", headers=headers(client))
    assert respuesta.status_code == 409
    assert "no has conectado" in respuesta.json()["detail"]


def test_devuelve_lo_ultimo_escuchado(
    client: TestClient, admin_user, fake_spotify, fake_downloader
) -> None:
    conectar(admin_user.id, fake_spotify)
    datos = client.get("/spotify/recently-played", headers=headers(client)).json()

    assert [(i["artist"], i["title"]) for i in datos["items"]] == [
        ("Blur", "Song 2"),
        ("Blur", "Parklife"),
    ]
    assert datos["items"][0]["album"] == "Blur"
    assert datos["items"][0]["already_in_library"] is False


def test_marca_lo_que_ya_esta_en_la_biblioteca(
    client: TestClient, admin_user, fake_spotify, fake_downloader
) -> None:
    """Para no volver a descargar lo que ya tienes."""
    h = headers(client)
    client.post("/tracks/from-url", json={"url": URL}, headers=h)  # descarga Song 2
    conectar(admin_user.id, fake_spotify)

    datos = client.get("/spotify/recently-played", headers=h).json()
    marcados = {i["title"]: i["already_in_library"] for i in datos["items"]}
    assert marcados == {"Song 2": True, "Parklife": False}


def test_si_spotify_falla_se_explica(
    client: TestClient, admin_user, fake_spotify
) -> None:
    conectar(admin_user.id, fake_spotify)
    fake_spotify.error = SpotifyError("El permiso de Spotify ha caducado.")
    respuesta = client.get("/spotify/recently-played", headers=headers(client))
    assert respuesta.status_code == 502
    assert "caducado" in respuesta.json()["detail"]


def test_desconectar_la_cuenta(client: TestClient, admin_user, fake_spotify) -> None:
    h = headers(client)
    conectar(admin_user.id, fake_spotify)
    assert client.get("/spotify/status", headers=h).json()["connected"] is True

    assert client.delete("/spotify/connection", headers=h).status_code == 204
    assert client.get("/spotify/status", headers=h).json()["connected"] is False


# --- Generos ----------------------------------------------------------------


def test_spotify_tapa_el_hueco_de_generos_de_musicbrainz(
    client: TestClient, admin_user, fake_downloader, fake_enrichment, fake_spotify
) -> None:
    """MusicBrainz no cataloga lo urbano reciente; Spotify si."""
    fake_enrichment.facts["Rels B"] = fake_enrichment.facts["Blur"].__class__(
        name="Rels B", country="ES", genres=[]
    )
    fake_downloader.info = fake_downloader.info.__class__(
        video_id="dQw4w9WgXcQ", title="A MI", artist="Rels B", duration_seconds=180,
        webpage_url=URL, site="youtube",
    )
    h = headers(client)
    client.post("/tracks/from-url", json={"url": URL}, headers=h)

    ficha = client.get("/artists", headers=h).json()["items"][0]
    assert ficha["genres"] == ["urbano latino", "trap latino"]
    assert fake_spotify.consultados == ["Rels B"]


def test_no_se_pregunta_a_spotify_si_musicbrainz_ya_tiene_generos(
    client: TestClient, admin_user, fake_downloader, fake_enrichment, fake_spotify
) -> None:
    h = headers(client)
    client.post("/tracks/from-url", json={"url": URL}, headers=h)  # Blur, con generos
    assert fake_spotify.consultados == []


def test_el_403_de_modo_desarrollo_explica_que_hacer(monkeypatch) -> None:
    """Es el 403 mas habitual con una app recien creada, y el mensaje generico
    mandaba a mirar los permisos, que no es el problema."""
    import httpx
    import pytest

    from app.core.config import settings
    from app.services import spotify

    monkeypatch.setattr(settings, "spotify_client_id", "id")
    monkeypatch.setattr(settings, "spotify_client_secret", "secreto")

    def fake_get(*args, **kwargs):
        return httpx.Response(
            403,
            text="The user is not registered for this application.",
            request=httpx.Request("GET", "https://api.spotify.com/v1/me"),
        )

    monkeypatch.setattr(httpx, "get", fake_get)
    with pytest.raises(spotify.SpotifyError, match="User Management"):
        spotify._get("/me", "token")
