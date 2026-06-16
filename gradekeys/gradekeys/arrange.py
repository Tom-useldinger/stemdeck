"""The arrangement engine: SongMaterial + GradeSpec -> a music21 Score.

Everything here is deterministic and offline. The melody is treated as the
"truth" of the song (so the result always *sounds like* the song); the grade
spec controls how much harmonic and rhythmic richness is layered around it.
"""

from __future__ import annotations

from music21 import chord, clef, instrument, key, layout, meter, note, stream, tempo

from .grading import GradeSpec, spec_for
from .models import HarmonyChord, MelodyNote, SongMaterial

# Semitone offsets from the chord root for each quality.
_THIRD = {"maj": 4, "min": 3, "dim": 3, "aug": 4, "sus4": 5,
          "dom7": 4, "maj7": 4, "min7": 3}
_FIFTH = {"maj": 7, "min": 7, "dim": 6, "aug": 8, "sus4": 7,
          "dom7": 7, "maj7": 7, "min7": 7}
_SEVENTH = {"maj": 11, "min": 10, "dim": 9, "aug": 10, "sus4": 10,
            "dom7": 10, "maj7": 11, "min7": 10}
_NINTH = 14

_LH_BASE_MIDI = 48   # around C3 — comfortable left-hand home
_RH_TARGET = 72      # bring the melody's median to around C5
# Even when a grade doesn't simplify rhythm, snap to at least a 16th-note grid
# so transcribed durations stay representable in notation (no insane tuplets).
_MIN_GRID = 0.25


def render(material: SongMaterial, grade: int) -> stream.Score:
    """Build a complete, engravable two-stave piano score for ``grade``."""
    spec = spec_for(grade)
    k = _safe_key(material.key)
    scale_pcs = _scale_pcs(k)

    melody = _normalise_melody_register(material.melody)

    # A single instrument shared by both staves so the two parts read as one
    # piano, not two separate instruments.
    rh = stream.Part(id="RH")
    rh.insert(0, _piano_instrument(named=True))
    rh.insert(0, clef.TrebleClef())
    rh.insert(0, meter.TimeSignature(material.time_signature))
    rh.insert(0, k)
    rh.insert(0, _tempo_mark(material.tempo_bpm))

    lh = stream.Part(id="LH")
    lh.insert(0, _piano_instrument(named=False))
    lh.insert(0, clef.BassClef())
    lh.insert(0, meter.TimeSignature(material.time_signature))
    lh.insert(0, k)

    _build_right_hand(rh, melody, material.harmony, spec, scale_pcs)
    _build_left_hand(lh, material.harmony, spec)

    score = stream.Score()
    score.metadata = _metadata(material, grade)
    score.insert(0, rh)
    score.insert(0, lh)

    # Brace the two staves into a single grand staff and bar them together.
    grand_staff = layout.StaffGroup(
        [rh, lh], name="Piano", abbreviation="Pno.", symbol="brace"
    )
    grand_staff.barTogether = True
    score.insert(0, grand_staff)

    # Bar the parts and fill gaps with rests so the result is valid notation.
    score.makeNotation(inPlace=True)
    return score


def _piano_instrument(named: bool) -> instrument.Instrument:
    piano = instrument.Piano()
    # Only the top staff carries the visible label; the brace name comes from
    # the StaffGroup, so blank the per-part names to avoid "Piano" twice.
    piano.partName = ""
    piano.partAbbreviation = ""
    piano.instrumentName = "" if not named else ""
    return piano


def _tempo_mark(bpm: float) -> tempo.TempoText:
    # Use a text tempo with the Unicode quarter note so it renders everywhere,
    # including engravers whose music font lacks the metronome notehead glyph.
    tt = tempo.TempoText(f"♩ = {round(bpm)}")
    tt.placement = "above"
    return tt


# --------------------------------------------------------------------------- #
# Right hand: the melody, optionally thickened.
# --------------------------------------------------------------------------- #
def _build_right_hand(
    part: stream.Part,
    melody: list[MelodyNote],
    harmony: list[HarmonyChord],
    spec: GradeSpec,
    scale_pcs: list[int],
) -> None:
    for offset, dur, pitch in _prepare_melody_events(melody, spec.rhythm_grid):
        if pitch is None:  # a rest
            if spec.fill_rests and dur >= 1.0:
                _insert_fill(part, offset, dur, _chord_at(harmony, offset), spec)
            continue

        pitches = [pitch]

        # Harmony notes beneath the tune.
        if spec.rh_harmony == "thirds":
            pitches.append(_diatonic_third_below(pitch, scale_pcs))
        elif spec.rh_harmony == "full":
            pitches.extend(_chord_tones_below(pitch, _chord_at(harmony, offset)))

        # Octave doubling on strong beats for a fuller, harder texture.
        if spec.rh_octave_doubling and _is_strong_beat(offset):
            pitches.append(pitch - 12)

        pitches = sorted(set(pitches))

        # Ornament only when there's room for the grace note *and* a sustained
        # main note afterwards, so we never overrun the next event.
        if spec.ornaments and dur >= 2.0:
            _insert_ornamented(part, offset, dur, pitches, scale_pcs)
        else:
            part.insert(offset, _make_event(pitches, dur))


