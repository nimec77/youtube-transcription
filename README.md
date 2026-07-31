# yt-transcribe

Download YouTube video transcripts (captions) as plain-text files.

Fetches the captions YouTube already hosts — manual or auto-generated — with no
API key, no audio download, and no speech-to-text.

## Install

```bash
uv sync
```

## Usage

```bash
yt-transcribe <url> [<url> ...]           # one or more videos
yt-transcribe -f videos.txt -o ./out      # list file, one URL per line
yt-transcribe --lang ru,en <url>          # caption language priority
yt-transcribe --force <url>               # overwrite existing output files
```

Accepted video references: `watch?v=` URLs, `youtu.be/` short links, `shorts/`,
`live/`, and bare 11-character video IDs.

Output: one `.txt` per video in the output folder (default `./transcripts/`),
named `<title>_<video-id>.txt`. Already-downloaded videos are skipped unless
`--force` is given.

## Development

```bash
uv run pytest
```

Design spec: [docs/superpowers/specs/2026-07-31-youtube-transcription-design.md](docs/superpowers/specs/2026-07-31-youtube-transcription-design.md)
