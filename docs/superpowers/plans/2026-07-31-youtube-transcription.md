# YouTube Transcript Downloader Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement `yt-transcribe`, a CLI that downloads YouTube caption transcripts as plain-text files — one `.txt` per video, batch-safe, no API key.

**Architecture:** Five flat modules in `yt_transcribe/`; `cli.py` is the only module that imports the others. Per-video pipeline: `urls.extract_video_id` → skip-check via `writer.find_existing` → `fetcher.fetch_transcript` → `formatter.format_transcript` → `writer.fetch_title`/`build_filename`/`write_transcript`. Every video is isolated in try/except; failures are recorded and the batch continues.

**Tech Stack:** Python 3.11+, `uv` + hatchling, `youtube-transcript-api` (locked 1.2.4), `requests` (oEmbed title lookup), `pytest`.

**Spec:** `docs/superpowers/specs/2026-07-31-youtube-transcription-design.md`

## Global Constraints

- `requires-python = ">=3.11"`; dependencies exactly `youtube-transcript-api>=1.0`, `requests>=2.31`; dev group `pytest>=8.0` (already in `pyproject.toml` — do not add more).
- Console script: `yt-transcribe = "yt_transcribe.cli:main"` (already wired).
- `cli.py` is the only module that imports the other project modules.
- Exit codes: `0` all succeeded (skips count as success), `1` any video failed, `2` usage error (no input given, list file missing/unreadable).
- No live network in tests: `fetcher` takes an injectable `api` object, `writer` tests monkeypatch `requests.get`, `cli` tests monkeypatch `fetcher.fetch_transcript` and `writer.fetch_title`.
- Non-goals (do NOT implement): Whisper fallback, parallel downloads, timestamps, playlist/channel expansion, GUI.
- Run tests with `uv run pytest`; run one file with `uv run pytest tests/test_urls.py -v`.

## Verified library facts (youtube-transcript-api 1.2.4)

The v1.x API is instance-based. These were verified against the locked version — rely on them:

- `YouTubeTranscriptApi().list(video_id) -> TranscriptList`
- `TranscriptList.find_transcript(language_codes)` is language-major with manual-preferred: for `['ru','en']` it tries ru-manual, ru-generated, en-manual, en-generated; raises `NoTranscriptFound` if none match. This exactly implements the spec's selection rule for requested languages.
- Iterating a `TranscriptList` yields manually-created transcripts first, then generated ones.
- `TranscriptList(video_id, manually_created_transcripts: dict[str, Transcript], generated_transcripts: dict[str, Transcript], translation_languages: list)` is directly constructible — tests build real `TranscriptList`s around fake transcript objects, so selection semantics are the library's own, not reimplemented.
- `Transcript` objects expose `.language_code`, `.is_generated`, `.fetch() -> FetchedTranscript`; a `FetchedTranscript` is iterable, yielding snippets with `.text`.
- Exceptions (all importable from `youtube_transcript_api`, all constructible as `Exc(video_id)`): `TranscriptsDisabled`, `VideoUnavailable`, `NoTranscriptFound` (3-arg), and base `CouldNotRetrieveTranscript`. `TranscriptsDisabled`/`VideoUnavailable`/`NoTranscriptFound` are subclasses of `CouldNotRetrieveTranscript` — except-clause order matters.

## Design decisions locked in

- **Summary has three buckets** — `N saved, M skipped, K failed` — because "skipped (already downloaded)" must not trigger exit code 1 while real failures must. The spec's "N saved, M skipped (reasons)" is covered: failure reasons are listed under the summary line.
- **`--lang` default is `en`**; the spec's "+ video's original language" falls out of the fetcher's fallback: when no requested language exists, it takes the first available transcript (manual first), which is the video's original-language track.
- **Skip-check runs before the transcript fetch** (cheap re-runs): `writer.find_existing` globs `*<video_id>.txt`, so it matches both `<title>_<id>.txt` and the degraded `<id>.txt` regardless of what a previous run named the file.
- **Paragraph budget is 600 characters**, split only at sentence boundaries; unpunctuated auto-captions stay one paragraph (accepted; no mid-sentence splits).

## File structure

