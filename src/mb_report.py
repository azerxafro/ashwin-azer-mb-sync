"""
mb_report.py
~~~~~~~~~~~~
Generate a JSON data file and a human-readable Markdown report of candidate
MusicBrainz additions/corrections, together with pre-filled edit-form URLs.

MusicBrainz does NOT allow automated edits via its API; all generated links
point to web forms for manual submission by a logged-in editor.
"""

from __future__ import annotations

import json
import logging
import os
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

REPORTS_DIR = Path(os.getenv("REPORTS_DIR", "reports"))

# MusicBrainz base URL for edit forms
MB_BASE = "https://musicbrainz.org"

# Known MusicBrainz MBID for Ashwin Azer (if already exists; leave empty otherwise)
ARTIST_MBID = os.getenv("ARTIST_MBID", "")


# ---------------------------------------------------------------------------
# URL builders
# ---------------------------------------------------------------------------


def mb_add_release_url(
    release_title: str,
    artist_name: str,
    release_date: dict[str, str | None],
    release_type: str,
    label: str | None = None,
    barcode: str | None = None,
) -> str:
    """
    Build a pre-filled URL for the MusicBrainz 'Add Release' form.

    Reference: https://musicbrainz.org/release/add
    """
    params: dict[str, str] = {
        "artist_credit[0][artist][name]": artist_name,
        "release_title": release_title,
        "type": release_type,
    }
    if release_date.get("year"):
        params["date[year]"] = release_date["year"]
    if release_date.get("month"):
        params["date[month]"] = release_date["month"]
    if release_date.get("day"):
        params["date[day]"] = release_date["day"]
    if label:
        params["label"] = label
    if barcode:
        params["barcode"] = barcode

    return f"{MB_BASE}/release/add?{urllib.parse.urlencode(params)}"


def mb_artist_page_url(mbid: str) -> str:
    return f"{MB_BASE}/artist/{mbid}"


def mb_isrc_search_url(isrc: str) -> str:
    return f"{MB_BASE}/isrc/{isrc}"


# ---------------------------------------------------------------------------
# Report builders
# ---------------------------------------------------------------------------


def _extract_source_ids(release: dict[str, Any]) -> dict[str, str | None]:
    """Return a dict of {spotify, apple_music} source IDs from a release dict."""
    source = release.get("source")
    source_id = release.get("source_id")
    return {
        "spotify": source_id if source == "spotify" else release.get("spotify_source_id"),
        "apple_music": (
            release.get("apple_source_id")
            or (source_id if source == "apple_music" else None)
        ),
    }


def _extract_source_urls(release: dict[str, Any]) -> dict[str, str | None]:
    """Return a dict of {spotify, apple_music} URLs from a release dict."""
    source = release.get("source")
    url = release.get("url")
    return {
        "spotify": url if source == "spotify" else None,
        "apple_music": release.get("apple_url") or (url if source == "apple_music" else None),
    }


def build_release_candidate(
    release: dict[str, Any],
    artist_name: str,
) -> dict[str, Any]:
    """Convert a normalized release dict into a MusicBrainz candidate record."""
    edit_url = mb_add_release_url(
        release_title=release["title"],
        artist_name=artist_name,
        release_date=release.get("release_date", {}),
        release_type=release.get("type", "Album"),
        label=release.get("label"),
        barcode=release.get("upc"),
    )

    missing_fields: list[str] = []
    if not release.get("label"):
        missing_fields.append("label")
    if not release.get("upc"):
        missing_fields.append("barcode/UPC")

    isrc_coverage = sum(
        1 for t in release.get("tracks", []) if t.get("isrc")
    )
    total_tracks = len(release.get("tracks", []))
    if isrc_coverage < total_tracks:
        missing_fields.append(
            f"ISRC codes ({total_tracks - isrc_coverage}/{total_tracks} missing)"
        )

    track_list = []
    for t in release.get("tracks", []):
        track_list.append(
            {
                "position": t.get("track_number"),
                "title": t.get("title"),
                "duration_seconds": t.get("duration_seconds"),
                "isrc": t.get("isrc"),
                "source_url": t.get("url"),
            }
        )

    return {
        "title": release["title"],
        "type": release.get("type"),
        "release_date": release.get("release_date", {}),
        "label": release.get("label"),
        "barcode": release.get("upc"),
        "source_ids": _extract_source_ids(release),
        "source_urls": _extract_source_urls(release),
        "artwork_url": release.get("artwork_url"),
        "mb_add_release_url": edit_url,
        "missing_fields": missing_fields,
        "tracks": track_list,
    }


