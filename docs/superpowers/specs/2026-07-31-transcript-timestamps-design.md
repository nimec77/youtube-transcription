# Transcript Paragraph Timestamps — Design

**Date:** 2026-07-31
**Status:** Approved
**Supersedes:** the "Timestamped output" non-goal in
`2026-07-31-youtube-transcription-design.md` — the user now needs timestamps to
navigate long transcripts.

## Overview

Prefix every paragraph in the output `.txt` with the video time at which that
paragraph's first sentence starts:

```
[0:00] Welcome back to the channel. Today we are looking at...

[1:12] So the first thing you will notice is...

[1:02:34] Wrapping up, the three takeaways are...
```

Timestamps are always on — no new CLI flags. Paragraph formation is unchanged
(~600 characters, split at sentence boundaries), so output is identical to the
current format except for the prefixes.

## Timestamp format

- `M:SS` — minutes unpadded, seconds zero-padded (`[0:00]`, `[4:07]`, `[59:59]`).
- From one hour on: `H:MM:SS` — hours unpadded, minutes and seconds zero-padded
  (`[1:02:34]`). This matches how YouTube displays times, and YouTube's player
  accepts both forms for seeking.
- `start` values from the API are floats; fractional seconds are truncated
  (`71.9` → `[1:11]`).
- The stamp is inline at the start of the paragraph: `[4:07] Text...`.
- The first paragraph's stamp is the start time of the first real caption —
  usually `[0:00]`, but not forced to be.

## Module changes

`cli.py` remains the only module that imports the others. Timing data travels
as plain tuples, so no shared types module is needed.

- **`fetcher.py`** — `fetch_transcript` returns `list[tuple[float, str]]`
  (start-seconds, fragment text) instead of `list[str]`, keeping the `start`
  field `youtube-transcript-api` already provides on each snippet. Transcript
  selection and error handling are untouched.
- **`formatter.py`** — `format_transcript` accepts an iterable of
  `(start, text)` pairs. Internally: clean each fragment exactly as today; track
  which fragment each sentence's first character originated from; pack sentences
  into paragraphs exactly as today; prefix each paragraph with the start time of
  the fragment its first sentence began in, via a `_format_timestamp(seconds)`
  helper.
- **`cli.py`** — no code change; it already pipes `fetch_transcript` output
  straight into `format_transcript`.
- **`urls.py`, `writer.py`** — untouched.
- **`CLAUDE.md`** — update the `fetcher.py`/`formatter.py` module descriptions
  when the code changes.

## Edge cases

- Fragments that clean to nothing (artifact-only, e.g. `[Music]`) are dropped as
  today and contribute no timestamp.
- Empty transcript (nothing survives cleaning) still returns `""` — the writer
  and CLI behavior for that case is unchanged.
- A sentence that starts mid-fragment is stamped with that fragment's start
  time; the goal is a navigation anchor, not subtitle-grade precision.
- Existing output files are still skipped by default; `--force` regenerates
  them with timestamps.

## Testing

All network access stays mocked; per-module suites as before.

- `test_formatter.py` — rewrite fixtures to `(start, text)` pairs: one stamp per
  paragraph, stamp equals first sentence's fragment start, `M:SS` vs `H:MM:SS`
  rollover, zero-padding, artifact-only fragments skipped, empty input returns
  `""`.
- `test_fetcher.py` — mocked snippets carry `start`; assert start times survive
  into the returned tuples.
- `test_cli.py` — update fetcher mocks to the tuple shape; end-to-end output
  file contains timestamped paragraphs.

## Non-goals

- Per-fragment (SRT-style) or fixed-interval timestamps.
- End times or durations in the output.
- Any flag to disable or reformat timestamps (add later only if needed).
- Retroactive migration of already-downloaded files (use `--force`).
