"""Plain data structures shared across the pipeline.

These are deliberately framework-free so the deterministic core (feasibility,
grading, arrangement) can be exercised in tests without any audio dependency.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


@dataclass(frozen=True)
class MelodyNote:
    """A single melodic event.

    pitch:    MIDI note number (60 = middle C). ``None`` represents a rest.
    offset:   start position in quarter-length beats from the start of the piece.
    duration: length in quarter-length beats.
    """

    pitch: int | None
    offset: float
    duration: float

    @property
    def is_rest(self) -> bool:
        return self.pitch is None


@dataclass(frozen=True)
class HarmonyChord:
    """A harmonic region (one chord) of the song.

    root:     pitch class name, e.g. "C", "F#", "Bb".
    quality:  "maj", "min", "dom7", "maj7", "min7", "dim", "aug", "sus4"...
    offset:   start position in quarter-length beats.
    duration: length in quarter-length beats.
    """

    root: str
    quality: str
    offset: float
    duration: float


@dataclass
class SongMaterial:
    """Everything the arranger needs: the tune plus its harmony.

    This is the hand-off point between the (audio, fuzzy) transcription stage
    and the (symbolic, deterministic) arrangement stage.
    """

    melody: list[MelodyNote]
    harmony: list[HarmonyChord]
    key: str = "C"           # e.g. "C", "A-" (A minor in music21 notation)
    tempo_bpm: float = 100.0
    time_signature: str = "4/4"
    title: str = "Untitled"

    @property
    def end(self) -> float:
        ends = [n.offset + n.duration for n in self.melody]
        ends += [c.offset + c.duration for c in self.harmony]
        return max(ends) if ends else 0.0


class Source(str, Enum):
    """Where the pitched material that drives the arrangement came from."""

    PIANO = "piano"        # an existing piano part was transcribed
    VOCAL = "vocal"        # the sung melody was transcribed and harmonised
    OTHER = "other"        # melodic instrument (guitar/synth lead, etc.)


@dataclass
class StemEnergies:
    """Per-stem loudness (RMS, 0..1-ish) used for feasibility & solo detection.

    Mirrors StemDeck's six-stem layout so this can be fed directly from a
    Demucs separation, but any subset works.
    """

    vocals: float = 0.0
    drums: float = 0.0
    bass: float = 0.0
    guitar: float = 0.0
    piano: float = 0.0
    other: float = 0.0

    def as_dict(self) -> dict[str, float]:
        return {
            "vocals": self.vocals,
            "drums": self.drums,
            "bass": self.bass,
            "guitar": self.guitar,
            "piano": self.piano,
            "other": self.other,
        }

    @property
    def total(self) -> float:
        return sum(self.as_dict().values())

    @property
    def pitched(self) -> float:
        """Energy in stems that can carry pitch (everything except drums)."""
        return self.total - self.drums


class Verdict(str, Enum):
    FEASIBLE = "feasible"
    NOT_FEASIBLE = "not_feasible"
    # Source is an existing, complete solo-piano work (likely classical):
    # difficulty must not be synthetically altered.
    LOCKED_SOLO_PIANO = "locked_solo_piano"


@dataclass
class FeasibilityReport:
    verdict: Verdict
    source: Source | None
    message: str
    detail: dict[str, float] = field(default_factory=dict)

    @property
    def can_continue(self) -> bool:
        return self.verdict is Verdict.FEASIBLE
