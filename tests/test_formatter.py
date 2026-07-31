"""Tests for caption-fragment formatting."""
from yt_transcribe.formatter import format_transcript


def test_joins_fragments_into_paragraph():
    assert format_transcript(["Hello there.", "How are you?"]) == "Hello there. How are you?\n"


def test_strips_caption_artifacts():
    assert format_transcript(["[Music]", "hello", "[Applause] world"]) == "hello world\n"


def test_strips_music_notes():
    assert format_transcript(["♪ la la ♪", "next line"]) == "la la next line\n"


def test_collapses_internal_whitespace():
    assert format_transcript(["line one\nline two", "  spaced   out  "]) == "line one line two spaced out\n"


def test_empty_input_returns_empty_string():
    assert format_transcript([]) == ""
    assert format_transcript(["[Music]", "  "]) == ""


def test_long_text_splits_into_paragraphs_at_sentence_boundaries():
    fragments = [f"This is sentence number {i}." for i in range(50)]
    result = format_transcript(fragments)
    assert result.endswith("\n")
    paragraphs = result.strip("\n").split("\n\n")
    assert len(paragraphs) > 1
    assert all(len(p) <= 600 for p in paragraphs)
    assert all(p.endswith(".") for p in paragraphs)
    # joining paragraphs back with spaces reconstructs the input losslessly
    assert " ".join(paragraphs) == " ".join(fragments)


def test_unpunctuated_text_stays_single_paragraph():
    fragments = ["word " * 200]
    result = format_transcript(fragments)
    assert result == ("word " * 200).strip() + "\n"
