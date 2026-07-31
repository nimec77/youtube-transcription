"""Select and fetch the best available transcript via youtube-transcript-api."""
from __future__ import annotations

from collections.abc import Sequence

from youtube_transcript_api import (
    CouldNotRetrieveTranscript,
    NoTranscriptFound,
    TranscriptsDisabled,
    VideoUnavailable,
    YouTubeTranscriptApi,
)


class TranscriptError(Exception):
    """Transcript could not be fetched; str(exc) is the human-readable reason."""


def fetch_transcript(
    video_id: str,
    languages: Sequence[str] = ("en",),
    api: YouTubeTranscriptApi | None = None,
) -> list[tuple[float, str]]:
    """Return (start_seconds, text) caption fragments for the best transcript.

    Selection: requested languages in priority order, manual captions preferred
    over auto-generated within each language; if no requested language exists,
    fall back to whatever is available (manual first).
    """
    api = api or YouTubeTranscriptApi()
    try:
        transcript_list = api.list(video_id)
    except TranscriptsDisabled:
        raise TranscriptError("captions disabled") from None
    except VideoUnavailable:
        raise TranscriptError("video unavailable or private") from None
    except CouldNotRetrieveTranscript as exc:
        raise TranscriptError(f"could not retrieve captions ({type(exc).__name__})") from exc

    try:
        transcript = transcript_list.find_transcript(languages)
    except NoTranscriptFound:
        transcript = next(iter(transcript_list), None)
    if transcript is None:
        raise TranscriptError("no captions available")

    try:
        fetched = transcript.fetch()
    except CouldNotRetrieveTranscript as exc:
        raise TranscriptError(f"could not retrieve captions ({type(exc).__name__})") from exc
    return [(snippet.start, snippet.text) for snippet in fetched]
