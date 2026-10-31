"""Sugerencias de crate para una cancion recien bajada."""

from fastapi.testclient import TestClient

from app.models.track import Track
from tests.conftest import TestingSessionLocal
from tests.test_batches import crear_crate, headers
from tests.test_energy_export import crear_track


def poner(track_id: int, **campos) -> None:
    with TestingSessionLocal() as db:
        track = db.get(Track, track_id)
        for k, v in campos.items():
            setattr(track, k, v)
        db.commit()


def test_sugiere_por_artista_bpm_y_nombre(client: TestClient, admin_user, fake_downloader) -> None:
    h = headers(client)
    blur = crear_crate(client, h, "Britpop")
    rapido = crear_crate(client, h, "Techno")
    mashups = crear_crate(client, h, "Mashups")
    vacio = crear_crate(client, h, "Vacío")

    for vid, titulo, crate, bpm in [
        ("aaaaaaaaaa1", "Uno", blur, 120), ("aaaaaaaaaa2", "Dos", blur, 122),
        ("aaaaaaaaaa3", "Tres", rapido, 140), ("aaaaaaaaaa4", "Cuatro", rapido, 142),
    ]:
        tid = crear_track(client, h, vid, titulo, fake_downloader)
        poner(tid, bpm=bpm)
        client.post(f"/crates/{crate}/tracks", json={"track_id": tid}, headers=h)

    nueva = crear_track(client, h, "bbbbbbbbbb1", "Song 2 (Mashup)", fake_downloader)
    poner(nueva, bpm=121)

    sugerencias = client.get(f"/tracks/{nueva}/crate-suggestions", headers=h).json()
    ids = [s["crate_id"] for s in sugerencias]
    assert ids[0] == blur
    assert any("Blur" in m for m in sugerencias[0]["reasons"])
    assert mashups in ids
    # Techno tambien tiene temas de Blur, pero su BPM esta lejos: va detras
    assert rapido not in ids or ids.index(rapido) > ids.index(blur)
    assert vacio not in ids

    # Donde ya esta no se sugiere
    client.post(f"/crates/{blur}/tracks", json={"track_id": nueva}, headers=h)
    ids = [s["crate_id"] for s in client.get(f"/tracks/{nueva}/crate-suggestions", headers=h).json()]
    assert blur not in ids
