# Transcript Paragraph Timestamps Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prefix every transcript paragraph with the video time of its first sentence (`[4:07]` / `[1:02:34]`), always on, per the approved spec `docs/superpowers/specs/2026-07-31-transcript-timestamps-design.md`.

**Architecture:** `fetcher.fetch_transcript` starts returning `(start_seconds, text)` tuples instead of bare strings; `formatter.format_transcript` accepts those tuples, tracks which fragment each sentence's first character came from, and stamps each packed paragraph. `cli.py`, `urls.py`, `writer.py` are untouched.

**Tech Stack:** Python 3.11+, `uv`, `pytest`, `youtube-transcript-api` (already a dependency — its snippets already carry `.start`).

## Global Constraints

- Package management is `uv`; run everything as `uv run pytest ...` / `uv run yt-transcribe ...`.
- No new dependencies.
- `cli.py` stays the only module that imports the other `yt_transcribe` modules; timing travels as plain tuples (no shared types module).
- All tests mock the network — no live YouTube calls in the suite.
- Timestamps are always on; no new CLI flags.
- Timestamp format: `M:SS` (minutes unpadded, seconds zero-padded); `H:MM:SS` from one hour; fractional seconds truncated (`71.9` → `[1:11]`); stamp inline: `[4:07] Text...`.
- Task order matters: Task 1 (formatter) then Task 2 (fetcher). The test suite is green after each commit, but the live CLI pipeline is only consistent again after Task 2 — don't stop between them.

---

### Task 1: Formatter accepts timed fragments and stamps paragraphs

**Files:**
- Modify: `yt_transcribe/formatter.py`
- Test: `tests/test_formatter.py` (rewrite fixtures to tuples, add timestamp tests)
- Test: `tests/test_cli.py` (its fake fetcher must return tuples or the suite goes red)

**Interfaces:**
- Consumes: nothing from other tasks.
- Produces: `format_transcript(fragments: Iterable[tuple[float, str]]) -> str` — each tuple is `(start_seconds, fragment_text)`; returns stamped paragraphs joined by blank lines with trailing `\n`, or `""` if nothing survives cleaning. Task 2's fetcher return type must match this input.

- [ ] **Step 1: Rewrite the formatter tests for timed input**

Replace the entire contents of `tests/test_formatter.py` with:

```python
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
```

- [ ] **Step 2: Run the formatter tests to verify they fail**

Run: `uv run pytest tests/test_formatter.py -v`
Expected: FAIL — every test errors (the current `format_transcript` treats each tuple as a string; typical failure is a `TypeError`/wrong output, not an import error).

- [ ] **Step 3: Implement the timed formatter**

Replace the entire contents of `yt_transcribe/formatter.py` with:

```python
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
```

- [ ] **Step 4: Run the formatter tests to verify they pass**

Run: `uv run pytest tests/test_formatter.py -v`
Expected: PASS (all tests).

- [ ] **Step 5: Update the CLI test mocks to the tuple shape**

Run: `uv run pytest` — expected: `tests/test_cli.py` fails now, because its fake fetcher still returns bare strings. In `tests/test_cli.py` make these three edits:

In `fake_network`, replace the `fake_fetch` return value:

```python
    def fake_fetch(video_id, languages=("en",), api=None):
        calls["languages"] = list(languages)
        if video_id == BAD_ID:
            raise TranscriptError("captions disabled")
        return [(0.0, "Hello world."), (2.0, "More text here.")]
```

In `test_single_video_saved`, update the content assertion:

```python
    assert files[0].read_text(encoding="utf-8") == "[0:00] Hello world. More text here.\n"
```

In `test_rerun_skips_existing_and_force_overwrites`, update `changed_fetch` and both content assertions:

```python
    def changed_fetch(video_id, languages=("en",), api=None):
        return [(0.0, "Changed text.")]
```

```python
    assert saved.read_text(encoding="utf-8") == "[0:00] Hello world. More text here.\n"
```

```python
    assert saved.read_text(encoding="utf-8") == "[0:00] Changed text.\n"
```

- [ ] **Step 6: Run the full suite to verify green**

