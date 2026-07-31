"""Tests for title lookup, filename sanitization, and file writing."""
import requests

from yt_transcribe import writer
from yt_transcribe.writer import (
    build_filename,
    fetch_title,
    find_existing,
    sanitize_title,
    write_transcript,
)

VID = "dQw4w9WgXcQ"


class FakeResponse:
    def __init__(self, payload=None, status_error=None):
        self._payload = payload
        self._status_error = status_error

    def raise_for_status(self):
        if self._status_error is not None:
            raise self._status_error

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


def test_fetch_title_returns_title(monkeypatch):
    monkeypatch.setattr(writer.requests, "get",
                        lambda *a, **k: FakeResponse({"title": "My Video"}))
    assert fetch_title(VID) == "My Video"


def test_fetch_title_http_error_returns_none(monkeypatch):
    monkeypatch.setattr(writer.requests, "get",
                        lambda *a, **k: FakeResponse(status_error=requests.HTTPError("404")))
    assert fetch_title(VID) is None


def test_fetch_title_network_error_returns_none(monkeypatch):
    def boom(*a, **k):
        raise requests.ConnectionError("no network")
    monkeypatch.setattr(writer.requests, "get", boom)
    assert fetch_title(VID) is None


def test_fetch_title_bad_json_returns_none(monkeypatch):
    monkeypatch.setattr(writer.requests, "get",
                        lambda *a, **k: FakeResponse(ValueError("not json")))
    assert fetch_title(VID) is None


def test_sanitize_replaces_path_and_special_chars():
    assert sanitize_title('AC/DC: "Best" <of> \\ all?') == "AC DC Best of all"


def test_sanitize_strips_emoji():
    assert sanitize_title("Great video 🎉🚀 wow") == "Great video wow"


def test_sanitize_keeps_non_latin_letters():
    assert sanitize_title("Привет мир") == "Привет мир"


def test_sanitize_caps_length():
    assert len(sanitize_title("x" * 300)) == 80


def test_sanitize_all_junk_returns_empty():
    assert sanitize_title("///???") == ""


def test_build_filename_with_title():
    assert build_filename("My Video", VID) == f"My Video_{VID}.txt"


def test_build_filename_without_title():
    assert build_filename(None, VID) == f"{VID}.txt"


def test_build_filename_junk_title_falls_back_to_id():
    assert build_filename("🎉🎉", VID) == f"{VID}.txt"


def test_find_existing_missing_dir(tmp_path):
    assert find_existing(VID, tmp_path / "nope") is None


def test_find_existing_titled_file(tmp_path):
    (tmp_path / f"Some Title_{VID}.txt").write_text("x", encoding="utf-8")
    assert find_existing(VID, tmp_path) == tmp_path / f"Some Title_{VID}.txt"


def test_find_existing_bare_id_file(tmp_path):
    (tmp_path / f"{VID}.txt").write_text("x", encoding="utf-8")
    assert find_existing(VID, tmp_path) == tmp_path / f"{VID}.txt"


def test_find_existing_ignores_other_videos(tmp_path):
    (tmp_path / "Other_zzzzzzzzzzz.txt").write_text("x", encoding="utf-8")
    assert find_existing(VID, tmp_path) is None


def test_write_transcript_creates_dirs(tmp_path):
    path = tmp_path / "deep" / "out" / "file.txt"
    write_transcript(path, "hello\n")
    assert path.read_text(encoding="utf-8") == "hello\n"
