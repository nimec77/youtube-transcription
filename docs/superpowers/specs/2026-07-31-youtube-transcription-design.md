# YouTube Transcript Downloader — Design

**Date:** 2026-07-31
**Status:** Approved

## Overview

A Python CLI tool that downloads transcripts of YouTube videos using the captions
YouTube already hosts (manual or auto-generated). Input is a single video URL or a
file with a list of URLs; output is a folder of plain-text transcript files, one
per video.

## Goals

- Fetch existing YouTube captions — no audio download, no speech-to-text, no API key.
- Accept a single URL, multiple URLs, or a list file; write one `.txt` per video.
- Survive bad inputs: one failed video never aborts the batch.
- Stay small: four focused modules, unit-testable with the network mocked.

## Non-goals (YAGNI — possible later extensions)

- Whisper/speech-to-text fallback for videos without captions.
- Parallel downloads.
- ~~Timestamped output.~~ Added later — see
  `2026-07-31-transcript-timestamps-design.md`.
- Playlist/channel expansion.
- Any GUI or web interface.

## Approach

Use the `youtube-transcript-api` library, which fetches captions via YouTube's
internal API. Video titles for filenames come from YouTube's public oEmbed
endpoint (`https://www.youtube.com/oembed?url=…`) — also keyless.

Alternatives considered and rejected:

- **`yt-dlp` as engine** — very robust, but downloads VTT/SRT that must then be
  parsed and cleaned; a much heavier dependency than needed. Revisit if a Whisper
  fallback is ever added.
- **Official YouTube Data API** — `captions.download` only works for videos the
  authenticated user owns; useless for arbitrary videos.

## CLI Interface

Installable package (`pyproject.toml`, `uv`-managed) exposing a `yt-transcribe`
console script.

```
yt-transcribe <url> [<url> …]           # one or more videos
yt-transcribe -f videos.txt -o ./out    # list file; positional URLs may be mixed in
yt-transcribe --lang ru,en <url>        # caption language priority
yt-transcribe --force <url>             # overwrite existing output files
```

Flags:

| Flag | Default | Meaning |
|------|---------|---------|
| `-f, --file PATH` | — | File with one URL per line; blank lines and `#` comments ignored |
| `-o, --output DIR` | `./transcripts/` | Output folder, created if missing |
| `--lang CODES` | `en` + video's original language | Comma-separated caption-language priority list |
| `--force` | off | Overwrite existing `.txt` files (default: skip already-downloaded) |

Accepted video references: `watch?v=` URLs, `youtu.be/` short links, `shorts/`,
`live/`, and bare 11-character video IDs.

## Architecture

```
yt_transcribe/
  cli.py         # argparse, orchestration loop, summary report, exit code
  urls.py        # URL/ID parsing: extract video IDs from all accepted forms + list file
  fetcher.py     # youtube-transcript-api calls: list transcripts, pick language, fetch
  formatter.py   # join caption fragments into clean readable paragraphs
  writer.py      # title via oEmbed, filename sanitization, write .txt to output dir
```

Each module has one purpose and a narrow interface; `cli.py` is the only module
that imports the others.

### Data flow

1. `cli.py` collects video references from argv and/or the list file.
2. `urls.py` normalizes each reference to a video ID (or reports it invalid).
3. For each ID, `fetcher.py` picks the best transcript: try requested languages in
   order, preferring human-made captions over auto-generated within each language;
   fall back to auto-generated; fall back to whatever exists.
4. `formatter.py` joins the caption fragments into paragraphs (strip caption
   artifacts, merge fragments into sentences, wrap into readable blocks).
5. `writer.py` fetches the title via oEmbed, builds `<sanitized-title>_<id>.txt`,
   and writes it to the output folder. If oEmbed fails, the filename is just
   `<id>.txt` — a title lookup failure never fails the video.
6. `cli.py` prints per-video status as it goes and a final summary.

## Error handling

- Per-video isolation: each video is wrapped in try/except; failures are recorded
  with a human-readable reason (captions disabled, video private/unavailable,
  invalid URL, network error) and the batch continues.
- Final summary: `N saved, M skipped (reasons)`; exit code 0 if all succeeded,
  1 if any failed, 2 for usage errors (no input given, list file missing).
- Existing output files are skipped by default (cheap re-runs); `--force`
  overwrites.

## Testing

- `pytest` unit tests per module:
  - `urls.py` — every accepted URL form, invalid inputs, list-file parsing.
  - `formatter.py` — fragment joining, artifact stripping, paragraph wrapping.
  - `writer.py` — filename sanitization (slashes, emoji, length), collision-free
    naming, skip-vs-force behavior (tmp_path).
  - `fetcher.py` — language-selection logic against mocked transcript lists.
- `cli.py` — end-to-end run with fetcher/oEmbed mocked: mixed good/bad inputs
  produce correct files, summary, and exit code.
- No live-network tests in the default suite.