def build_report(merged_data: dict[str, Any]) -> dict[str, Any]:
    """Build the full JSON report from merged normalized data."""
    artist = merged_data.get("artist", {})
    artist_name = artist.get("name", "Unknown Artist")

    candidates = [
        build_release_candidate(r, artist_name)
        for r in merged_data.get("releases", [])
    ]

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "artist": {
            "name": artist_name,
            "spotify_id": artist.get("spotify_id"),
            "apple_music_id": artist.get("apple_music_id"),
            "spotify_url": artist.get("spotify_url"),
            "apple_music_url": artist.get("apple_music_url"),
            "mbid": ARTIST_MBID or None,
            "mb_url": mb_artist_page_url(ARTIST_MBID) if ARTIST_MBID else None,
        },
        "note": (
            "MusicBrainz does not allow automated edits. "
            "All mb_add_release_url links are for manual submission by a "
            "logged-in editor."
        ),
        "release_candidates": candidates,
    }


def write_json_report(report: dict[str, Any], output_dir: Path = REPORTS_DIR) -> Path:
    """Write the report to a JSON file and return the path."""
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = output_dir / f"mb_report_{timestamp}.json"
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    logger.info("JSON report written to %s", path)
    return path


def write_markdown_report(report: dict[str, Any], output_dir: Path = REPORTS_DIR) -> Path:
    """Write the report to a Markdown file and return the path."""
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = output_dir / f"mb_report_{timestamp}.md"

    artist = report["artist"]
    lines: list[str] = [
        f"# MusicBrainz Sync Report — {artist['name']}",
        "",
        f"_Generated at: {report['generated_at']}_",
        "",
        f"> **Note:** {report['note']}",
        "",
        "## Artist",
        "",
        f"- **Name:** {artist['name']}",
    ]
    if artist.get("spotify_url"):
        lines.append(f"- **Spotify:** [{artist['spotify_url']}]({artist['spotify_url']})")
    if artist.get("apple_music_url"):
        lines.append(f"- **Apple Music:** [{artist['apple_music_url']}]({artist['apple_music_url']})")
    if artist.get("mbid"):
        lines.append(f"- **MusicBrainz:** [{artist['mb_url']}]({artist['mb_url']})")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Release Candidates")
    lines.append("")

    for i, candidate in enumerate(report.get("release_candidates", []), 1):
        lines.append(f"### {i}. {candidate['title']}")
        lines.append("")
        rd = candidate.get("release_date", {})
        date_str = "-".join(
            v for v in [rd.get("year"), rd.get("month"), rd.get("day")] if v
        )
        lines.append(f"- **Type:** {candidate.get('type', 'Unknown')}")
        lines.append(f"- **Release Date:** {date_str or 'Unknown'}")
        if candidate.get("label"):
            lines.append(f"- **Label:** {candidate['label']}")
        if candidate.get("barcode"):
            lines.append(f"- **Barcode/UPC:** {candidate['barcode']}")
        src = candidate.get("source_urls", {})
        if src.get("spotify"):
            lines.append(f"- **Spotify:** [{src['spotify']}]({src['spotify']})")
        if src.get("apple_music"):
            lines.append(f"- **Apple Music:** [{src['apple_music']}]({src['apple_music']})")
        if candidate.get("artwork_url"):
            lines.append(f"- **Artwork:** [{candidate['artwork_url']}]({candidate['artwork_url']})")
        lines.append(
            f"- **[→ Add to MusicBrainz]({candidate['mb_add_release_url']})**"
        )
        if candidate.get("missing_fields"):
            lines.append(f"- ⚠️ **Missing fields:** {', '.join(candidate['missing_fields'])}")

        if candidate.get("tracks"):
            lines.append("")
            lines.append("#### Tracks")
            lines.append("")
            lines.append("| # | Title | Duration | ISRC |")
            lines.append("|---|-------|----------|------|")
            for t in candidate["tracks"]:
                dur = f"{t['duration_seconds']}s" if t.get("duration_seconds") else "—"
                isrc = t.get("isrc") or "—"
                if t.get("isrc"):
                    isrc = f"[{isrc}]({mb_isrc_search_url(isrc)})"
                lines.append(
                    f"| {t.get('position', '')} | {t.get('title', '')} | {dur} | {isrc} |"
                )

        lines.append("")

    path.write_text("\n".join(lines))
    logger.info("Markdown report written to %s", path)
    return path
