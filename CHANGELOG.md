# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] — 2026-07-31

### Added

- Video timestamps in transcript output: every paragraph is prefixed with the
  time its first sentence starts in the video — `[M:SS]`, or `[H:MM:SS]` past
  the one-hour mark. Always on, no new flags
  ([design spec](docs/superpowers/specs/2026-07-31-transcript-timestamps-design.md)).

### Changed

- Transcript files gain `[M:SS]` paragraph prefixes; the paragraphs themselves
  are unchanged. Files downloaded before this change keep the old format until
  regenerated with `--force`.
- `fetcher.fetch_transcript` now returns `(start_seconds, text)` tuples instead
  of bare caption strings (internal API).

## [0.1.0] — 2026-07-31

### Added

- Initial implementation: `yt-transcribe` CLI that downloads YouTube captions
  as plain-text transcripts — no API key, no audio download, no speech-to-text.
- Accepted video references: `watch?v=`, `youtu.be`, `shorts/`, `live/` URLs
  and bare 11-character video IDs, passed as arguments or via a `--file` URL
  list (blank lines and `#` comments ignored).
- Caption selection: `--lang` priority order, human-made captions preferred
  over auto-generated within each language, fallback to any available language.
- Readable output: caption fragments joined into clean paragraphs, written as
  `<title>_<video-id>.txt` (title via keyless YouTube oEmbed; falls back to
  `<id>.txt` when the title lookup fails).
- Batch behavior: per-video error isolation (one failure never aborts the
  batch), already-downloaded videos skipped unless `--force`, per-video status
  lines plus a final summary, exit codes 0 (all ok) / 1 (any failed) /
  2 (usage error).

### Fixed

- Non-dict JSON payloads from the oEmbed endpoint no longer crash the title
  lookup; the video degrades to `<id>.txt` naming instead.
- Undecodable `--file` list files exit with a usage error instead of a
  traceback.
