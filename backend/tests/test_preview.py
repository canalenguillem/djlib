"""Fragmento de audio para decidir si un candidato es la version buena."""

from fastapi.testclient import TestClient

from app.services.downloader import DownloadError
from tests.conftest import ADMIN_PASSWORD, auth_headers, login

URL = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"


def headers(client: TestClient) -> dict[str, str]:
    return auth_headers(login(client, "enguillem", ADMIN_PASSWORD)["access_token"])


def test_requiere_sesion(client: TestClient) -> None:
    assert client.get(f"/tracks/preview?url={URL}").status_code == 401


def test_devuelve_el_fragmento(client: TestClient, admin_user, fake_preview) -> None:
    respuesta = client.get(f"/tracks/preview?url={URL}", headers=headers(client))
    assert respuesta.status_code == 200
    assert respuesta.headers["content-type"] == "audio/mp4"
    assert b"fragmento-de-mentira" in respuesta.content
    assert fake_preview["construidos"] == [URL]


def test_url_no_valida(client: TestClient, admin_user, fake_preview) -> None:
    respuesta = client.get("/tracks/preview?url=esto-no-es-una-url", headers=headers(client))
    assert respuesta.status_code == 400
    assert fake_preview["construidos"] == []  # ni se intenta


def test_si_falla_la_descarga_se_explica(
    client: TestClient, admin_user, fake_preview
) -> None:
    fake_preview["error"] = DownloadError("El video es privado.")
    respuesta = client.get(f"/tracks/preview?url={URL}", headers=headers(client))
    assert respuesta.status_code == 502
    assert "privado" in respuesta.json()["detail"]


def test_la_cache_evita_volver_a_bajarlo(tmp_path, monkeypatch) -> None:
    """Pinchar dos veces el mismo candidato no debe salir a la red dos veces."""
    from app.core.config import settings
    from app.services import preview

    monkeypatch.setattr(settings, "music_dir", str(tmp_path))
    llamadas: list[str] = []

    def fake_run(args):
        llamadas.append(" ".join(args))
        # yt-dlp deja el fichero donde le dice --output
        destino = next(a for i, a in enumerate(args) if args[i - 1] == "--output")
        from pathlib import Path

        Path(destino).write_bytes(b"audio")
        return ""

    monkeypatch.setattr(preview, "_run", fake_run)
    monkeypatch.setattr(preview, "_base_args", lambda: ["yt-dlp"])

    primero = preview.build(URL)
    segundo = preview.build(URL)
    assert primero == segundo
    assert len(llamadas) == 1  # la segunda vez sale de la cache
    assert "--download-sections" in llamadas[0]


def test_la_cache_no_crece_sin_limite(tmp_path, monkeypatch) -> None:
    from app.core.config import settings
    from app.services import preview

    monkeypatch.setattr(settings, "music_dir", str(tmp_path))
    monkeypatch.setattr(settings, "preview_cache_files", 3)

    for i in range(6):
        (preview.cache_dir() / f"video{i}.m4a").write_bytes(b"x")
    preview._limpiar_cache()
    assert len(list(preview.cache_dir().glob("*.m4a"))) == 3
