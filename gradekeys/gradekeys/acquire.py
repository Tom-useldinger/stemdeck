"""Step 1: turn the user's request into a local audio file.

Three kinds of input are accepted:
  * a local audio file  -> used directly
  * a URL (YouTube etc.) -> downloaded with yt-dlp
  * a song *name*        -> resolved via a yt-dlp search, then downloaded

All of this needs the optional ``audio`` extra (yt-dlp). The import is guarded
so the rest of the package works without it.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

AUDIO_SUFFIXES = {".mp3", ".wav", ".flac", ".m4a", ".ogg", ".aac", ".opus"}


@dataclass
class Acquired:
    audio_path: Path
    title: str
    source_kind: str  # "file" | "url" | "search"


class AcquireError(RuntimeError):
    pass


def _require_ytdlp():
    try:
        import yt_dlp  # noqa: F401
    except ImportError as exc:  # pragma: no cover - optional dep
        raise AcquireError(
            "Resolving a name or URL needs yt-dlp. Install the audio extra:\n"
            "    pip install 'gradekeys[audio]'"
        ) from exc
    return yt_dlp


def acquire(request: str, out_dir: str | Path) -> Acquired:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    p = Path(request)
    if p.exists() and p.suffix.lower() in AUDIO_SUFFIXES:
        return Acquired(p, p.stem, "file")

    if request.startswith(("http://", "https://")):
        return _download(request, out_dir, kind="url")

    # Treat as a song name: search and take the best match.
    return _download(f"ytsearch1:{request}", out_dir, kind="search")


def _download(target: str, out_dir: Path, kind: str) -> Acquired:
    yt_dlp = _require_ytdlp()
    template = str(out_dir / "%(id)s.%(ext)s")
    opts = {
        "format": "bestaudio/best",
        "outtmpl": template,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "postprocessors": [
            {"key": "FFmpegExtractAudio", "preferredcodec": "wav"},
        ],
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(target, download=True)
        if "entries" in info:  # search result
            if not info["entries"]:
                raise AcquireError(f"No results found for {target!r}.")
            info = info["entries"][0]
        audio_path = Path(out_dir / f"{info['id']}.wav")
        if not audio_path.exists():
            # Fall back to whatever extension landed.
            matches = list(out_dir.glob(f"{info['id']}.*"))
            if not matches:
                raise AcquireError("Download produced no audio file.")
            audio_path = matches[0]
    return Acquired(audio_path, info.get("title", target), kind)
