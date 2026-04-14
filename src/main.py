"""
main.py
~~~~~~~
CLI entry point for the Ashwin Azer MusicBrainz sync tool.

Usage examples:
    python -m src.main --help
    python -m src.main web              # scrape public sources + report
    python -m src.main web --evidence   # also generate evidence pack
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

from src.normalize import normalize_source_data  # noqa: E402
from src.mb_report import build_report, write_json_report, write_markdown_report  # noqa: E402
from src.evidence_pack import build_evidence_pack, write_evidence_pack, write_evidence_markdown  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)


def _run_web_scrape() -> dict:
    from src.web_scrape_ingest import fetch_full_discography

    logger.info("=== Scraping public sources (Last.fm) ===")
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


def cmd_web(args: argparse.Namespace) -> None:
    data = _run_web_scrape()
    _write_reports(data, args.evidence)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Ashwin Azer MusicBrainz Sync — scrape artist data from "
        "public web sources and generate MusicBrainz edit suggestions.",
    )
    parser.add_argument(
        "--evidence",
        action="store_true",
        help="Also generate an evidence pack alongside the main report.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    sp_web = subparsers.add_parser(
        "web",
        help="Scrape public sources (Last.fm) and produce a report.",
    )
    sp_web.add_argument("--evidence", action="store_true")
    sp_web.set_defaults(func=cmd_web)

    args = parser.parse_args(argv)
    try:
        args.func(args)
    except KeyError as exc:
        logger.error(
            "Missing required environment variable: %s. "
            "Copy .env.example to .env and fill in your settings.",
            exc,
        )
        return 1
    except Exception as exc:  # noqa: BLE001
        logger.error("Unexpected error: %s", exc, exc_info=True)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
