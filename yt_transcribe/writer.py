"""Video title lookup (oEmbed), filename construction, and transcript file writing."""
from __future__ import annotations

from pathlib import Path

import requests

_OEMBED_URL = "https://www.youtube.com/oembed"
_OEMBED_TIMEOUT = 10
_MAX_TITLE_LENGTH = 80
_ALLOWED_PUNCTUATION = " -_.,!'"


def fetch_title(video_id: str) -> str | None:
    """Return the video title via YouTube oEmbed, or None on any failure."""
    try:
        response = requests.get(
            _OEMBED_URL,
            params={"url": f"https://www.youtube.com/watch?v={video_id}", "format": "json"},
            timeout=_OEMBED_TIMEOUT,
        )
        response.raise_for_status()
        title = response.json().get("title")
    except (requests.RequestException, ValueError):
        return None
    return title if isinstance(title, str) and title.strip() else None


def sanitize_title(title: str) -> str:
    """Make a title filesystem-safe: drop emoji/special chars, cap the length."""
    cleaned = "".join(
        ch if ch.isalnum() or ch in _ALLOWED_PUNCTUATION else " " for ch in title
    )
    cleaned = " ".join(cleaned.split()).strip(". ")
    return cleaned[:_MAX_TITLE_LENGTH].rstrip()


def build_filename(title: str | None, video_id: str) -> str:
    safe = sanitize_title(title) if title else ""
    return f"{safe}_{video_id}.txt" if safe else f"{video_id}.txt"


def find_existing(video_id: str, output_dir: Path) -> Path | None:
    """Find this video's output file regardless of how a previous run named it."""
    if not output_dir.is_dir():
        return None
    matches = sorted(output_dir.glob(f"*{video_id}.txt"))
    return matches[0] if matches else None


def write_transcript(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
