"""Join caption fragments into clean readable paragraphs."""
from __future__ import annotations

import re
from collections.abc import Iterable

_ARTIFACT_RE = re.compile(r"\[[^\]]*\]|♪")
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?…])\s+")
_PARAGRAPH_MAX_CHARS = 600


def format_transcript(fragments: Iterable[str]) -> str:
    """Join caption fragments into paragraphs; '' if nothing survives cleaning."""
    cleaned = []
    for fragment in fragments:
        text = _ARTIFACT_RE.sub(" ", fragment)
        text = re.sub(r"\s+", " ", text).strip()
        if text:
            cleaned.append(text)
    if not cleaned:
        return ""
    sentences = _SENTENCE_SPLIT_RE.split(" ".join(cleaned))
    paragraphs: list[str] = []
    current = ""
    for sentence in sentences:
        if current and len(current) + 1 + len(sentence) > _PARAGRAPH_MAX_CHARS:
            paragraphs.append(current)
            current = sentence
        else:
            current = f"{current} {sentence}".strip()
    if current:
        paragraphs.append(current)
    return "\n\n".join(paragraphs) + "\n"