def _prepare_melody_events(
    melody: list[MelodyNote], grid: float
) -> list[tuple[float, float, int | None]]:
    """Quantise, de-duplicate, and clip the melody into a strictly sequential
    (non-overlapping) event list.

    Overlapping or coincident notes in a single staff make ``makeNotation``
    emit malformed ties; a monophonic-in-time event stream (chords are added
    later, vertically) avoids that entirely.
    """
    events: list[tuple[float, float, int | None]] = []
    for mn in melody:
        offset, dur = _quantise(mn.offset, mn.duration, grid)
        if dur > 0:
            events.append((offset, dur, mn.pitch))
    events.sort(key=lambda e: e[0])

    # Keep one event per onset (the first), then clip each to the next onset.
    deduped: list[tuple[float, float, int | None]] = []
    for off, dur, pitch in events:
        if deduped and abs(deduped[-1][0] - off) < 1e-6:
            continue
        deduped.append((off, dur, pitch))

    cleaned: list[tuple[float, float, int | None]] = []
    for i, (off, dur, pitch) in enumerate(deduped):
        if i + 1 < len(deduped):
            dur = min(dur, deduped[i + 1][0] - off)
        if dur > 0:
            cleaned.append((off, dur, pitch))
    return cleaned


# --------------------------------------------------------------------------- #
# Left hand: the accompaniment pattern.
# --------------------------------------------------------------------------- #
def _build_left_hand(part: stream.Part, harmony: list[HarmonyChord], spec: GradeSpec) -> None:
    for hc in harmony:
        intervals = _chord_intervals(hc, spec.chord_vocab)
        root = _root_midi(hc.root, _LH_BASE_MIDI)
        if spec.use_inversions:
            root = _voice_lead(root)
        tones = [root + iv for iv in intervals]
        for onset, dur, midis in _pattern_events(spec, hc, tones):
            part.insert(onset, _make_event(midis, dur))


def _pattern_events(spec: GradeSpec, hc: HarmonyChord, tones: list[int]):
    """Yield (onset, duration, [midi...]) events realising the LH pattern."""
    slot_ql = {1: None, 2: 2.0, 4: 1.0, 8: 0.5}[spec.lh_subdivision]
    if slot_ql is None:
        slots = [(hc.offset, hc.duration)]
    else:
        slots = []
        t = hc.offset
        end = hc.offset + hc.duration
        while t < end - 1e-6:
            slots.append((t, min(slot_ql, end - t)))
            t += slot_ql

    root = tones[0]
    fifth = root + (_FIFTH.get(hc.quality, 7))
    for i, (onset, dur) in enumerate(slots):
        pat = spec.lh_pattern
        if pat == "root":
            sel = [root]
        elif pat == "fifth":
            sel = [root, fifth]
        elif pat == "triad":
            sel = tones[:3]
        elif pat == "broken":
            sel = [tones[i % len(tones)]]
        elif pat == "alberti":
            order = [0, 2, 1, 2]
            sel = [tones[order[i % 4] % len(tones)]]
        elif pat == "arpeggio":
            asc = tones + tones[-2:0:-1]          # up then down
            sel = [asc[i % len(asc)]]
        elif pat == "wide_arpeggio":
            asc = tones + [t + 12 for t in tones]  # span two octaves, ascending
            sel = [asc[i % len(asc)]]
        else:  # pragma: no cover - defensive
            sel = [root]
        yield onset, dur, sel


# --------------------------------------------------------------------------- #
# Chord / pitch helpers
# --------------------------------------------------------------------------- #
def _chord_intervals(hc: HarmonyChord, vocab: str) -> list[int]:
    q = hc.quality
    intervals = [0, _THIRD.get(q, 4), _FIFTH.get(q, 7)]
    inherently_seventh = q.endswith("7")
    if vocab in ("sevenths", "extended") or inherently_seventh:
        intervals.append(_SEVENTH.get(q, 10))
    if vocab == "extended":
        intervals.append(_NINTH)
    return intervals


