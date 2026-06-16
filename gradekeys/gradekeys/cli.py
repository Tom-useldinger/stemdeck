"""Interactive 3-step command line: song -> feasibility -> graded PDF.

    gradekeys                      # fully interactive (asks questions)
    gradekeys "let it be"          # name; still asks for the grade
    gradekeys song.wav --grade 5   # non-interactive
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

from .models import Verdict


def _prompt(msg: str) -> str:
    try:
        return input(msg).strip()
    except (EOFError, KeyboardInterrupt):
        print()
        sys.exit(1)


def _ask_grade() -> int:
    while True:
        raw = _prompt("Which grade would you like to learn? (1-8): ")
        if raw.isdigit() and 1 <= int(raw) <= 8:
            return int(raw)
        print("  Please enter a whole number from 1 to 8.")


def run(request: str, grade: int | None, out: Path, workdir: Path) -> int:
    from . import acquire, feasibility, separate, transcribe
    from .arrange import render
    from .engrave import engrave

    # --- Step 1: get the audio ------------------------------------------------
    print(f"\n[1/3] Finding “{request}” …")
    try:
        got = acquire.acquire(request, workdir / "audio")
    except acquire.AcquireError as exc:
        print(f"  ✗ {exc}")
        return 2
    print(f"  ✓ Got: {got.title}  ({got.source_kind})")

    # --- Step 2: feasibility --------------------------------------------------
    print("\n[2/3] Checking whether a piano part is possible …")
    try:
        stem_dir = separate.separate(got.audio_path, workdir / "stems")
        energies = separate.measure_energies(stem_dir)
    except Exception as exc:  # demucs/optional deps missing or failed
        print(f"  ! Couldn't separate stems ({exc}).")
        print("    Install the separation extra:  pip install 'gradekeys[separate]'")
        return 3

    report = feasibility.assess(energies)
    print(f"  {report.message}")
    if report.verdict is not Verdict.FEASIBLE:
        # Polite stop for both percussion-only and locked solo-piano cases.
        return 0 if report.verdict is Verdict.LOCKED_SOLO_PIANO else 1

    # --- Step 3: grade + arrange + engrave ------------------------------------
    if grade is None:
        grade = _ask_grade()
    print(f"\n[3/3] Arranging at grade {grade} and engraving …")
    material = transcribe.transcribe(
        got.audio_path, report.source, title=got.title
    )
    score = render(material, grade)
    result = engrave(score, out)
    print(f"  ✓ MusicXML: {result.musicxml_path}")
    if result.pdf_path:
        print(f"  ✓ PDF:      {result.pdf_path}  ({result.renderer})")
    else:
        print(f"  ! {result.note}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="gradekeys",
        description="Turn a song into a learnable, grade-adjustable piano score.",
    )
    ap.add_argument("request", nargs="?", help="song name, URL, or audio file path")
    ap.add_argument("--grade", type=int, choices=range(1, 9), metavar="1-8",
                    help="target difficulty grade (skips the prompt)")
    ap.add_argument("--out", type=Path, default=Path("score"),
                    help="output basename (default: ./score)")
    ap.add_argument("--workdir", type=Path, default=None,
                    help="scratch dir for audio/stems (default: a temp dir)")
    args = ap.parse_args(argv)

    print("🎹  GradeKeys")
    request = args.request or _prompt("What song would you like to learn? ")
    if not request:
        print("No song given. Bye!")
        return 1

    workdir = args.workdir or Path(tempfile.mkdtemp(prefix="gradekeys-"))
    try:
        return run(request, args.grade, args.out, workdir)
    except KeyboardInterrupt:  # pragma: no cover
        print("\nCancelled.")
        return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
