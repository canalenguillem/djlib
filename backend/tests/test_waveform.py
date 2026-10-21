"""Forma de onda en tres bandas, la que se pinta en cada fila como en un CDJ."""

import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.services import waveform as waveform_service
from tests.conftest import ADMIN_PASSWORD, auth_headers, login


def headers(client: TestClient) -> dict[str, str]:
    return auth_headers(login(client, "enguillem", ADMIN_PASSWORD)["access_token"])


def crear(client: TestClient, h: dict, video_id: str, fake_downloader) -> int:
    fake_downloader.info = fake_downloader.info.__class__(
        video_id=video_id, title="Tema", artist="Blur", duration_seconds=180,
        webpage_url=f"https://www.youtube.com/watch?v={video_id}", site="youtube",
    )
    return client.post(
        "/tracks/from-url",
        json={"url": f"https://www.youtube.com/watch?v={video_id}"},
        headers=h,
    ).json()["id"]


# --- Calculo ------------------------------------------------------------------


def test_cada_tramo_resume_su_energia() -> None:
    """RMS por tramo: un tramo en silencio da cero y uno a tope da su nivel."""
    banda = [0.0] * 4 + [0.5, -0.5, 0.5, -0.5]
    assert waveform_service.summarize(banda, 2) == [0.0, 0.5]


def test_una_cancion_cortisima_no_deja_tramos_vacios() -> None:
    assert len(waveform_service.summarize([0.1, 0.2], 5)) == 5
    assert waveform_service.summarize([], 3) == [0.0, 0.0, 0.0]


def test_las_tres_bandas_comparten_escala() -> None:
    """Si cada banda se escalara por su cuenta, unos agudos flojisimos saldrian
    tan altos como el bombo. Con un maximo comun conservan su peso real."""
    datos = waveform_service.encode([1.0, 0.25], [0.25, 0.0], [0.0, 0.0])
    bandas = waveform_service.decode(datos)
    assert bandas["low"] == [255, 128]
    assert bandas["mid"] == [128, 0]
    assert bandas["high"] == [0, 0]


def test_el_silencio_no_divide_por_cero() -> None:
    assert waveform_service.encode([0.0], [0.0], [0.0]) == bytes(3)


@pytest.mark.parametrize(
    ("frecuencia", "banda"),
    [(60, 0), (800, 1), (5000, 2)],
)
def test_cada_frecuencia_cae_en_su_banda(tmp_path: Path, frecuencia: int, banda: int) -> None:
    """Con ffmpeg de verdad: sin fijar el orden de los canales, ffmpeg los
    reordena y los graves salian pintados como agudos."""
    tono = tmp_path / "tono.wav"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", f"sine=frequency={frecuencia}:duration=2",
         str(tono)],
        capture_output=True, check=True,
    )
    muestras = waveform_service._decode(tono)
    energias = [
        waveform_service.summarize(muestras[i::waveform_service.BANDS], 1)[0]
        for i in range(waveform_service.BANDS)
    ]
    assert max(range(3), key=lambda i: energias[i]) == banda


# --- En la tuberia y en la API ---------------------------------------------


def test_al_descargar_se_calcula_la_onda(
    client: TestClient, admin_user, fake_downloader, fake_waveform
) -> None:
    h = headers(client)
    track_id = crear(client, h, "aaaaaaaaaaa", fake_downloader)
    assert len(fake_waveform.analizados) == 1

    respuesta = client.get(f"/tracks/{track_id}/waveform", headers=h)
    assert respuesta.status_code == 200
    assert respuesta.json() == {"bins": 2, "low": [255, 128], "mid": [100, 50], "high": [20, 10]}
    # Ya estaba guardada: pedirla no vuelve a lanzar ffmpeg
    assert len(fake_waveform.analizados) == 1


def test_el_listado_no_carga_la_onda(
    client: TestClient, admin_user, fake_downloader
) -> None:
    """Son mil bytes por cancion que el listado no usa."""
    h = headers(client)
    crear(client, h, "aaaaaaaaaaa", fake_downloader)
    assert "waveform" not in client.get("/tracks", headers=h).json()["items"][0]


def test_las_canciones_antiguas_la_calculan_al_pedirla(
    client: TestClient, admin_user, fake_downloader, fake_waveform
) -> None:
    """Las que se bajaron antes de existir la onda no la tienen."""
    fake_waveform.datos = None
    h = headers(client)
    track_id = crear(client, h, "aaaaaaaaaaa", fake_downloader)
    assert client.get(f"/tracks/{track_id}/waveform", headers=h).status_code == 404

    fake_waveform.datos = bytes([10, 20, 30])
    respuesta = client.get(f"/tracks/{track_id}/waveform", headers=h)
    assert respuesta.status_code == 200
    assert respuesta.json()["low"] == [10]


def test_lo_que_no_esta_descargado_no_tiene_onda(
    client: TestClient, admin_user, fake_downloader, fake_waveform
) -> None:
    from app.services.downloader import DownloadError

    fake_downloader.error = DownloadError("Video privado.")
    h = headers(client)
    track_id = crear(client, h, "zzzzzzzzzzz", fake_downloader)
    assert client.get(f"/tracks/{track_id}/waveform", headers=h).status_code == 409
    assert fake_waveform.analizados == []


def test_la_onda_requiere_sesion(client: TestClient) -> None:
    assert client.get("/tracks/1/waveform").status_code == 401
