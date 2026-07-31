"""Join timed caption fragments into clean, timestamped paragraphs."""
from __future__ import annotations

import re
from bisect import bisect_right
from collections.abc import Iterable

_ARTIFACT_RE = re.compile(r"\[[^\]]*\]|♪")
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?…])\s+")
_PARAGRAPH_MAX_CHARS = 600


def _format_timestamp(seconds: float) -> str:
    total = int(seconds)
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def format_transcript(fragments: Iterable[tuple[float, str]]) -> str:
    """Join (start_seconds, text) fragments into '[M:SS] ...' paragraphs.

    Each paragraph is prefixed with the start time of the fragment its first
    sentence began in. Returns '' if nothing survives cleaning.
    """
    cleaned: list[tuple[float, str]] = []
    for start, fragment in fragments:
        text = _ARTIFACT_RE.sub(" ", fragment)
        text = re.sub(r"\s+", " ", text).strip()
        if text:
            cleaned.append((start, text))
    if not cleaned:
        return ""

    # Join fragment texts, remembering each fragment's char offset so a
    # sentence can be traced back to the fragment holding its first char.
    fragment_offsets: list[int] = []
    fragment_starts: list[float] = []
    parts: list[str] = []
    offset = 0
    for start, text in cleaned:
        fragment_offsets.append(offset)
        fragment_starts.append(start)
        parts.append(text)
        offset += len(text) + 1  # +1 for the joining space
    joined = " ".join(parts)

    def time_at(char_offset: int) -> float:
        return fragment_starts[bisect_right(fragment_offsets, char_offset) - 1]

    # Split into sentences, keeping each sentence's char offset in `joined`.
    sentences: list[tuple[int, str]] = []
    last = 0
    for match in _SENTENCE_SPLIT_RE.finditer(joined):
        sentences.append((last, joined[last:match.start()]))
        last = match.end()
    sentences.append((last, joined[last:]))

    paragraphs: list[str] = []
    current = ""
    current_start = 0.0
    for char_offset, sentence in sentences:
        if not current:
            current = sentence
            current_start = time_at(char_offset)
        elif len(current) + 1 + len(sentence) > _PARAGRAPH_MAX_CHARS:
            paragraphs.append(f"[{_format_timestamp(current_start)}] {current}")
            current = sentence
            current_start = time_at(char_offset)
        else:
            current = f"{current} {sentence}"
    if current:
        paragraphs.append(f"[{_format_timestamp(current_start)}] {current}")
    return "\n\n".join(paragraphs) + "\n"
