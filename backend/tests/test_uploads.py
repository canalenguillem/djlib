"""Importar ficheros propios: compras, descargas de un record pool, lo que sea
que ya este en el disco del usuario."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests.conftest import ADMIN_PASSWORD, auth_headers, login


def headers(client: TestClient) -> dict[str, str]:
    return auth_headers(login(client, "enguillem", ADMIN_PASSWORD)["access_token"])


@pytest.fixture
def wav(tmp_path) -> bytes:
    """Un wav de verdad, generado con ffmpeg: los metadatos se leen del fichero
    con ffprobe, asi que un fichero falso no serviria para probar nada."""
    import subprocess

    destino = tmp_path / "prueba.wav"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=3",
         "-metadata", "title=Cancion De Prueba", "-metadata", "artist=Artista De Prueba",
         "-ac", "2", "-ar", "44100", str(destino)],
        capture_output=True, check=True,
    )
    return destino.read_bytes()


def subir(client: TestClient, h: dict, contenido: bytes, nombre: str = "tema.wav", **campos):
    return client.post(
        "/tracks/upload",
        files={"audio": (nombre, contenido, "audio/wav")},
        data=campos,
        headers=h,
    )


def test_subir_requiere_sesion(client: TestClient) -> None:
    assert client.post("/tracks/upload", files={"audio": ("a.wav", b"x")}).status_code == 401


def test_subir_un_fichero_lo_deja_listo(
    client: TestClient, admin_user, wav, music_dir: Path, fake_downloader
) -> None:
    respuesta = subir(client, headers(client), wav)
    assert respuesta.status_code == 201, respuesta.text
    track = respuesta.json()

    # No hay nada que descargar: nace lista
    assert track["status"] == "ready"
    assert track["ingest_source"] == "upload"
    assert track["duration_seconds"] == 3
    # Los metadatos salen del propio fichero
    assert track["title"] == "Cancion De Prueba"
    assert track["artist_text"] == "Artista De Prueba"
    assert len(list(music_dir.glob("up_*.wav"))) == 1


def test_el_titulo_y_el_artista_que_escribe_el_usuario_mandan(
    client: TestClient, admin_user, wav, fake_downloader
) -> None:
    track = subir(
        client, headers(client), wav, title="Mi titulo", artist="Mi artista"
    ).json()
    assert track["title"] == "Mi titulo"
    assert track["artist_text"] == "Mi artista"


def test_sin_etiquetas_se_usa_el_nombre_del_fichero(
    client: TestClient, admin_user, tmp_path, fake_downloader
) -> None:
    import subprocess

    destino = tmp_path / "sin_tags.wav"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=2", str(destino)],
        capture_output=True, check=True,
    )
    track = subir(
        client, headers(client), destino.read_bytes(), nombre="Blur - Parklife.wav"
    ).json()
    assert track["title"] == "Blur - Parklife"


def test_se_crea_la_ficha_del_artista(
    client: TestClient, admin_user, wav, fake_enrichment, fake_downloader
) -> None:
    h = headers(client)
    track = subir(client, h, wav, artist="Blur").json()
    assert [a["name"] for a in track["artists"]] == ["Blur"]
    assert client.get("/artists", headers=h).json()["total"] == 1


def test_formato_no_admitido(client: TestClient, admin_user, wav, fake_downloader) -> None:
    respuesta = subir(client, headers(client), wav, nombre="documento.pdf")
    assert respuesta.status_code == 400
    assert "no admitido" in respuesta.json()["detail"]


def test_un_fichero_que_no_es_audio_se_rechaza(
    client: TestClient, admin_user, music_dir: Path, fake_downloader
) -> None:
    """La extension no basta: si ffprobe no ve audio, no entra."""
    respuesta = subir(client, headers(client), b"esto no es audio" * 100, nombre="falso.wav")
    assert respuesta.status_code == 400
    assert list(music_dir.glob("up_*")) == []  # y no deja basura en el disco


def test_fichero_vacio(client: TestClient, admin_user, fake_downloader) -> None:
    assert subir(client, headers(client), b"").status_code == 400


def test_demasiado_grande(client: TestClient, admin_user, wav, monkeypatch, fake_downloader) -> None:
    from app.core.config import settings

    monkeypatch.setattr(settings, "upload_max_bytes", 100)
    respuesta = subir(client, headers(client), wav)
    assert respuesta.status_code == 413


def test_subir_dos_veces_la_misma_cancion(
    client: TestClient, admin_user, wav, music_dir: Path, fake_downloader
) -> None:
    h = headers(client)
    assert subir(client, h, wav).status_code == 201
    repetida = subir(client, h, wav)
    assert repetida.status_code == 409
    # Y no se queda un fichero huerfano del intento fallido
    assert len(list(music_dir.glob("up_*.wav"))) == 1


def test_el_fichero_subido_se_puede_descargar_y_borrar(
    client: TestClient, admin_user, wav, music_dir: Path, fake_downloader
) -> None:
    h = headers(client)
    track_id = subir(client, h, wav).json()["id"]

    fichero = client.get(f"/tracks/{track_id}/file", headers=h)
    assert fichero.status_code == 200
    assert fichero.headers["content-type"] == "audio/wav"

    client.delete(f"/tracks/{track_id}", headers=h)
    assert list(music_dir.glob("up_*.wav")) == []
