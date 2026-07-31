# yt-transcribe

Download YouTube video transcripts (captions) as plain-text files.

A Python CLI that fetches the captions YouTube already hosts — manual or
auto-generated — with no API key, no audio download, and no speech-to-text.
Input: a single video URL, multiple URLs, or a file with one URL per line;
output: a folder of plain-text transcript files, one per video, with
`[M:SS]`-timestamped paragraphs.

## Install

```bash
uv sync
```

## Usage

Run the tool via `uv run yt-transcribe`:

```bash
uv run yt-transcribe <url> [<url> …]           # one or more videos
uv run yt-transcribe -f videos.txt -o ./out    # list file; positional URLs may be mixed in
uv run yt-transcribe --lang ru,en <url>        # caption language priority
uv run yt-transcribe --force <url>             # overwrite existing output files
uv run yt-transcribe --version                 # print the installed version
```

### Flags

| Flag | Default | Meaning |
|------|---------|---------|
| `-f, --file PATH` | — | File with one URL per line; blank lines and `#` comments ignored |
| `-o, --output DIR` | `./transcripts/` | Output folder, created if missing |
| `--lang CODES` | `en` | Comma-separated caption-language priority list |
| `--force` | off | Overwrite existing `.txt` files (default: skip already-downloaded) |
| `--version` | — | Print the installed version and exit |

### Accepted video references

- `watch?v=<id>` — full YouTube URL
- `youtu.be/<id>` — short link
- `shorts/<id>` — YouTube Shorts
- `live/<id>` — YouTube Live
- `<id>` — bare 11-character video ID

Output: one `.txt` per video in the output folder (default `./transcripts/`),
named `<title>_<video-id>.txt`. Each paragraph starts with the video time of
its first sentence — `[M:SS]`, or `[H:MM:SS]` past the one-hour mark:

```text
[0:00] Welcome back to the channel. Today we are looking at...

[1:12] So the first thing you will notice is...
```

Already-downloaded videos are skipped unless `--force` is given; files saved
before timestamps were added keep the old format until regenerated with
`--force`.

### Exit codes

- **0** — all videos processed successfully
- **1** — one or more videos failed (transcript unavailable, private video, etc.)
- **2** — usage error (no input given, list file missing, invalid arguments)

## Development

```bash
uv run pytest
```

Design specs: [core CLI](docs/superpowers/specs/2026-07-31-youtube-transcription-design.md) ·
[paragraph timestamps](docs/superpowers/specs/2026-07-31-transcript-timestamps-design.md)

Changes: [CHANGELOG.md](CHANGELOG.md)
