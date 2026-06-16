"""End-to-end tests of the symbolic arranger (no audio needed)."""

from music21 import chord as m21chord

from gradekeys.arrange import render
from gradekeys.models import HarmonyChord, MelodyNote, SongMaterial


def sample_song() -> SongMaterial:
    # A simple C-major tune over C and G chords, two bars of 4/4.
    melody = [
        MelodyNote(72, 0.0, 1.0),  # C5
        MelodyNote(74, 1.0, 1.0),  # D5
        MelodyNote(76, 2.0, 1.0),  # E5
        MelodyNote(77, 3.0, 1.0),  # F5
        MelodyNote(79, 4.0, 1.0),  # G5
        MelodyNote(81, 5.0, 1.0),  # A5
        MelodyNote(83, 6.0, 1.0),  # B5
        MelodyNote(84, 7.0, 1.0),  # C6
    ]
    harmony = [
        HarmonyChord("C", "maj", 0.0, 4.0),
        HarmonyChord("G", "maj", 4.0, 4.0),
    ]
    return SongMaterial(melody=melody, harmony=harmony, key="C", title="Scale Tune")


def _events(score):
    return list(score.recurse().notes)


def test_renders_two_staves_for_every_grade():
    song = sample_song()
    for g in range(1, 9):
        score = render(song, g)
        parts = list(score.parts)
        assert len(parts) == 2, f"grade {g} should have RH+LH"


def test_grade1_is_all_single_notes():
    score = render(sample_song(), 1)
    multi = [e for e in _events(score) if isinstance(e, m21chord.Chord) and len(e.pitches) > 1]
    assert multi == [], "grade 1 should contain no stacked chords"


def test_grade8_is_richer_than_grade1():
    song = sample_song()
    g1 = len(_events(render(song, 1)))
    g8 = len(_events(render(song, 8)))
    assert g8 > g1 * 2, f"grade 8 ({g8}) should be far denser than grade 1 ({g1})"


def test_high_grade_has_octave_doubling_in_melody():
    score = render(sample_song(), 8)
    rh = next(p for p in score.parts if p.id == "RH")
    has_octave = False
    for c in rh.recurse().getElementsByClass(m21chord.Chord):
        midis = sorted(p.midi for p in c.pitches)
        # Any two notes an exact octave apart (same pitch class, 12 semitones).
        if any(hi - lo == 12 for i, lo in enumerate(midis) for hi in midis[i + 1:]):
            has_octave = True
            break
    assert has_octave, "grade 8 right hand should double the melody at the octave"


def test_melody_is_preserved_in_top_voice():
    # The highest pitch at each melodic onset should track the original contour
    # (transposed by whole octaves at most).
    score = render(sample_song(), 3)
    rh = next(p for p in score.parts if p.id == "RH")
    tops = []
    for n in rh.recurse().notes:
        top = max(p.midi for p in n.pitches)
        tops.append(top % 12)
    # The original pitch-classes in order: C D E F G A B C
    expected = [0, 2, 4, 5, 7, 9, 11, 0]
    assert tops[: len(expected)] == expected
