"""Normalizacion de titulos y claves: la parte que decide si dos canciones son
la misma y como se ve el nombre en la biblioteca."""

import pytest

from app.core.text import normalize_key, slugify, split_artist_title


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [
        ("Warm-Up  Chill!", "warm-up-chill"),
        ("  OCHENTAS ", "ochentas"),
        ("Ochentas", "ochentas"),
        ("Británica", "britanica"),
    ],
)
def test_slugify(entrada: str, esperado: str) -> None:
    assert slugify(entrada) == esperado


@pytest.mark.parametrize(
    ("titulo", "canal", "artista", "cancion"),
    [
        ("Blur - Song 2 (Official Music Video)", "BlurVEVO", "Blur", "Song 2"),
        ("Song 2", "Blur - Topic", "Blur", "Song 2"),
        ("Daft Punk - Around The World [HD]", "Daft Punk", "Daft Punk", "Around The World"),
        # Lo que si distingue una version de otra se conserva
        (
            "La Casa Azul - La Revolucion Sexual (Remix) (Official Video)",
            "elefant",
            "La Casa Azul",
            "La Revolucion Sexual (Remix)",
        ),
        ("Radiohead – Creep (Live at Glastonbury)", "Radiohead", "Radiohead", "Creep (Live at Glastonbury)"),
    ],
)
def test_split_artist_title(titulo: str, canal: str, artista: str, cancion: str) -> None:
    assert split_artist_title(titulo, canal) == (artista, cancion)


def test_normalize_key_iguala_escrituras_distintas() -> None:
    assert normalize_key("Blur", "Song 2 (Official Video)") == normalize_key("blur", "song 2")
    assert normalize_key(None, "Blur - Song 2") == normalize_key("Blur", "Song 2")


def test_normalize_key_distingue_canciones_distintas() -> None:
    assert normalize_key("Blur", "Song 2") != normalize_key("Blur", "Parklife")
