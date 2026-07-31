# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

`yt-transcribe` — a Python CLI that downloads YouTube video transcripts using the
captions YouTube already hosts (via `youtube-transcript-api`), no API key or
audio download. Input: video URLs (args or list file); output: one plain-text
file per video.

The authoritative design spec is
`docs/superpowers/specs/2026-07-31-youtube-transcription-design.md` — read it
before implementing or changing behavior. Deliberate non-goals (Whisper
fallback, parallelism, timestamps, playlists) are listed there; don't add them
unprompted.

## Commands

Package management is `uv` (Python 3.11+, hatchling build).

```bash
uv sync                                  # create venv, install deps
uv run pytest                            # run all tests
uv run pytest tests/test_urls.py         # run one test file
uv run pytest tests/test_urls.py::test_name -x   # run a single test
uv run yt-transcribe <url>               # run the CLI
```

## Architecture

Flat package `yt_transcribe/`; `cli.py` is the only module that imports the
others — keep it that way:

- `cli.py` — argparse, per-video orchestration loop, summary report, exit codes
  (0 all ok, 1 any video failed, 2 usage error)
- `urls.py` — normalize every accepted reference form (`watch?v=`, `youtu.be`,
  `shorts/`, `live/`, bare 11-char ID) to a video ID
- `fetcher.py` — transcript selection/fetch via `youtube-transcript-api`:
  requested languages in priority order, human-made captions preferred over
  auto-generated, then any available
- `formatter.py` — join caption fragments into clean readable paragraphs
- `writer.py` — video title via YouTube oEmbed (keyless), filename
  sanitization, writes `<title>_<id>.txt`; oEmbed failure degrades to
  `<id>.txt`, never fails the video

Error-handling invariant: each video is isolated — a failure is recorded with a
reason and the batch continues.

Tests mock all network access (`youtube-transcript-api` and oEmbed); no live
YouTube calls in the suite.

## Status

Scaffold only: module files are stubs, `cli.main()` raises `NotImplementedError`.
Implementation follows the superpowers flow — spec is approved; next step is a
written implementation plan (`writing-plans` skill), then TDD per module.
