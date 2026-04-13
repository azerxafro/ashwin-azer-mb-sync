"""
main.py
~~~~~~~
CLI entry point for the Ashwin Azer MusicBrainz sync tool.

Usage examples:
    python -m src.main --help
    python -m src.main spotify          # ingest + report from Spotify only
    python -m src.main apple            # ingest + report from Apple Music only
    python -m src.main all              # ingest from both, merge, full report
    python -m src.main all --evidence   # also generate evidence pack
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Load .env file if present
load_dotenv()

from src.normalize import normalize_source_data, merge_sources  # noqa: E402
from src.mb_report import build_report, write_json_report, write_markdown_report  # noqa: E402
from src.evidence_pack import build_evidence_pack, write_evidence_pack, write_evidence_markdown  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)


def _run_spotify() -> dict:
    from src.spotify_ingest import fetch_full_discography

    logger.info("=== Ingesting from Spotify ===")
    raw = fetch_full_discography()
    return normalize_source_data(raw)


def _run_apple() -> dict:
    from src.apple_music_ingest import fetch_full_discography

    logger.info("=== Ingesting from Apple Music ===")
    raw = fetch_full_discography()
    return normalize_source_data(raw)


def _write_reports(merged_data: dict, generate_evidence: bool) -> None:
    report = build_report(merged_data)

    json_path = write_json_report(report)
    md_path = write_markdown_report(report)
    logger.info("Reports written:\n  JSON: %s\n  Markdown: %s", json_path, md_path)

    if generate_evidence:
        pack = build_evidence_pack(report)
        ep_json = write_evidence_pack(pack)
        ep_md = write_evidence_markdown(pack)
        logger.info(
            "Evidence packs written:\n  JSON: %s\n  Markdown: %s",
            ep_json,
            ep_md,
        )


def cmd_spotify(args: argparse.Namespace) -> None:
    spotify_data = _run_spotify()
    _write_reports(spotify_data, args.evidence)


def cmd_apple(args: argparse.Namespace) -> None:
    apple_data = _run_apple()
    _write_reports(apple_data, args.evidence)


def cmd_all(args: argparse.Namespace) -> None:
    spotify_data = _run_spotify()
    apple_data = _run_apple()
    merged = merge_sources(spotify_data, apple_data)
    _write_reports(merged, args.evidence)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Ashwin Azer MusicBrainz Sync — pull artist data from "
        "Spotify and Apple Music and generate MusicBrainz edit suggestions.",
    )
    parser.add_argument(
        "--evidence",
        action="store_true",
        help="Also generate an evidence pack alongside the main report.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    sp_spotify = subparsers.add_parser(
        "spotify",
        help="Ingest from Spotify only and produce a report.",
    )
    sp_spotify.add_argument("--evidence", action="store_true")
    sp_spotify.set_defaults(func=cmd_spotify)

    sp_apple = subparsers.add_parser(
        "apple",
        help="Ingest from Apple Music only and produce a report.",
    )
    sp_apple.add_argument("--evidence", action="store_true")
    sp_apple.set_defaults(func=cmd_apple)

    sp_all = subparsers.add_parser(
        "all",
        help="Ingest from both sources, merge, and produce a report.",
    )
    sp_all.add_argument("--evidence", action="store_true")
    sp_all.set_defaults(func=cmd_all)

    args = parser.parse_args(argv)
    try:
        args.func(args)
    except KeyError as exc:
        logger.error(
            "Missing required environment variable: %s. "
            "Copy .env.example to .env and fill in your credentials.",
            exc,
        )
        return 1
    except Exception as exc:  # noqa: BLE001
        logger.error("Unexpected error: %s", exc, exc_info=True)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
