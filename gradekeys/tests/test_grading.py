import pytest

from gradekeys.arrange import _chord_intervals
from gradekeys.grading import GRADES, spec_for
from gradekeys.models import HarmonyChord


def test_all_eight_grades_defined():
    assert sorted(GRADES) == list(range(1, 9))


def test_spec_for_rejects_out_of_range():
    with pytest.raises(ValueError):
        spec_for(0)
    with pytest.raises(ValueError):
        spec_for(9)


def test_chord_vocab_sizes():
    c = HarmonyChord("C", "maj", 0, 4)
    assert len(_chord_intervals(c, "triad")) == 3
    assert len(_chord_intervals(c, "sevenths")) == 4
    assert len(_chord_intervals(c, "extended")) == 5


def test_seventh_quality_always_has_seventh():
    c = HarmonyChord("D", "min7", 0, 4)
    ivs = _chord_intervals(c, "triad")  # even as a "triad" vocab
    assert 10 in ivs  # the minor seventh is intrinsic to the quality


def test_difficulty_progression_is_monotonic():
    # Left-hand attack density and chord richness should not decrease with grade.
    subdivs = [GRADES[g].lh_subdivision for g in range(1, 9)]
    assert subdivs == sorted(subdivs)
    vocab_rank = {"triad": 0, "sevenths": 1, "extended": 2}
    ranks = [vocab_rank[GRADES[g].chord_vocab] for g in range(1, 9)]
    assert ranks == sorted(ranks)