| File | Responsibility |
|------|---------------|
| `yt_transcribe/urls.py` | Normalize URL/ID reference forms to video IDs; parse list files |
| `yt_transcribe/formatter.py` | Caption fragments → clean paragraphs |
| `yt_transcribe/fetcher.py` | Transcript selection/fetch; translate library errors to `TranscriptError` |
| `yt_transcribe/writer.py` | oEmbed title, filename sanitization, existing-file detection, file writing |
| `yt_transcribe/cli.py` | argparse, per-video loop, progress lines, summary, exit code |
| `tests/test_<module>.py` | One test file per module (`tests/__init__.py` exists) |

Tasks 1–4 are independent of each other; Task 5 consumes all of them; Task 6 is docs. Execute in order for a clean commit history.

---

### Task 1: urls.py — reference normalization and list files

**Files:**
- Create: `yt_transcribe/urls.py` (currently an empty stub)
- Test: `tests/test_urls.py`

**Interfaces:**
- Consumes: nothing (stdlib only: `re`, `pathlib`, `urllib.parse`)
- Produces:
  - `extract_video_id(ref: str) -> str | None` — video ID for any accepted form, `None` for anything invalid
  - `read_url_file(path: str | Path) -> list[str]` — stripped non-blank, non-`#` lines; raises `OSError` (e.g. `FileNotFoundError`) if unreadable

- [ ] **Step 1: Write the failing tests**

Create `tests/test_urls.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_urls.py -v`
Expected: FAIL — `ImportError: cannot import name 'extract_video_id'`

- [ ] **Step 3: Implement**

Replace the empty `yt_transcribe/urls.py` with:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_urls.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add yt_transcribe/urls.py tests/test_urls.py
git commit -m "feat: add URL/ID normalization and list-file parsing"
```

---

### Task 2: formatter.py — fragments to paragraphs

**Files:**
- Create: `yt_transcribe/formatter.py` (currently an empty stub)
- Test: `tests/test_formatter.py`

**Interfaces:**
- Consumes: nothing (stdlib only: `re`)
- Produces: `format_transcript(fragments: Iterable[str]) -> str` — cleaned text in paragraphs separated by blank lines, ending with a single `\n`; `""` when nothing survives cleaning

- [ ] **Step 1: Write the failing tests**

Create `tests/test_formatter.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_formatter.py -v`
Expected: FAIL — `ImportError: cannot import name 'format_transcript'`

- [ ] **Step 3: Implement**

Replace the empty `yt_transcribe/formatter.py` with:

```python
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
```

A sentence longer than the budget becomes its own paragraph — never split mid-sentence.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_formatter.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add yt_transcribe/formatter.py tests/test_formatter.py
git commit -m "feat: add transcript formatter"
```

---

### Task 3: fetcher.py — transcript selection and error translation

**Files:**
- Create: `yt_transcribe/fetcher.py` (currently an empty stub)
- Test: `tests/test_fetcher.py`

**Interfaces:**
- Consumes: `youtube_transcript_api` (see "Verified library facts" above)
- Produces:
  - `class TranscriptError(Exception)` — `str(exc)` is the human-readable failure reason
  - `fetch_transcript(video_id: str, languages: Sequence[str] = ("en",), api: YouTubeTranscriptApi | None = None) -> list[str]` — caption fragment texts; raises `TranscriptError` on any transcript failure. `api` exists for test injection; production callers omit it.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_fetcher.py`. Note: real `TranscriptList` around fake transcripts, so selection semantics are the library's own.

```python
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
        return [SimpleNamespace(text=t) for t in self._texts]


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
    assert fetch_transcript(VID, ("en",), api=api) == ["manual en"]


def test_respects_language_priority_order():
    api = FakeApi(make_list(manual=[
        FakeTranscript("en", False, ["manual en"]),
        FakeTranscript("ru", False, ["manual ru"]),
    ]))
    assert fetch_transcript(VID, ("ru", "en"), api=api) == ["manual ru"]


def test_generated_in_priority_language_beats_manual_in_later():
    api = FakeApi(make_list(
        manual=[FakeTranscript("en", False, ["manual en"])],
        generated=[FakeTranscript("ru", True, ["auto ru"])],
    ))
    assert fetch_transcript(VID, ("ru", "en"), api=api) == ["auto ru"]


def test_falls_back_to_any_available_language():
    api = FakeApi(make_list(generated=[FakeTranscript("fr", True, ["auto fr"])]))
    assert fetch_transcript(VID, ("en",), api=api) == ["auto fr"]


