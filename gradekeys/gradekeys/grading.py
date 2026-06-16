"""Grade 1-8 arrangement specifications.

Each grade maps to a bundle of deterministic parameters that ``arrange.py``
applies. The progression mirrors how real graded piano repertoire scales up:

    Grade 1-2  single-note melody, very simple held bass
    Grade 3-4  melody intact, triads / simple broken-chord bass
    Grade 5-6  octave accents, broken chords & arpeggios, first 7th chords
    Grade 7-8  full voicings, wide arpeggios, extended chords, fills & ornaments

The same input melody + harmony therefore produces a recognisably *same song*
that is progressively richer and harder to play.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GradeSpec:
    grade: int

    # --- Melody (right hand) --------------------------------------------------
    # Quantise melody onsets/durations to this beat grid (larger = simpler).
    # e.g. 1.0 = quarter-note grid, 0.5 = eighth-note grid, 0.0 = leave as-is.
    rhythm_grid: float
    # Add harmony notes beneath the melody: "none", "thirds", or "full" (triad).
    rh_harmony: str
    # Double the melody an octave below on strong beats (fuller, harder).
    rh_octave_doubling: bool
    # Add ornaments (grace notes / turns) on long melody notes.
    ornaments: bool
    # Fill melodic rests with short arpeggio flourishes (advanced).
    fill_rests: bool

    # --- Accompaniment (left hand) -------------------------------------------
    # "root"        single held root
    # "fifth"       open root + fifth
    # "triad"       block triad
    # "broken"      root-third-fifth broken chord
    # "alberti"     root-fifth-third-fifth Alberti figure
    # "arpeggio"    one-octave arpeggio
    # "wide_arpeggio" arpeggio spanning two octaves
    lh_pattern: str
    # How many LH attacks per chord region (1 = one held event, 4 = quarters...).
    lh_subdivision: int
    # Chord vocabulary: "triad", "sevenths", or "extended" (adds 9ths).
    chord_vocab: str
    # Allow chord inversions for smoother voice-leading (slightly harder).
    use_inversions: bool


GRADES: dict[int, GradeSpec] = {
    1: GradeSpec(
        grade=1,
        rhythm_grid=1.0,
        rh_harmony="none",
        rh_octave_doubling=False,
        ornaments=False,
        fill_rests=False,
        lh_pattern="root",
        lh_subdivision=1,
        chord_vocab="triad",
        use_inversions=False,
    ),
    2: GradeSpec(
        grade=2,
        rhythm_grid=0.5,
        rh_harmony="none",
        rh_octave_doubling=False,
        ornaments=False,
        fill_rests=False,
        lh_pattern="fifth",
        lh_subdivision=1,
        chord_vocab="triad",
        use_inversions=False,
    ),
    3: GradeSpec(
        grade=3,
        rhythm_grid=0.5,
        rh_harmony="none",
        rh_octave_doubling=False,
        ornaments=False,
        fill_rests=False,
        lh_pattern="triad",
        lh_subdivision=2,
        chord_vocab="triad",
        use_inversions=False,
    ),
    4: GradeSpec(
        grade=4,
        rhythm_grid=0.25,
        rh_harmony="thirds",
        rh_octave_doubling=False,
        ornaments=False,
        fill_rests=False,
        lh_pattern="broken",
        lh_subdivision=2,
        chord_vocab="triad",
        use_inversions=True,
    ),
    5: GradeSpec(
        grade=5,
        rhythm_grid=0.25,
        rh_harmony="thirds",
        rh_octave_doubling=True,
        ornaments=False,
        fill_rests=False,
        lh_pattern="alberti",
        lh_subdivision=4,
        chord_vocab="sevenths",
        use_inversions=True,
    ),
    6: GradeSpec(
        grade=6,
        rhythm_grid=0.0,
        rh_harmony="thirds",
        rh_octave_doubling=True,
        ornaments=True,
        fill_rests=False,
        lh_pattern="arpeggio",
        lh_subdivision=4,
        chord_vocab="sevenths",
        use_inversions=True,
    ),
    7: GradeSpec(
        grade=7,
        rhythm_grid=0.0,
        rh_harmony="full",
        rh_octave_doubling=True,
        ornaments=True,
        fill_rests=True,
        lh_pattern="arpeggio",
        lh_subdivision=8,
        chord_vocab="extended",
        use_inversions=True,
    ),
    8: GradeSpec(
        grade=8,
        rhythm_grid=0.0,
        rh_harmony="full",
        rh_octave_doubling=True,
        ornaments=True,
        fill_rests=True,
        lh_pattern="wide_arpeggio",
        lh_subdivision=8,
        chord_vocab="extended",
        use_inversions=True,
    ),
}


def spec_for(grade: int) -> GradeSpec:
    if grade not in GRADES:
        raise ValueError(f"grade must be 1-8, got {grade!r}")
    return GRADES[grade]
