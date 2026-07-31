"""Normalize YouTube video references (URLs or bare IDs) to video IDs."""
from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import parse_qs, urlparse

_VIDEO_ID_RE = re.compile(r"^[0-9A-Za-z_-]{11}$")
_YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com"}
_PATH_PREFIXES = ("/shorts/", "/live/")


def extract_video_id(ref: str) -> str | None:
    """Return the 11-character video ID for any accepted reference form, else None."""
    ref = ref.strip()
    if not ref:
        return None
    if _VIDEO_ID_RE.match(ref):
        return ref
    if "://" not in ref:
        ref = "https://" + ref
    parsed = urlparse(ref)
    host = parsed.netloc.lower()
    candidate = None
    if host == "youtu.be":
        candidate = parsed.path.lstrip("/").split("/")[0]
    elif host in _YOUTUBE_HOSTS:
        if parsed.path == "/watch":
            candidate = parse_qs(parsed.query).get("v", [None])[0]
        else:
            for prefix in _PATH_PREFIXES:
                if parsed.path.startswith(prefix):
                    candidate = parsed.path[len(prefix):].split("/")[0]
                    break
    if candidate and _VIDEO_ID_RE.match(candidate):
        return candidate
    return None


def read_url_file(path: str | Path) -> list[str]:
    """Return video references from a list file, skipping blanks and # comments."""
    refs = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            refs.append(line)
    return refs
