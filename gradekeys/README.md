# 🎹 GradeKeys

Turn any song into a **learnable, grade-adjustable piano score** — engraved as
sheet-music PDF.

GradeKeys is a standalone tool (it lives in this repo but does not depend on
StemDeck). Give it a song name, a URL, or an audio file and pick a difficulty
from **Grade 1 to Grade 8**; it works out whether a piano part is even possible,
then arranges the song at the level you asked for.

## The three steps

1. **Pick a song.** Type a name (resolved via search), paste a URL, or point at
   an audio file.
2. **Feasibility check.** GradeKeys separates the track into stems and decides:
   - has a **piano** part → arrange from it;
   - has a **sung melody** but no piano → transcribe the singing and *build* a
     piano part around it;
   - is essentially **just drums/percussion** → politely asks for another song;
   - is already a **complete solo-piano work** (e.g. a Nocturne) → stops,
     because the difficulty of such a piece is part of the composition and
     should not be synthetically re-graded.
3. **Choose a grade (1–8).** A simple sung tune asked for at Grade 8 gains
   octave doublings, 7th/extended chords, broken-chord and wide-arpeggio
   accompaniment, ornaments and fills — while still *sounding like the song*.
   The same tune at Grade 1 is a single-note melody over held bass roots.

## How the grading scales

| Grade | Right hand | Left hand | Harmony |
|------:|------------|-----------|---------|
| 1 | melody, quarter-note grid | held root | triads |
| 2 | melody | open fifth | triads |
| 3 | melody | block triads (half notes) | triads |
| 4 | + diatonic thirds | broken chords, inversions | triads |
| 5 | + octave accents | Alberti bass | **7th chords** |
| 6 | + ornaments | one-octave arpeggios | 7ths |
| 7 | full harmony, rest-fills | eighth-note arpeggios | **extended (9ths)** |
| 8 | dense voicing + octaves | **two-octave** arpeggios | extended |

The mapping lives in `gradekeys/grading.py` and is applied deterministically by
`gradekeys/arrange.py`.

## Install

The deterministic music-theory core needs only `music21`:

```sh
cd gradekeys
uv venv && uv pip install -e .
```

Optional extras enable the audio pipeline and PDF rendering:

```sh
uv pip install -e ".[pdf]"         # pure-pip PDF engraver (verovio) — no binary needed
uv pip install -e ".[audio]"       # yt-dlp + librosa: name/URL input & vocal transcription
uv pip install -e ".[separate]"    # demucs: stem separation for the feasibility check
uv pip install -e ".[transcribe]"  # basic-pitch: polyphonic (piano) transcription
uv pip install -e ".[web]"         # fastapi + uvicorn: the browser UI
uv pip install -e ".[dev]"         # pytest + ruff

# A practical combo that runs everything except polyphonic piano transcription:
uv pip install -e ".[audio,pdf,web]"
```

PDF rendering uses MuseScore or LilyPond if present on your PATH; otherwise the
pure-pip `pdf` extra (verovio + cairosvg + pypdf) renders PDFs with no external
binary. MusicXML is always written regardless, so you can open the result in any
notation app.

## Use

Interactive (asks the questions for you):

```sh
gradekeys
```

Or non-interactively:

```sh
gradekeys "let it be" --grade 4 --out ./let_it_be
gradekeys song.wav --grade 7
```

### Web UI

```sh
gradekeys-web          # serves http://127.0.0.1:8000
# or: uvicorn gradekeys.webapp:app --port 8000
```

A single page walks through the three steps: enter a song name / URL or upload
audio → see the feasibility verdict → pick a grade → the engraved PDF is shown
inline with download links. Feasibility uses Demucs when the `separate` extra is
installed and otherwise falls back to a no-separation **mix analysis**
(`separate.analyze_mix`), so the UI works with just the `audio` + `pdf` + `web`
extras (the solo-piano lock needs real separation and isn't attempted in the
fallback).

## Architecture

```
gradekeys/
├── models.py       # framework-free data structures (the symbolic hand-off point)
├── acquire.py      # Step 1: name / URL / file  -> local audio        [audio]
├── separate.py     # Demucs split + energies, or no-Demucs mix analysis  [separate/audio]
├── feasibility.py  # Step 2: feasible / not-feasible / locked-solo-piano  (pure)
├── transcribe.py   # audio -> melody + harmony (basic-pitch / librosa) [audio/transcribe]
├── grading.py      # Grade 1-8 rule definitions                         (pure)
├── arrange.py      # SongMaterial + grade -> music21 Score              (pure)
├── engrave.py      # Score -> MusicXML + PDF                            [pdf]
├── cli.py          # the interactive 3-step flow
└── webapp.py       # FastAPI browser UI for the same flow               [web]
```

The stages marked **(pure)** have no audio dependency and are covered by
`tests/` — run them with `pytest`. This is where the musical decisions live, so
they can be exercised and tuned without ever touching an audio file.

## Notes & limitations

- "Classical solo piano" detection is a heuristic (a track that is overwhelmingly
  piano with everything else near-silent). It deliberately errs toward *not*
  re-grading something that already stands on its own.
- Transcription quality depends on the source. A clean lead vocal or an isolated
  piano stem gives the best results; dense mixes are harder.
- The arranger optimises for *recognisable and playable*, not for reproducing
  every nuance of the original recording.
