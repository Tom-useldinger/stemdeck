from gradekeys.feasibility import assess
from gradekeys.models import Source, StemEnergies, Verdict


def test_silence_is_rejected():
    r = assess(StemEnergies())
    assert r.verdict is Verdict.NOT_FEASIBLE
    assert not r.can_continue


def test_drums_only_is_rejected():
    r = assess(StemEnergies(drums=0.9, other=0.02))
    assert r.verdict is Verdict.NOT_FEASIBLE
    assert "drums" in r.message.lower()


def test_solo_piano_is_locked():
    r = assess(StemEnergies(piano=0.9, other=0.02, drums=0.01))
    assert r.verdict is Verdict.LOCKED_SOLO_PIANO
    assert r.source is Source.PIANO
    assert not r.can_continue


def test_band_with_piano_is_feasible_from_piano():
    r = assess(StemEnergies(vocals=0.2, drums=0.2, bass=0.2, piano=0.3, other=0.1))
    assert r.verdict is Verdict.FEASIBLE
    assert r.source is Source.PIANO


def test_vocal_song_is_feasible_from_vocals():
    r = assess(StemEnergies(vocals=0.45, drums=0.25, bass=0.2, other=0.1))
    assert r.verdict is Verdict.FEASIBLE
    assert r.source is Source.VOCAL


def test_weak_vocal_still_kept():
    r = assess(StemEnergies(vocals=0.05, bass=0.4, other=0.4, drums=0.15))
    # No stem clears the lead floor except via the weak-vocal fallback or other.
    assert r.verdict is Verdict.FEASIBLE
