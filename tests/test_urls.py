"""Tests for URL/ID normalization and list-file parsing."""
import pytest

from yt_transcribe.urls import extract_video_id, read_url_file

VID = "dQw4w9WgXcQ"


@pytest.mark.parametrize("ref", [
    f"https://www.youtube.com/watch?v={VID}",
    f"https://youtube.com/watch?v={VID}",
    f"http://m.youtube.com/watch?v={VID}",
    f"www.youtube.com/watch?v={VID}",
    f"https://www.youtube.com/watch?v={VID}&t=42s&list=PL123",
    f"https://youtu.be/{VID}",
    f"https://youtu.be/{VID}?t=30",
    f"youtu.be/{VID}",
    f"https://www.youtube.com/shorts/{VID}",
    f"https://www.youtube.com/live/{VID}",
    VID,
    f"  {VID}  ",
])
def test_valid_references(ref):
    assert extract_video_id(ref) == VID


@pytest.mark.parametrize("ref", [
    "",
    "   ",
    "not a url",
    "https://vimeo.com/12345",
    "https://www.youtube.com/watch",
    "https://www.youtube.com/watch?v=tooshort",
    "https://www.youtube.com/playlist?list=PL123",
    "https://www.youtube.com/channel/UCabc",
    "abcdefghij",      # 10 chars — too short for an ID
    "abcdefghijkl",    # 12 chars — too long
    "abcde!ghijk",     # 11 chars but invalid character
])
def test_invalid_references(ref):
    assert extract_video_id(ref) is None


def test_read_url_file(tmp_path):
    listfile = tmp_path / "videos.txt"
    listfile.write_text(
        "# my videos\n"
        f"https://youtu.be/{VID}\n"
        "\n"
        f"  {VID}  \n"
        "# trailing comment\n",
        encoding="utf-8",
    )
    assert read_url_file(listfile) == [f"https://youtu.be/{VID}", VID]


def test_read_url_file_missing(tmp_path):
    with pytest.raises(OSError):
        read_url_file(tmp_path / "missing.txt")
