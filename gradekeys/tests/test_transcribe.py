"""Pure-logic tests for transcription cleanup and the notation grid floor.

These need no audio: they exercise the deterministic helpers that turn raw,
frame-level pitch data into notation-friendly notes.
"""

from gradekeys.arrange import _MIN_GRID, _quantise
from gradekeys.models import MelodyNote
from gradekeys.transcribe import _clean_segmentation


def test_short_glissando_notes_are_absorbed():
    # A 0.25-beat blip between two sustained notes (a pitch-tracker artifact).
    notes = [
        MelodyNote(60, 0.0, 1.0),
        MelodyNote(61, 1.0, 0.25),   # artifact
        MelodyNote(62, 1.25, 1.0),
    ]
    cleaned = _clean_segmentation(notes, min_beats=0.3)
    pitches = [n.pitch for n in cleaned]
    assert pitches == [60, 62], "the short in-between note should be dropped"
    # The preceding note is extended to cover the gap.
    assert cleaned[0].duration == 1.25


def test_real_eighth_notes_survive_cleanup():
    notes = [MelodyNote(60, i * 0.5, 0.5) for i in range(4)]
    assert len(_clean_segmentation(notes, min_beats=0.3)) == 4


def test_quantise_never_finer_than_a_sixteenth():
    # Even with grid 0 (high grades), durations snap to the 16th-note floor.
    off, dur = _quantise(1.01, 0.97, grid=0.0)
    assert dur % _MIN_GRID == 0
    assert (off / _MIN_GRID) == round(off / _MIN_GRID)
    assert dur >= _MIN_GRID
