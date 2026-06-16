"""Step 2: decide whether a learnable piano piece can be made from a song.

Pure, deterministic logic over per-stem energies so it is fully testable
without any audio. Three outcomes:

* FEASIBLE           -> we have pitched material (piano, vocal, or other lead)
                        to build a piano arrangement from.
* NOT_FEASIBLE       -> effectively only drums/percussion: no melody to keep.
* LOCKED_SOLO_PIANO  -> the song already *is* a complete solo piano work
                        (e.g. a Nocturne). Difficulty must not be synthesised;
                        we stop politely.
"""

from __future__ import annotations

from dataclasses import dataclass

from .models import FeasibilityReport, Source, StemEnergies, Verdict


@dataclass(frozen=True)
class Thresholds:
    # Below this share of pitched (non-drum) energy, the track is treated as
    # percussion-only and rejected.
    min_pitched_ratio: float = 0.15
    # A stem must carry at least this share of total energy to be considered a
    # usable lead source.
    lead_floor: float = 0.18
    # Piano this dominant, with everything else near-silent, means "solo piano".
    solo_piano_ratio: float = 0.65
    # Combined share allowed for all non-piano stems in the solo-piano case.
    solo_other_ceiling: float = 0.20
    # Total energy below this is treated as silence.
    silence_floor: float = 1e-4


DEFAULT = Thresholds()


def assess(energies: StemEnergies, thresholds: Thresholds = DEFAULT) -> FeasibilityReport:
    total = energies.total
    if total <= thresholds.silence_floor:
        return FeasibilityReport(
            verdict=Verdict.NOT_FEASIBLE,
            source=None,
            message=(
                "I couldn't find any audible music in that track. "
                "Could you try a different song?"
            ),
            detail={"total_energy": total},
        )

    ratios = {k: v / total for k, v in energies.as_dict().items()}
    pitched_ratio = energies.pitched / total
    non_piano = total - energies.piano
    non_piano_ratio = non_piano / total

    detail = {**ratios, "pitched_ratio": pitched_ratio}

    # --- Only drums / percussion: nothing melodic to arrange. -----------------
    if pitched_ratio < thresholds.min_pitched_ratio:
        return FeasibilityReport(
            verdict=Verdict.NOT_FEASIBLE,
            source=None,
            message=(
                "This track is almost entirely drums and percussion, so there's "
                "no melody or harmony to build a piano part around. "
                "Try a song that has singing or a melodic instrument."
            ),
            detail=detail,
        )

    # --- Already a complete solo-piano work: don't fake a difficulty. ---------
    if (
        ratios["piano"] >= thresholds.solo_piano_ratio
        and non_piano_ratio <= thresholds.solo_other_ceiling
    ):
        return FeasibilityReport(
            verdict=Verdict.LOCKED_SOLO_PIANO,
            source=Source.PIANO,
            message=(
                "This already sounds like a complete solo piano piece. Its "
                "difficulty is part of the composition, so I won't re-grade it. "
                "Learn it from the original score, or pick a song with vocals or "
                "a band arrangement if you'd like a graded version."
            ),
            detail=detail,
        )

    # --- Pick the lead source to transcribe. ----------------------------------
    # Preference order: an existing piano part, then the sung melody, then any
    # other melodic instrument.
    if ratios["piano"] >= thresholds.lead_floor:
        source = Source.PIANO
    elif ratios["vocals"] >= thresholds.lead_floor:
        source = Source.VOCAL
    elif max(ratios["guitar"], ratios["other"]) >= thresholds.lead_floor:
        source = Source.OTHER
    elif ratios["vocals"] > 0.0:
        # Weak but present vocal melody — still worth keeping.
        source = Source.VOCAL
    else:
        return FeasibilityReport(
            verdict=Verdict.NOT_FEASIBLE,
            source=None,
            message=(
                "I can hear pitched content but no clear melody to hang a piano "
                "part on (it's mostly bass and texture). Try a song with a "
                "stronger vocal or instrumental melody."
            ),
            detail=detail,
        )

    nice = {
        Source.PIANO: "There's a piano part here I can turn into a graded score.",
        Source.VOCAL: "I'll follow the sung melody and build the piano around it.",
        Source.OTHER: "I'll follow the lead instrument and build the piano around it.",
    }[source]
    return FeasibilityReport(
        verdict=Verdict.FEASIBLE,
        source=source,
        message=f"Good news — this song works. {nice}",
        detail=detail,
    )