def _root_midi(root_name: str, target: int) -> int:
    from music21 import pitch as _pitch

    pc = _pitch.Pitch(root_name).pitchClass
    base = (target // 12) * 12 + pc
    # Pick the octave placement nearest the target.
    for cand in (base, base + 12, base - 12):
        if abs(cand - target) <= 6:
            return cand
    return base


def _voice_lead(root: int) -> int:
    """Keep the bass within a fifth of the LH home to smooth voice-leading."""
    while root - _LH_BASE_MIDI > 7:
        root -= 12
    while _LH_BASE_MIDI - root > 5:
        root += 12
    return root


def _scale_pcs(k: key.Key) -> list[int]:
    return sorted({p.pitchClass for p in k.getScale().getPitches("C2", "C3")})


def _diatonic_third_below(midi: int, scale_pcs: list[int]) -> int:
    pc = midi % 12
    if pc in scale_pcs:
        idx = scale_pcs.index(pc)
        target_pc = scale_pcs[(idx - 2) % len(scale_pcs)]
    else:
        target_pc = (pc - 4) % 12
    cand = midi - 1
    for _ in range(12):
        if cand % 12 == target_pc:
            return cand
        cand -= 1
    return midi - 3


def _chord_tones_below(midi: int, hc: HarmonyChord | None) -> list[int]:
    if hc is None:
        return []
    intervals = _chord_intervals(hc, "triad")
    root = _root_midi(hc.root, midi - 8)
    out = []
    for iv in intervals:
        t = root + iv
        while t >= midi:
            t -= 12
        if midi - t <= 12:
            out.append(t)
    return out


def _chord_at(harmony: list[HarmonyChord], offset: float) -> HarmonyChord | None:
    for hc in harmony:
        if hc.offset - 1e-6 <= offset < hc.offset + hc.duration - 1e-6:
            return hc
    return harmony[-1] if harmony else None


# --------------------------------------------------------------------------- #
# Melody shaping
# --------------------------------------------------------------------------- #
def _normalise_melody_register(melody: list[MelodyNote]) -> list[MelodyNote]:
    pitched = [m.pitch for m in melody if m.pitch is not None]
    if not pitched:
        return melody
    median = sorted(pitched)[len(pitched) // 2]
    shift = 0
    while median + shift < _RH_TARGET - 6:
        shift += 12
    while median + shift > _RH_TARGET + 6:
        shift -= 12
    if shift == 0:
        return melody
    return [
        m if m.pitch is None else MelodyNote(m.pitch + shift, m.offset, m.duration)
        for m in melody
    ]


def _quantise(offset: float, dur: float, grid: float) -> tuple[float, float]:
    grid = max(grid, _MIN_GRID)  # never finer than a 16th, even at high grades
    q_off = round(offset / grid) * grid
    q_dur = max(grid, round(dur / grid) * grid)
    return q_off, q_dur


def _is_strong_beat(offset: float) -> bool:
    return abs(offset - round(offset)) < 1e-6 and int(round(offset)) % 2 == 0


# --------------------------------------------------------------------------- #
# Ornaments & fills (advanced grades)
# --------------------------------------------------------------------------- #
def _insert_ornamented(part, offset, dur, pitches, scale_pcs):
    top = max(pitches)
    upper = _step_up(top, scale_pcs)
    part.insert(offset, _make_event([upper], 0.25))
    part.insert(offset + 0.25, _make_event(pitches, dur - 0.25))


def _insert_fill(part, offset, dur, hc, spec):
    if hc is None:
        part.insert(offset, note.Rest(quarterLength=dur))
        return
    intervals = _chord_intervals(hc, spec.chord_vocab)
    root = _root_midi(hc.root, _RH_TARGET - 12)
    tones = [root + iv for iv in intervals]
    step = 0.5
    t = offset
    i = 0
    while t < offset + dur - 1e-6:
        d = min(step, offset + dur - t)
        part.insert(t, _make_event([tones[i % len(tones)]], d))
        t += step
        i += 1


def _step_up(midi: int, scale_pcs: list[int]) -> int:
    pc = midi % 12
    if pc in scale_pcs:
        idx = scale_pcs.index(pc)
        target = scale_pcs[(idx + 1) % len(scale_pcs)]
    else:
        target = (pc + 2) % 12
    cand = midi + 1
    for _ in range(12):
        if cand % 12 == target:
            return cand
        cand += 1
    return midi + 2


# --------------------------------------------------------------------------- #
# music21 plumbing
# --------------------------------------------------------------------------- #
def _make_event(midis: list[int], dur: float):
    midis = sorted(set(midis))
    if len(midis) == 1:
        n = note.Note(midis[0])
        n.quarterLength = dur
        return n
    c = chord.Chord(midis)
    c.quarterLength = dur
    return c


def _safe_key(key_str: str) -> key.Key:
    try:
        return key.Key(key_str)
    except Exception:
        return key.Key("C")


def _metadata(material: SongMaterial, grade: int):
    from music21 import metadata as _md

    m = _md.Metadata()
    m.title = material.title
    m.composer = f"GradeKeys arrangement · Grade {grade}"
    return m
