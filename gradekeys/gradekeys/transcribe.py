"""Audio -> symbolic notes (melody + harmony) for the arranger.

Two strategies:
  * polyphonic (piano stems): basic-pitch -> MIDI -> melody + chords     [transcribe extra]
  * monophonic (vocal/lead):  librosa pitch tracking -> melody           [audio extra]

Harmony is estimated from whatever pitched content is available (a coarse
per-window chord guess). Both paths are optional; the symbolic core does not
depend on them.
"""

from __future__ import annotations

from pathlib import Path

from .models import HarmonyChord, MelodyNote, SongMaterial, Source


def transcribe(audio_path: str | Path, source: Source, *,
               tempo_bpm: float = 100.0, key: str = "C",
               title: str = "Untitled") -> SongMaterial:
    """Dispatch to the right transcription strategy for the source type."""
    if source is Source.PIANO:
        melody, harmony = _transcribe_polyphonic(audio_path, tempo_bpm)
    else:
        melody = _transcribe_monophonic(audio_path, tempo_bpm)
        harmony = _harmony_from_melody(melody, key)
    return SongMaterial(
        melody=melody, harmony=harmony, key=key,
        tempo_bpm=tempo_bpm, title=title,
    )


def _transcribe_monophonic(audio_path, tempo_bpm) -> list[MelodyNote]:
    import librosa
    import numpy as np

    y, sr = librosa.load(str(audio_path), mono=True)
    f0, voiced, _ = librosa.pyin(
        y, fmin=librosa.note_to_hz("C2"), fmax=librosa.note_to_hz("C7"), sr=sr
    )
    hop = 512
    sec_per_frame = hop / sr
    beats_per_sec = tempo_bpm / 60.0

    notes: list[MelodyNote] = []
    cur_midi: int | None = None
    start_frame = 0

    def flush(end_frame: int):
        nonlocal cur_midi, start_frame
        if cur_midi is None:
            return
        dur_beats = max(0.25, (end_frame - start_frame) * sec_per_frame * beats_per_sec)
        off_beats = start_frame * sec_per_frame * beats_per_sec
        notes.append(MelodyNote(cur_midi, round(off_beats, 3), round(dur_beats, 3)))

    for i, (hz, v) in enumerate(zip(f0, voiced, strict=False)):
        midi = int(round(librosa.hz_to_midi(hz))) if (v and not np.isnan(hz)) else None
        if midi != cur_midi:
            flush(i)
            cur_midi = midi
            start_frame = i
    flush(len(f0))
    return _clean_segmentation(notes)


def _clean_segmentation(notes: list[MelodyNote], min_beats: float = 0.3) -> list[MelodyNote]:
    """Drop pitch-tracker glissando artifacts: very short notes between two
    sustained ones are absorbed into the preceding note (extending its length).
    """
    cleaned: list[MelodyNote] = []
    for n in notes:
        if not n.is_rest and n.duration < min_beats and cleaned and not cleaned[-1].is_rest:
            prev = cleaned[-1]
            cleaned[-1] = MelodyNote(
                prev.pitch, prev.offset,
                round(n.offset + n.duration - prev.offset, 3),
            )
            continue
        cleaned.append(n)
    return cleaned


def _transcribe_polyphonic(audio_path, tempo_bpm):
    from basic_pitch import ICASSP_2022_MODEL_PATH
    from basic_pitch.inference import predict

    _model_out, midi_data, _note_events = predict(str(audio_path), ICASSP_2022_MODEL_PATH)
    beats_per_sec = tempo_bpm / 60.0

    events = []
    for inst in midi_data.instruments:
        for n in inst.notes:
            events.append((n.start, n.end, n.pitch))
    events.sort()

    # Melody = highest sounding pitch per onset window; harmony = the rest.
    melody: list[MelodyNote] = []
    for start, end, pitch in events:
        off = round(start * beats_per_sec, 3)
        dur = max(0.25, round((end - start) * beats_per_sec, 3))
        melody.append(MelodyNote(pitch, off, dur))
    harmony = _harmony_from_events(events, beats_per_sec)
    return melody, harmony


def _harmony_from_events(events, beats_per_sec) -> list[HarmonyChord]:
    # Coarse: one chord per bar-ish window, rooted on the most common bass pc.
    if not events:
        return []
    span = max(e[1] for e in events)
    window = 4.0 / beats_per_sec  # ~one 4/4 bar in seconds
    chords: list[HarmonyChord] = []
    t = 0.0
    names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
    while t < span:
        in_win = [p for (s, e, p) in events if s < t + window and e > t]
        if in_win:
            root_pc = min(in_win) % 12
            chords.append(HarmonyChord(names[root_pc], "maj",
                                       round(t * beats_per_sec, 3),
                                       round(window * beats_per_sec, 3)))
        t += window
    return chords


def _harmony_from_melody(melody: list[MelodyNote], key_str: str) -> list[HarmonyChord]:
    """Pick a simple diatonic chord per bar from the melody notes it spans."""
    from music21 import key as m21key

    k = m21key.Key(key_str)
    scale = [p.pitchClass for p in k.getScale().getPitches("C2", "C3")]
    names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
    pitched = [m for m in melody if m.pitch is not None]
    if not pitched:
        return []
    end = max(m.offset + m.duration for m in pitched)

    chords: list[HarmonyChord] = []
    bar = 4.0
    t = 0.0
    while t < end:
        in_bar = [m.pitch % 12 for m in pitched if t <= m.offset < t + bar]
        if in_bar:
            # Root = scale degree under the most prominent melody pitch.
            top_pc = max(set(in_bar), key=in_bar.count)
            root_pc = min(scale, key=lambda pc: min((pc - top_pc) % 12, (top_pc - pc) % 12))
            quality = "min" if k.mode == "minor" and root_pc == scale[0] else "maj"
            chords.append(HarmonyChord(names[root_pc], quality, t, bar))
        else:
            chords.append(HarmonyChord(names[scale[0]], "maj", t, bar))
        t += bar
    return chords
