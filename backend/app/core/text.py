import re
import unicodedata


def _strip_accents(value: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", value) if not unicodedata.combining(c)
    )


def slugify(value: str) -> str:
    """"Warm-Up  Chill!" -> "warm-up-chill". Base de la unicidad de etiquetas."""
    value = _strip_accents(value).lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-")


# Ruido habitual en los titulos de YouTube que no distingue una cancion de otra.
_NOISE = re.compile(
    r"\b(official|video|videoclip|audio|lyrics?|hd|hq|4k|remaster(ed)?|"
    r"letra|con letra|full album|mv|m/v)\b",
    re.IGNORECASE,
)


def normalize_key(artist: str | None, title: str) -> str:
    """Clave para detectar la misma cancion escrita de formas distintas.

    "Blur - Song 2 (Official Video)" y "blur song 2" colapsan en la misma clave.
    Es una red secundaria: la deduplicacion fiable es por id de video.
    """
    raw = f"{artist or ''} {title}"
    raw = _strip_accents(raw).lower()
    raw = re.sub(r"[\(\[\{].*?[\)\]\}]", " ", raw)  # quita (Official Video), [HD]...
    raw = _NOISE.sub(" ", raw)
    raw = re.sub(r"[^a-z0-9]+", " ", raw)
    return " ".join(sorted(raw.split()))[:400]


# Cosas que YouTube mete en el titulo y que no distinguen una cancion de otra.
# Ojo: "(Remix)", "(Live)" o "(feat. X)" SI importan y se conservan.
_BRACKET_NOISE = re.compile(
    r"[\(\[]\s*(?:[^\)\]]*\b(?:official|video|videoclip|audio|lyrics?|lyric|"
    r"hd|hq|4k|full\s*hd|visualizer|letra|con\s+letra|mv|m/v|"
    r"clip\s*oficial|video\s*oficial|audio\s*oficial)\b[^\)\]]*)\s*[\)\]]",
    re.IGNORECASE,
)

_TOPIC_SUFFIX = re.compile(r"\s*-\s*topic$", re.IGNORECASE)

# Separadores que la gente usa entre artista y titulo
_SEPARATORS = (" - ", " – ", " — ", " | ")


def clean_title(raw_title: str) -> str:
    """"Blur - Song 2 (Official Music Video)" -> "Blur - Song 2"."""
    cleaned = _BRACKET_NOISE.sub(" ", raw_title)
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    return cleaned.strip(" -–—|·.")


def split_artist_title(raw_title: str, uploader: str | None) -> tuple[str | None, str]:
    """Separa "Artista - Titulo" en sus dos partes.

    Si el titulo no trae separador, se usa el canal como artista, quitandole el
    sufijo "- Topic" que YouTube anade a los canales automaticos de musica.
    """
    cleaned = clean_title(raw_title)

    for separator in _SEPARATORS:
        if separator in cleaned:
            left, _, right = cleaned.partition(separator)
            left, right = left.strip(), right.strip()
            if left and right:
                return left, right

    channel = _TOPIC_SUFFIX.sub("", (uploader or "").strip()) or None
    return channel, cleaned or raw_title.strip()
