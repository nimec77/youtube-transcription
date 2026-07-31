"""Tests for transcript selection and error translation (network fully faked)."""
from types import SimpleNamespace

import pytest
from youtube_transcript_api import (
    CouldNotRetrieveTranscript,
    TranscriptsDisabled,
    VideoUnavailable,
)
from youtube_transcript_api._transcripts import TranscriptList

from yt_transcribe.fetcher import TranscriptError, fetch_transcript

VID = "vid1234567x"


class FakeTranscript:
    def __init__(self, language_code, is_generated, texts):
        self.language_code = language_code
        self.is_generated = is_generated
        self._texts = texts

    def fetch(self):
        return [
            SimpleNamespace(start=float(i * 5), text=t)
            for i, t in enumerate(self._texts)
        ]


class FakeApi:
    def __init__(self, transcript_list=None, error=None):
        self._transcript_list = transcript_list
        self._error = error

    def list(self, video_id):
        if self._error is not None:
            raise self._error
        return self._transcript_list


def make_list(manual=(), generated=()):
    return TranscriptList(
        VID,
        {t.language_code: t for t in manual},
        {t.language_code: t for t in generated},
        [],
    )


def test_prefers_manual_over_generated_in_same_language():
    api = FakeApi(make_list(
        manual=[FakeTranscript("en", False, ["manual en"])],
        generated=[FakeTranscript("en", True, ["auto en"])],
    ))
    assert fetch_transcript(VID, ("en",), api=api) == [(0.0, "manual en")]


def test_respects_language_priority_order():
    api = FakeApi(make_list(manual=[
        FakeTranscript("en", False, ["manual en"]),
        FakeTranscript("ru", False, ["manual ru"]),
    ]))
    assert fetch_transcript(VID, ("ru", "en"), api=api) == [(0.0, "manual ru")]


def test_generated_in_priority_language_beats_manual_in_later():
    api = FakeApi(make_list(
        manual=[FakeTranscript("en", False, ["manual en"])],
        generated=[FakeTranscript("ru", True, ["auto ru"])],
    ))
    assert fetch_transcript(VID, ("ru", "en"), api=api) == [(0.0, "auto ru")]


def test_falls_back_to_any_available_language():
    api = FakeApi(make_list(generated=[FakeTranscript("fr", True, ["auto fr"])]))
    assert fetch_transcript(VID, ("en",), api=api) == [(0.0, "auto fr")]


def test_fallback_prefers_manual_transcripts():
    api = FakeApi(make_list(
        manual=[FakeTranscript("fr", False, ["manual fr"])],
        generated=[FakeTranscript("de", True, ["auto de"])],
    ))
    assert fetch_transcript(VID, ("en",), api=api) == [(0.0, "manual fr")]


def test_returns_start_times_with_texts():
    api = FakeApi(make_list(manual=[FakeTranscript("en", False, ["first", "second"])]))
    assert fetch_transcript(VID, ("en",), api=api) == [(0.0, "first"), (5.0, "second")]


def test_captions_disabled():
    api = FakeApi(error=TranscriptsDisabled(VID))
    with pytest.raises(TranscriptError, match="captions disabled"):
        fetch_transcript(VID, api=api)


def test_video_unavailable():
    api = FakeApi(error=VideoUnavailable(VID))
    with pytest.raises(TranscriptError, match="video unavailable or private"):
        fetch_transcript(VID, api=api)


def test_other_retrieval_error():
    api = FakeApi(error=CouldNotRetrieveTranscript(VID))
    with pytest.raises(TranscriptError, match="could not retrieve captions"):
        fetch_transcript(VID, api=api)


def test_no_transcripts_at_all():
    api = FakeApi(make_list())
    with pytest.raises(TranscriptError, match="no captions available"):
        fetch_transcript(VID, api=api)
