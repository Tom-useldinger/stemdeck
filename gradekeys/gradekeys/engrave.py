"""Engrave a music21 Score to a sheet-music PDF.

Engraver preference, best-effort and fully offline:
  1. MuseScore        (if the binary is on PATH)
  2. LilyPond         (if the binary is on PATH)
  3. verovio+cairosvg (pure-pip `pdf` extra — no external binary needed)
Whatever happens, MusicXML is always written so any notation app can open it.
"""

from __future__ import annotations

import io
import shutil
from dataclasses import dataclass
from pathlib import Path

from music21 import environment, stream


@dataclass
class EngraveResult:
    musicxml_path: Path
    pdf_path: Path | None
    renderer: str | None
    note: str


def _find_musescore() -> str | None:
    for name in ("mscore", "musescore", "MuseScore4", "mscore4", "MuseScore"):
        found = shutil.which(name)
        if found:
            return found
    return None


def engrave(score: stream.Score, out_basename: str | Path) -> EngraveResult:
    base = Path(out_basename)
    base.parent.mkdir(parents=True, exist_ok=True)

    xml_path = base.with_suffix(".musicxml")
    score.write("musicxml", fp=str(xml_path))

    mscore = _find_musescore()
    lily = shutil.which("lilypond")

    if mscore:
        env = environment.Environment()
        env["musicxmlPath"] = mscore
        env["musescoreDirectPNGPath"] = mscore
        pdf_path = base.with_suffix(".pdf")
        try:
            score.write("musicxml.pdf", fp=str(pdf_path))
            return EngraveResult(xml_path, pdf_path, "musescore",
                                 "Rendered PDF with MuseScore.")
        except Exception as exc:  # pragma: no cover - depends on local binary
            return EngraveResult(xml_path, None, None,
                                 f"MuseScore PDF render failed ({exc}); MusicXML written.")

    if lily:
        pdf_path = base.with_suffix(".pdf")
        try:
            score.write("lily.pdf", fp=str(pdf_path))
            return EngraveResult(xml_path, pdf_path, "lilypond",
                                 "Rendered PDF with LilyPond.")
        except Exception as exc:  # pragma: no cover
            return EngraveResult(xml_path, None, None,
                                 f"LilyPond PDF render failed ({exc}); MusicXML written.")

    pdf_path = base.with_suffix(".pdf")
    try:
        _render_verovio(xml_path, pdf_path)
        return EngraveResult(xml_path, pdf_path, "verovio",
                             "Rendered PDF with verovio (no external engraver needed).")
    except ImportError:
        return EngraveResult(
            xml_path, None, None,
            "No PDF engraver found. Wrote MusicXML. For PDFs either install the "
            "pure-pip engraver (pip install 'gradekeys[pdf]'), or install MuseScore "
            "(https://musescore.org) / LilyPond, or open the .musicxml in any "
            "notation app.",
        )
    except Exception as exc:  # pragma: no cover - depends on content
        return EngraveResult(xml_path, None, None,
                             f"verovio PDF render failed ({exc}); MusicXML written.")


def _render_verovio(xml_path: Path, pdf_path: Path) -> None:
    """Render MusicXML -> paginated PDF using verovio + cairosvg + pypdf."""
    import cairosvg
    import verovio
    from pypdf import PdfReader, PdfWriter

    tk = verovio.toolkit()
    tk.setOptions({
        "pageWidth": 2100,    # ~A4 portrait at verovio's default unit
        "pageHeight": 2970,
        "scale": 40,
        "footer": "none",
        "header": "none",
    })
    if not tk.loadFile(str(xml_path)):
        raise RuntimeError("verovio could not load the MusicXML")

    writer = PdfWriter()
    for page in range(1, tk.getPageCount() + 1):
        svg = tk.renderToSVG(page)
        page_pdf = cairosvg.svg2pdf(bytestring=svg.encode("utf-8"))
        for p in PdfReader(io.BytesIO(page_pdf)).pages:
            writer.add_page(p)
    with open(pdf_path, "wb") as fh:
        writer.write(fh)
