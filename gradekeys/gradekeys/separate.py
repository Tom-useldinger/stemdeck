"""Optional source separation + per-stem energy measurement.

Used by Step 2 (feasibility) to see whether a track has a piano part, a vocal
melody, or is just drums. Separation uses Demucs (the same model StemDeck uses);
energy measurement only needs librosa/soundfile from the ``audio`` extra.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from .models import StemEnergies

_STEMS = ("vocals", "drums", "bass", "guitar", "piano", "other")


def measure_energies(stem_dir: str | Path) -> StemEnergies:
    """RMS energy per stem from a directory of ``<name>.wav`` files."""
    import numpy as np
    import soundfile as sf

    stem_dir = Path(stem_dir)
    vals: dict[str, float] = {}
    for name in _STEMS:
        f = stem_dir / f"{name}.wav"
        if not f.exists():
            vals[name] = 0.0
            continue
        data, _ = sf.read(str(f), always_2d=True)
        vals[name] = float(np.sqrt(np.mean(np.square(data)))) if data.size else 0.0
    return StemEnergies(**vals)


def analyze_mix(audio_path: str | Path, max_seconds: float = 45.0) -> StemEnergies:
    """Approximate per-stem energies *without* source separation.

    A no-Demucs fallback for the feasibility check: harmonic/percussive
    separation estimates how much of the track is drums vs pitched, and a
    voiced-ratio estimate decides whether the pitched content is a clear melody
    (treated as "vocals") or general harmonic texture ("other"). Coarse, but
    enough to reject percussion-only tracks and route melodic songs forward.

    Note: solo-piano locking needs real separation and is not attempted here.
    """
    import librosa
    import numpy as np

    y, sr = librosa.load(str(audio_path), mono=True, duration=max_seconds)
    if y.size == 0:
        return StemEnergies()

    harm, perc = librosa.effects.hpss(y)

    def rms(x) -> float:
        return float(np.sqrt(np.mean(np.square(x)))) if x.size else 0.0

    drums = rms(perc)
    pitched = rms(harm)

    f0, voiced, _ = librosa.pyin(
        harm if harm.size else y,
        fmin=librosa.note_to_hz("C2"), fmax=librosa.note_to_hz("C7"), sr=sr,
    )
    voiced_ratio = float(np.nanmean(voiced.astype(float))) if voiced is not None else 0.0

    if voiced_ratio > 0.35:
        return StemEnergies(vocals=pitched, drums=drums, other=pitched * 0.2)
    return StemEnergies(other=pitched, drums=drums)


def separate(audio_path: str | Path, out_root: str | Path,
             model: str = "htdemucs_6s") -> Path:
    """Run Demucs and return the directory holding the six stem WAVs."""
    audio_path = Path(audio_path)
    out_root = Path(out_root)
    out_root.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable, "-m", "demucs",
        "-n", model,
        "--out", str(out_root),
        str(audio_path),
    ]
    subprocess.run(cmd, check=True)
    return out_root / model / audio_path.stem
