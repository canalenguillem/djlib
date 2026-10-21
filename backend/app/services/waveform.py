"""Forma de onda en tres bandas, como la de los equipos Pioneer.

Los CDJ y rekordbox pintan la onda separando graves (azul), medios (ambar) y
agudos (blanco): de un vistazo se ve donde entra el bombo, donde hay un break
sin graves y donde vuelve la subida. Para eso no basta con la amplitud total;
hay que medir cada banda por separado.

ffmpeg parte la senal con tres filtros y la devuelve en tres canales; aqui solo
se resume cada tramo en su energia (RMS). Sin numpy: `math.sumprod` hace la
suma de cuadrados en C y una cancion de cuatro minutos sale en un segundo.
"""

from __future__ import annotations

import array
import math
import subprocess
from pathlib import Path

from app.core.config import settings


class WaveformError(RuntimeError):
    pass


# Frecuencia de muestreo del analisis. Llega de sobra para separar las tres
# bandas y tener seis veces menos muestras que procesar que a 44,1 kHz.
SAMPLE_RATE = 11025

# Cortes de banda en Hz, los mismos que usa a grandes rasgos rekordbox. Los
# filtros se aplican dos veces para que caigan con mas pendiente.
LOW_CUT = 200
HIGH_CUT = 2500

# El `map` de join es imprescindible: sin el, ffmpeg reordena los canales y los
# graves acaban en la tercera posicion.
_FILTER = (
    "[0:a]aformat=channel_layouts=mono,"
    f"aresample={SAMPLE_RATE},asplit=3[a][b][c];"
    f"[a]lowpass=f={LOW_CUT},lowpass=f={LOW_CUT}[low];"
    f"[b]highpass=f={LOW_CUT},lowpass=f={HIGH_CUT}[mid];"
    f"[c]highpass=f={HIGH_CUT},highpass=f={HIGH_CUT}[high];"
    "[low][mid][high]join=inputs=3:channel_layout=3.0:map=0.0-FL|1.0-FR|2.0-FC[out]"
)

BANDS = 3


def _decode(path: Path) -> array.array:
    try:
        resultado = subprocess.run(
            [
                "ffmpeg", "-v", "error", "-i", str(path),
                "-filter_complex", _FILTER, "-map", "[out]",
                "-f", "f32le", "-acodec", "pcm_f32le", "-",
            ],
            capture_output=True,
            timeout=settings.waveform_timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise WaveformError("Calcular la forma de onda ha tardado demasiado.") from exc
    if resultado.returncode != 0 or not resultado.stdout:
        raise WaveformError("No se pudo leer el audio para dibujar la onda.")

    muestras = array.array("f")
    # Un volcado cortado a mitad de muestra no deberia pasar, pero frombytes
    # se niega a leerlo: se descarta el resto.
    util = len(resultado.stdout) - len(resultado.stdout) % (4 * BANDS)
    muestras.frombytes(resultado.stdout[:util])
    return muestras


def summarize(band: array.array | list[float], bins: int) -> list[float]:
    """Energia RMS de cada uno de los `bins` tramos de una banda."""
    if not band:
        return [0.0] * bins
    paso = len(band) / bins
    salida = []
    for i in range(bins):
        inicio = int(i * paso)
        # Al menos una muestra por tramo, aunque la cancion sea cortisima
        tramo = band[inicio:max(int((i + 1) * paso), inicio + 1)]
        salida.append(math.sqrt(math.sumprod(tramo, tramo) / len(tramo)) if tramo else 0.0)
    return salida


def encode(low: list[float], mid: list[float], high: list[float]) -> bytes:
    """Empaqueta las tres bandas en un byte por banda y tramo (0-255).

    Las tres se escalan con el mismo maximo, para que conserven su peso real:
    en musica de baile los graves dominan y los agudos son un hilo encima,
    que es justo lo que se ve en un CDJ. La raiz cuadrada levanta los pasajes
    flojos, que en escala lineal quedarian casi invisibles.
    """
    pico = max([*low, *mid, *high, 0.0])
    if pico <= 0:
        return bytes(len(low) * BANDS)
    datos = bytearray()
    for valores in zip(low, mid, high):
        for valor in valores:
            datos.append(min(255, round(math.sqrt(valor / pico) * 255)))
    return bytes(datos)


def decode(datos: bytes) -> dict[str, list[int]]:
    """El inverso de `encode`, en el formato que devuelve la API."""
    return {
        "low": list(datos[0::BANDS]),
        "mid": list(datos[1::BANDS]),
        "high": list(datos[2::BANDS]),
    }


def analyze(path: Path) -> bytes:
    """Forma de onda de un fichero, lista para guardar."""
    if not path.exists():
        raise WaveformError("El fichero de audio no existe.")
    muestras = _decode(path)
    bins = settings.waveform_bins
    bandas = [summarize(muestras[i::BANDS], bins) for i in range(BANDS)]
    return encode(*bandas)