Run: `uv run pytest`
Expected: PASS — all tests in all files (fetcher tests still pass; they don't touch the formatter).

- [ ] **Step 7: Commit**

```bash
git add yt_transcribe/formatter.py tests/test_formatter.py tests/test_cli.py
git commit -m "feat: formatter stamps paragraphs with [M:SS] video timestamps"
```

---

### Task 2: Fetcher returns (start, text) tuples

**Files:**
- Modify: `yt_transcribe/fetcher.py:19-51` (signature, docstring, return statement)
- Test: `tests/test_fetcher.py`

**Interfaces:**
- Consumes: nothing — but its return type must match Task 1's `format_transcript` input: `list[tuple[float, str]]`.
- Produces: `fetch_transcript(video_id, languages=("en",), api=None) -> list[tuple[float, str]]` — `(snippet.start, snippet.text)` per caption snippet. Selection logic and `TranscriptError` behavior unchanged.

- [ ] **Step 1: Update the fetcher tests for timed output**

In `tests/test_fetcher.py`, replace `FakeTranscript.fetch` so fake snippets carry starts (5 s apart):

```python
    def fetch(self):
        return [
            SimpleNamespace(start=float(i * 5), text=t)
            for i, t in enumerate(self._texts)
        ]
```

Update the five selection-test assertions to the tuple shape:

```python
    assert fetch_transcript(VID, ("en",), api=api) == [(0.0, "manual en")]
```

```python
    assert fetch_transcript(VID, ("ru", "en"), api=api) == [(0.0, "manual ru")]
```

```python
    assert fetch_transcript(VID, ("ru", "en"), api=api) == [(0.0, "auto ru")]
```

```python
    assert fetch_transcript(VID, ("en",), api=api) == [(0.0, "auto fr")]
```

```python
    assert fetch_transcript(VID, ("en",), api=api) == [(0.0, "manual fr")]
```

Add a test that multiple snippets keep their own start times:

```python
def test_returns_start_times_with_texts():
    api = FakeApi(make_list(manual=[FakeTranscript("en", False, ["first", "second"])]))
    assert fetch_transcript(VID, ("en",), api=api) == [(0.0, "first"), (5.0, "second")]
```

The four error tests (`test_captions_disabled` etc.) need no changes.

- [ ] **Step 2: Run the fetcher tests to verify the updated ones fail**

Run: `uv run pytest tests/test_fetcher.py -v`
Expected: FAIL — the six assertions above (fetcher still returns bare strings); error tests still pass.

- [ ] **Step 3: Implement the fetcher change**

In `yt_transcribe/fetcher.py`, change the signature line, the docstring's first line, and the return statement:

```python
def fetch_transcript(
    video_id: str,
    languages: Sequence[str] = ("en",),
    api: YouTubeTranscriptApi | None = None,
) -> list[tuple[float, str]]:
    """Return (start_seconds, text) caption fragments for the best transcript.
```

```python
    return [(snippet.start, snippet.text) for snippet in fetched]
```

Everything else in the function body stays exactly as it is.

- [ ] **Step 4: Run the full suite to verify green**

Run: `uv run pytest`
Expected: PASS — all tests. The live pipeline (fetcher → formatter) is now type-consistent again.

- [ ] **Step 5: Commit**

```bash
git add yt_transcribe/fetcher.py tests/test_fetcher.py
git commit -m "feat: fetcher returns (start, text) tuples with snippet timing"
```

---

### Task 3: Docs update and live verification

**Files:**
- Modify: `CLAUDE.md` (Architecture section, `fetcher.py` and `formatter.py` lines)
- Regenerate: `transcripts/AI Agents Security Week 2026 Лекция 4. Enterprise AI agent security_h_XfNaUKPQ8.txt`

**Interfaces:**
- Consumes: the complete feature from Tasks 1–2.
- Produces: nothing for later tasks (final task).

- [ ] **Step 1: Update CLAUDE.md module descriptions**

In `CLAUDE.md`, replace the `fetcher.py` and `formatter.py` bullet lines with:

```markdown
- `fetcher.py` — transcript selection/fetch via `youtube-transcript-api`:
  requested languages in priority order, human-made captions preferred over
  auto-generated, then any available; returns `(start_seconds, text)` tuples
- `formatter.py` — join caption fragments into clean readable paragraphs,
  each prefixed with a `[M:SS]` / `[H:MM:SS]` video timestamp
```

Also update the CLAUDE.md "Project" paragraph's output description from "output: one plain-text file per video" to "output: one plain-text file per video with `[M:SS]`-stamped paragraphs".

- [ ] **Step 2: Check README for output examples**

Run: `grep -n -i "paragraph\|output\|transcript" README.md | head -20`
If the README shows sample output content, update it to show a `[0:00]`-stamped paragraph; if it only describes flags/usage, leave it.

- [ ] **Step 3: Regenerate the user's transcript (live network, out of test suite)**

Run:

```bash
uv run yt-transcribe --force --lang ru h_XfNaUKPQ8
```

Expected: `[1/1] saved: h_XfNaUKPQ8 — transcripts/AI Agents Security Week 2026 Лекция 4. Enterprise AI agent security_h_XfNaUKPQ8.txt` and `1 saved, 0 skipped, 0 failed`.

- [ ] **Step 4: Verify the regenerated file is timestamped**

Run: `head -c 400 "transcripts/AI Agents Security Week 2026 Лекция 4. Enterprise AI agent security_h_XfNaUKPQ8.txt"`
Expected: the file starts with a `[0:00]`-style stamp, and paragraphs (`grep -c '^\[' <file>`) all start with stamps.

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md README.md
git commit -m "docs: describe timestamped transcript output"
```

(Only add `README.md` if Step 2 changed it. The regenerated transcript stays uncommitted — `transcripts/` is user output, not source.)
