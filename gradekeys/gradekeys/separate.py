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
