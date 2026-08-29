"""Eleccion de resultado en una busqueda.

Buscar "Bad Bunny Nueva Yirky" en YouTube devuelve como primer resultado un mix
de 42 minutos. Coger ciegamente el primero llena la biblioteca de
recopilatorios, asi que se elige por duracion.
"""

import json

import pytest

from app.core.config import settings
from app.services.downloader import DownloadError, _parse_info, search_query


def _entrada(i: int, duracion: int | None) -> dict:
    return {
        "id": f"video{i}",
        "title": f"Resultado {i}",
        "duration": duracion,
        "uploader": "Canal",
    }


def busqueda(*duraciones: int | None) -> str:
    """Forma real de la salida de yt-dlp en una busqueda: un JSON por linea."""
    return "\n".join(json.dumps(_entrada(i, d)) for i, d in enumerate(duraciones))


def busqueda_plana(*duraciones: int | None) -> str:
    """Forma alternativa, la de --flat-playlist: un objeto con las entradas."""
    entries = [_entrada(i, d) for i, d in enumerate(duraciones)]
    return json.dumps({"_type": "playlist", "entries": entries})


def test_se_piden_varios_candidatos() -> None:
    assert search_query("Song 2", "Blur") == f"ytsearch{settings.search_candidates}:Blur Song 2"


def test_se_descarta_el_mix_largo_y_se_coge_la_cancion() -> None:
    # 42 min, luego 3 min: el caso real que se colo en la biblioteca
    info = _parse_info(busqueda(2527, 180, 200))
    assert info.video_id == "video1"
    assert info.duration_seconds == 180


def test_si_el_primero_ya_dura_como_una_cancion_se_coge_ese() -> None:
    info = _parse_info(busqueda(200, 180))
    assert info.video_id == "video0"


def test_los_resultados_sin_duracion_no_se_eligen() -> None:
    info = _parse_info(busqueda(None, 210))
    assert info.video_id == "video1"


def test_si_todos_son_largos_se_avisa_en_vez_de_bajar_un_mix() -> None:
    with pytest.raises(DownloadError) as exc:
        _parse_info(busqueda(2527, 3400, 5000))
    mensaje = str(exc.value)
    assert "demasiado largos" in mensaje
    assert "42 min" in mensaje  # se dice cuanto duran los que se han descartado


def test_tambien_funciona_con_la_forma_de_flat_playlist() -> None:
    info = _parse_info(busqueda_plana(2527, 180))
    assert info.video_id == "video1"


def test_busqueda_sin_resultados() -> None:
    with pytest.raises(DownloadError, match="ningun resultado"):
        _parse_info(json.dumps({"_type": "playlist", "entries": []}))
    with pytest.raises(DownloadError, match="ningun resultado"):
        _parse_info("")


def test_una_url_directa_no_pasa_por_la_eleccion() -> None:
    payload = json.dumps(
        {"id": "abc", "title": "Blur - Song 2", "duration": 2000, "uploader": "Canal"}
    )
    info = _parse_info(payload)
    assert info.video_id == "abc"
    assert info.duration_seconds == 2000
