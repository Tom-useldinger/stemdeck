"""GradeKeys — turn any song into a learnable, grade-adjustable piano score."""

from __future__ import annotations

from .arrange import render
from .feasibility import assess
from .grading import GRADES, spec_for
from .models import (
    FeasibilityReport,
    HarmonyChord,
    MelodyNote,
    SongMaterial,
    Source,
    StemEnergies,
    Verdict,
)

__all__ = [
    "render",
    "assess",
    "GRADES",
    "spec_for",
    "FeasibilityReport",
    "HarmonyChord",
    "MelodyNote",
    "SongMaterial",
    "Source",
    "StemEnergies",
    "Verdict",
]

__version__ = "0.1.0"
