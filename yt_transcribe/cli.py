"""Command-line entry point: argument parsing, orchestration loop, summary report."""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

from yt_transcribe import __version__, fetcher, formatter, urls, writer

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
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
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
        except (OSError, UnicodeDecodeError) as exc:
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