def test_fallback_prefers_manual_transcripts():
    api = FakeApi(make_list(
        manual=[FakeTranscript("fr", False, ["manual fr"])],
        generated=[FakeTranscript("de", True, ["auto de"])],
    ))
    assert fetch_transcript(VID, ("en",), api=api) == ["manual fr"]


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_fetcher.py -v`
Expected: FAIL — `ImportError: cannot import name 'TranscriptError'`

- [ ] **Step 3: Implement**

Replace the empty `yt_transcribe/fetcher.py` with:

```python
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
) -> list[str]:
    """Return caption fragment texts for the best transcript.

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
    return [snippet.text for snippet in fetched]
```

Except-clause order in the first block is significant: `TranscriptsDisabled` and `VideoUnavailable` are subclasses of `CouldNotRetrieveTranscript`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_fetcher.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add yt_transcribe/fetcher.py tests/test_fetcher.py
git commit -m "feat: add transcript fetcher with language selection"
```

---

### Task 4: writer.py — titles, filenames, files

**Files:**
- Create: `yt_transcribe/writer.py` (currently an empty stub)
- Test: `tests/test_writer.py`

**Interfaces:**
- Consumes: `requests` (oEmbed lookup only)
- Produces:
  - `fetch_title(video_id: str) -> str | None` — oEmbed title; `None` on ANY failure (never raises)
  - `sanitize_title(title: str) -> str` — filesystem-safe, ≤ 80 chars, may be `""`
  - `build_filename(title: str | None, video_id: str) -> str` — `<safe-title>_<id>.txt`, or `<id>.txt` when title is `None`/sanitizes to empty
  - `find_existing(video_id: str, output_dir: Path) -> Path | None` — existing output file for this video, however a previous run named it
  - `write_transcript(path: Path, text: str) -> None` — creates parent dirs, writes UTF-8

- [ ] **Step 1: Write the failing tests**

Create `tests/test_writer.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_writer.py -v`
Expected: FAIL — `ImportError: cannot import name 'build_filename'`

- [ ] **Step 3: Implement**

Replace the empty `yt_transcribe/writer.py` with:

```python
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
```

(`ch.isalnum()` is False for emoji but True for non-Latin letters, so Cyrillic/CJK titles survive while emoji become spaces. The glob `*<id>.txt` matches both `<title>_<id>.txt` and bare `<id>.txt` because `*` matches the empty string.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_writer.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add yt_transcribe/writer.py tests/test_writer.py
git commit -m "feat: add title lookup and transcript writer"
```

---

### Task 5: cli.py — orchestration, summary, exit codes

**Files:**
- Modify: `yt_transcribe/cli.py` (replace the `NotImplementedError` stub entirely)
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes (exact signatures from Tasks 1–4):
  - `urls.extract_video_id(ref: str) -> str | None`, `urls.read_url_file(path) -> list[str]` (raises `OSError`)
  - `formatter.format_transcript(fragments: Iterable[str]) -> str`
  - `fetcher.TranscriptError`, `fetcher.fetch_transcript(video_id, languages) -> list[str]`
  - `writer.fetch_title`, `writer.build_filename`, `writer.find_existing`, `writer.write_transcript`
- Produces: `main(argv: list[str] | None = None) -> int` (console-script entry point, already wired in `pyproject.toml`)

**Testability requirement:** `cli.py` must import the modules (`from yt_transcribe import fetcher, formatter, urls, writer`) and call `fetcher.fetch_transcript(...)` etc. through the module attribute — never `from yt_transcribe.fetcher import fetch_transcript` — so tests can monkeypatch the module attributes.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_cli.py`:

```python
"""End-to-end CLI tests with all network access mocked."""
import pytest

from yt_transcribe import cli, fetcher, writer
from yt_transcribe.fetcher import TranscriptError

GOOD_ID = "aaaaaaaaaaa"
BAD_ID = "bbbbbbbbbbb"


@pytest.fixture
def fake_network(monkeypatch):
    calls = {"languages": None}

    def fake_fetch(video_id, languages=("en",), api=None):
        calls["languages"] = list(languages)
        if video_id == BAD_ID:
            raise TranscriptError("captions disabled")
        return ["Hello world.", "More text here."]

    monkeypatch.setattr(fetcher, "fetch_transcript", fake_fetch)
    monkeypatch.setattr(writer, "fetch_title", lambda video_id: f"Video {video_id}")
    return calls


def test_single_video_saved(tmp_path, capsys, fake_network):
    out = tmp_path / "out"
    exit_code = cli.main([GOOD_ID, "-o", str(out)])
    assert exit_code == 0
    files = list(out.glob("*.txt"))
    assert len(files) == 1
    assert files[0].name == f"Video {GOOD_ID}_{GOOD_ID}.txt"
    assert files[0].read_text(encoding="utf-8") == "Hello world. More text here.\n"
    assert "1 saved, 0 skipped, 0 failed" in capsys.readouterr().out


def test_mixed_batch_isolates_failures(tmp_path, capsys, fake_network):
    out = tmp_path / "out"
    exit_code = cli.main([GOOD_ID, "@@invalid@@", BAD_ID, "-o", str(out)])
    assert exit_code == 1
    assert len(list(out.glob("*.txt"))) == 1
    output = capsys.readouterr().out
    assert "1 saved, 0 skipped, 2 failed" in output
    assert "invalid URL or video ID" in output
    assert "captions disabled" in output


def test_no_input_is_usage_error():
    with pytest.raises(SystemExit) as excinfo:
        cli.main([])
    assert excinfo.value.code == 2


def test_missing_list_file_is_usage_error(tmp_path):
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["-f", str(tmp_path / "nope.txt")])
    assert excinfo.value.code == 2


def test_list_file_and_positional_combined(tmp_path, fake_network):
    listfile = tmp_path / "videos.txt"
    listfile.write_text(f"# comment\n\n{GOOD_ID}\n", encoding="utf-8")
    out = tmp_path / "out"
    exit_code = cli.main(["ccccccccccc", "-f", str(listfile), "-o", str(out)])
    assert exit_code == 0
    assert len(list(out.glob("*.txt"))) == 2


def test_rerun_skips_existing_and_force_overwrites(tmp_path, capsys, fake_network, monkeypatch):
    out = tmp_path / "out"
    assert cli.main([GOOD_ID, "-o", str(out)]) == 0
    saved = next(out.glob("*.txt"))

    def changed_fetch(video_id, languages=("en",), api=None):
        return ["Changed text."]
    monkeypatch.setattr(fetcher, "fetch_transcript", changed_fetch)

    # second run: file exists -> skipped, content untouched, still exit 0
    assert cli.main([GOOD_ID, "-o", str(out)]) == 0
    assert "1 skipped" in capsys.readouterr().out
    assert saved.read_text(encoding="utf-8") == "Hello world. More text here.\n"

    # --force overwrites
    assert cli.main([GOOD_ID, "-o", str(out), "--force"]) == 0
    assert saved.read_text(encoding="utf-8") == "Changed text.\n"


def test_lang_flag_passes_priority_list(tmp_path, fake_network):
    cli.main([GOOD_ID, "-o", str(tmp_path / "out"), "--lang", "ru,en"])
    assert fake_network["languages"] == ["ru", "en"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_cli.py -v`
Expected: FAIL — `NotImplementedError` (the stub) on every test

- [ ] **Step 3: Implement**

Replace `yt_transcribe/cli.py` entirely with:

```python
"""Command-line entry point: argument parsing, orchestration loop, summary report."""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

from yt_transcribe import fetcher, formatter, urls, writer

_USAGE_ERROR = 2


@dataclass
class VideoResult:
    ref: str
    status: str  # "saved" | "skipped" | "failed"
    detail: str  # output path for saved/skipped, reason for failed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="yt-transcribe",
        description="Download YouTube video transcripts (captions) as plain-text files.",
    )
    parser.add_argument("urls", nargs="*", metavar="URL",
                        help="video URLs or 11-character video IDs")
    parser.add_argument("-f", "--file", metavar="PATH",
                        help="file with one URL per line (# comments and blank lines ignored)")
    parser.add_argument("-o", "--output", metavar="DIR", default="transcripts",
                        help="output folder, created if missing (default: ./transcripts/)")
    parser.add_argument("--lang", metavar="CODES", default="en",
                        help="comma-separated caption-language priority list (default: en)")
    parser.add_argument("--force", action="store_true",
                        help="overwrite existing output files (default: skip them)")
    return parser


def process_video(ref: str, languages: list[str], output_dir: Path, force: bool) -> VideoResult:
    video_id = urls.extract_video_id(ref)
    if video_id is None:
        return VideoResult(ref, "failed", "invalid URL or video ID")
    try:
        existing = writer.find_existing(video_id, output_dir)
        if existing is not None and not force:
            return VideoResult(ref, "skipped", str(existing))
        fragments = fetcher.fetch_transcript(video_id, languages)
        text = formatter.format_transcript(fragments)
        title = writer.fetch_title(video_id)
        path = output_dir / writer.build_filename(title, video_id)
        writer.write_transcript(path, text)
        return VideoResult(ref, "saved", str(path))
    except fetcher.TranscriptError as exc:
        return VideoResult(ref, "failed", str(exc))
    except Exception as exc:  # per-video isolation: one failure never aborts the batch
        return VideoResult(ref, "failed", f"unexpected error: {exc}")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    refs = list(args.urls)
    if args.file:
        try:
            refs.extend(urls.read_url_file(args.file))
        except OSError as exc:
            parser.exit(_USAGE_ERROR, f"error: cannot read list file: {exc}\n")
    if not refs:
        parser.exit(_USAGE_ERROR, "error: no video URLs given (pass URLs or --file)\n")

    languages = [code.strip() for code in args.lang.split(",") if code.strip()] or ["en"]
    output_dir = Path(args.output)

    results = []
    for index, ref in enumerate(refs, start=1):
        result = process_video(ref, languages, output_dir, args.force)
        results.append(result)
        print(f"[{index}/{len(refs)}] {result.status}: {ref} — {result.detail}")

    saved = sum(1 for r in results if r.status == "saved")
    skipped = sum(1 for r in results if r.status == "skipped")
    failed = [r for r in results if r.status == "failed"]
    print(f"\n{saved} saved, {skipped} skipped, {len(failed)} failed")
    for result in failed:
        print(f"  {result.ref}: {result.detail}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_cli.py -v`
Expected: all PASS

- [ ] **Step 5: Run the whole suite and smoke-test the console script**

Run: `uv run pytest`
Expected: all tests from all five files PASS

Run: `uv run yt-transcribe --help`
Expected: usage text listing URL, -f/--file, -o/--output, --lang, --force; exit 0

- [ ] **Step 6: Commit**

```bash
git add yt_transcribe/cli.py tests/test_cli.py
git commit -m "feat: add CLI orchestration, summary, and exit codes"
```

---

### Task 6: Documentation

**Files:**
- Modify: `README.md` (usage documentation)
- Modify: `CLAUDE.md` (Status section only)

**Interfaces:**
- Consumes: the CLI behavior from Task 5 (flags, defaults, exit codes)
- Produces: nothing consumed by other tasks

- [ ] **Step 1: Update README.md**

Replace/extend the README so it contains: a one-paragraph description (captions-based, no API key), install/run instructions (`uv sync`, `uv run yt-transcribe …`), the four usage examples from the spec's CLI Interface section, the flags table (copy from the spec: `-f/--file`, `-o/--output` default `./transcripts/`, `--lang` default `en`, `--force`), accepted reference forms (`watch?v=`, `youtu.be`, `shorts/`, `live/`, bare 11-char ID), and the exit codes (0 all ok / 1 any failed / 2 usage error). Development section: `uv run pytest`.

- [ ] **Step 2: Update CLAUDE.md status**

Replace the entire `## Status` section body with:

```markdown
Implemented and tested. All five modules are complete with per-module pytest
suites (network fully mocked). See the design spec for behavior and the plan
in `docs/superpowers/plans/2026-07-31-youtube-transcription.md` for history.
```

- [ ] **Step 3: Verify the suite still passes**

Run: `uv run pytest`
Expected: all PASS

- [ ] **Step 4: Commit**

```bash
git add README.md CLAUDE.md
git commit -m "docs: update README usage and project status"
```

---

## Self-review checklist (already applied)

- **Spec coverage:** all four flags (Task 5), all five reference forms (Task 1), list-file parsing with comments/blanks (Task 1), manual-over-generated language priority + fallbacks (Task 3), paragraph formatting with artifact stripping (Task 2), oEmbed title with degrade-to-`<id>.txt` (Task 4), skip/`--force` (Tasks 4+5), per-video isolation (Task 5), summary + exit codes 0/1/2 (Task 5), no live network in tests (all).
- **Type consistency:** `fetch_transcript` returns `list[str]` consumed by `format_transcript(Iterable[str])`; `fetch_title` returns `str | None` accepted by `build_filename(title: str | None, ...)`; `main` returns `int` matching the `yt-transcribe = yt_transcribe.cli:main` + `SystemExit(main())` wiring.
- **Library API:** verified against installed youtube-transcript-api 1.2.4 (see "Verified library facts").
