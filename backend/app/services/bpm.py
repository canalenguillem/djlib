"""Deteccion de tempo.

Se usa `soundstretch` (SoundTouch), que en una prueba contra metronomos exactos
acerto 90, 110, 128 y 140 BPM con menos de un 0,1 % de error. Solo fallo a 174,
donde devolvio 58 (un tercio). La alternativa, derivar el tempo de las marcas de
`aubiotrack`, fallaba a la mitad de tempo a partir de 128, y librosa habria
anadido 400 MB a la imagen para este unico uso.

Aun asi, ninguna deteccion automatica es infalible: el BPM se puede corregir a
mano desde la biblioteca, y esa correccion no se pisa.
"""

from __future__ import annotations

import logging
import subprocess
import tempfile
from pathlib import Path

from app.core.config import settings

logger = logging.getLogger(__name__)


class BpmError(RuntimeError):
    pass


def _to_wav(origen: Path, destino: Path) -> None:
    """soundstretch solo lee WAV; el resto lo convierte ffmpeg."""
    resultado = subprocess.run(
        [
            "ffmpeg", "-y", "-i", str(origen),
            # Mono y 44,1 kHz: el analisis no mejora con estereo y va mas rapido.
            "-ac", "1", "-ar", "44100",
            # Con los primeros minutos sobra, y evita analizar temas larguisimos
            "-t", str(settings.bpm_analysis_seconds),
            str(destino),
        ],
        capture_output=True,
        timeout=settings.bpm_timeout_seconds,
        check=False,
    )
    if resultado.returncode != 0 or not destino.exists():
        raise BpmError("No se pudo preparar el audio para analizarlo.")


def _parse(salida: str) -> float | None:
    for linea in salida.splitlines():
        if "bpm" not in linea.lower():
            continue
        for parte in linea.replace("=", " ").replace(":", " ").split():
            try:
                valor = float(parte)
            except ValueError:
                continue
            if 20 < valor < 400:
                return valor
    return None


def normalize(bpm: float) -> int:
    """Corrige los errores de octava mas comunes.

    Un detector puede devolver la mitad o el doble del tempo real. Se lleva el
    valor a la horquilla en la que vive la musica de baile, que es donde estara
    casi siempre lo que hay en la biblioteca.
    """
    valor = bpm
    for _ in range(4):
        if valor < settings.bpm_min:
            valor *= 2
        elif valor > settings.bpm_max:
            valor /= 2
        else:
            break
    return int(round(valor))


def analyze(path: Path) -> int | None:
    """BPM de un fichero, o None si no se ha podido determinar."""
    if not path.exists():
        raise BpmError("El fichero de audio no existe.")

    with tempfile.TemporaryDirectory() as carpeta:
        wav = Path(carpeta) / "analisis.wav"
        _to_wav(path, wav)
        try:
            resultado = subprocess.run(
                ["soundstretch", str(wav), "-bpm"],
                capture_output=True,
                text=True,
                timeout=settings.bpm_timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise BpmError("El analisis de tempo ha tardado demasiado.") from exc

    crudo = _parse(resultado.stdout + resultado.stderr)
    if crudo is None:
        logger.info("soundstretch no ha detectado tempo en %s", path.name)
        return None
    return normalize(crudo)
