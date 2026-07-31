"""Tests for caption-fragment formatting."""
from yt_transcribe.formatter import format_transcript


def test_joins_fragments_into_stamped_paragraph():
    assert format_transcript(
        [(0.0, "Hello there."), (2.5, "How are you?")]
    ) == "[0:00] Hello there. How are you?\n"


def test_first_stamp_uses_first_fragment_start():
    assert format_transcript([(7.2, "Hello.")]) == "[0:07] Hello.\n"


def test_timestamp_formats():
    assert format_transcript([(59.9, "A.")]) == "[0:59] A.\n"
    assert format_transcript([(600.0, "B.")]) == "[10:00] B.\n"
    assert format_transcript([(3599.0, "C.")]) == "[59:59] C.\n"
    assert format_transcript([(3754.2, "D.")]) == "[1:02:34] D.\n"


def test_artifact_only_fragment_contributes_no_timestamp():
    # [Music] at 0.0 is dropped entirely; the stamp comes from the first
    # fragment that survives cleaning.
    assert format_transcript(
        [(0.0, "[Music]"), (61.0, "hello"), (62.0, "[Applause] world")]
    ) == "[1:01] hello world\n"


def test_strips_music_notes():
    assert format_transcript(
        [(0.0, "♪ la la ♪"), (1.0, "next line")]
    ) == "[0:00] la la next line\n"


def test_collapses_internal_whitespace():
    assert format_transcript(
        [(0.0, "line one\nline two"), (1.0, "  spaced   out  ")]
    ) == "[0:00] line one line two spaced out\n"


def test_empty_input_returns_empty_string():
    assert format_transcript([]) == ""
    assert format_transcript([(0.0, "[Music]"), (1.0, "  ")]) == ""


def test_long_text_splits_into_paragraphs_with_advancing_stamps():
    # 50 one-sentence fragments, 4 seconds apart.
    fragments = [(float(i * 4), f"This is sentence number {i}.") for i in range(50)]
    result = format_transcript(fragments)
    assert result.endswith("\n")
    paragraphs = result.strip("\n").split("\n\n")
    assert len(paragraphs) > 1

    first_sentence_index = 0
    texts = []
    for paragraph in paragraphs:
        stamp, text = paragraph.split("] ", 1)
        texts.append(text)
        assert len(text) <= 600
        assert text.endswith(".")
        # stamp = start time of the paragraph's first sentence (index * 4 s)
        minutes, secs = divmod(first_sentence_index * 4, 60)
        assert stamp == f"[{minutes}:{secs:02d}"
        first_sentence_index += text.count(".")
    # joining paragraph texts back reconstructs the input losslessly
    assert " ".join(texts) == " ".join(text for _, text in fragments)


def test_unpunctuated_text_stays_single_paragraph():
    fragments = [(0.0, "word " * 200)]
    result = format_transcript(fragments)
    assert result == "[0:00] " + ("word " * 200).strip() + "\n"
