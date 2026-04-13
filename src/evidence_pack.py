"""
evidence_pack.py
~~~~~~~~~~~~~~~~
Generate an "evidence pack" — a structured collection of URLs and source
citations to support MusicBrainz edits.

The pack is written as a JSON file (and optionally a Markdown summary) in the
evidence_packs/ output directory.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

EVIDENCE_DIR = Path(os.getenv("EVIDENCE_DIR", "evidence_packs"))


def _isrc_evidence(isrc: str) -> list[dict[str, str]]:
    """Return standard online ISRC lookup URLs as evidence sources."""
    return [
        {
            "source": "IFPI ISRC Search",
            "url": f"https://isrc.ifpi.org/search?q={isrc}",
        },
        {
            "source": "MusicBrainz ISRC",
            "url": f"https://musicbrainz.org/isrc/{isrc}",
        },
    ]


def build_evidence_pack(report: dict[str, Any]) -> dict[str, Any]:
    """
    Build a structured evidence pack from a MB report dict (output of
    ``mb_report.build_report``).
    """
    artist = report.get("artist", {})
    entries: list[dict[str, Any]] = []

    for candidate in report.get("release_candidates", []):
        title = candidate.get("title", "")
        sources: list[dict[str, str]] = []

        src_urls = candidate.get("source_urls", {})
        if src_urls.get("spotify"):
            sources.append(
                {
                    "source": "Spotify",
                    "url": src_urls["spotify"],
                    "description": f'Spotify listing for "{title}"',
                }
            )
        if src_urls.get("apple_music"):
            sources.append(
                {
                    "source": "Apple Music",
                    "url": src_urls["apple_music"],
                    "description": f'Apple Music listing for "{title}"',
                }
            )
        if candidate.get("artwork_url"):
            sources.append(
                {
                    "source": "Cover Art",
                    "url": candidate["artwork_url"],
                    "description": f'Cover artwork for "{title}"',
                }
            )

        # Collect ISRC evidence from tracks
        track_isrc_entries: list[dict[str, Any]] = []
        for track in candidate.get("tracks", []):
            if track.get("isrc"):
                track_isrc_entries.append(
                    {
                        "track": track.get("title"),
                        "isrc": track["isrc"],
                        "evidence_urls": _isrc_evidence(track["isrc"]),
                    }
                )

        entries.append(
            {
                "release_title": title,
                "release_type": candidate.get("type"),
                "release_date": candidate.get("release_date", {}),
                "mb_add_url": candidate.get("mb_add_release_url"),
                "source_citations": sources,
                "isrc_evidence": track_isrc_entries,
            }
        )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "artist": {
            "name": artist.get("name"),
            "spotify_url": artist.get("spotify_url"),
            "apple_music_url": artist.get("apple_music_url"),
        },
        "evidence_entries": entries,
    }


def write_evidence_pack(
    pack: dict[str, Any],
    output_dir: Path = EVIDENCE_DIR,
) -> Path:
    """Write the evidence pack to a JSON file and return the path."""
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = output_dir / f"evidence_pack_{timestamp}.json"
    path.write_text(json.dumps(pack, indent=2, ensure_ascii=False))
    logger.info("Evidence pack written to %s", path)
    return path


def write_evidence_markdown(
    pack: dict[str, Any],
    output_dir: Path = EVIDENCE_DIR,
) -> Path:
    """Write a Markdown summary of the evidence pack and return the path."""
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = output_dir / f"evidence_pack_{timestamp}.md"

    artist = pack.get("artist", {})
    lines: list[str] = [
        f"# Evidence Pack — {artist.get('name', 'Unknown Artist')}",
        "",
        f"_Generated at: {pack['generated_at']}_",
        "",
        "## Artist Sources",
        "",
    ]
    if artist.get("spotify_url"):
        lines.append(f"- Spotify: [{artist['spotify_url']}]({artist['spotify_url']})")
    if artist.get("apple_music_url"):
        lines.append(f"- Apple Music: [{artist['apple_music_url']}]({artist['apple_music_url']})")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Release Evidence")
    lines.append("")

    for i, entry in enumerate(pack.get("evidence_entries", []), 1):
        rd = entry.get("release_date", {})
        date_str = "-".join(
            v for v in [rd.get("year"), rd.get("month"), rd.get("day")] if v
        )
        lines.append(f"### {i}. {entry['release_title']}")
        lines.append("")
        lines.append(f"- **Type:** {entry.get('release_type', 'Unknown')}")
        lines.append(f"- **Release Date:** {date_str or 'Unknown'}")
        if entry.get("mb_add_url"):
            lines.append(f"- **[→ Add to MusicBrainz]({entry['mb_add_url']})**")
        lines.append("")
        lines.append("**Sources:**")
        lines.append("")
        for src in entry.get("source_citations", []):
            lines.append(f"- [{src['source']}]({src['url']}) — {src.get('description', '')}")
        lines.append("")

        if entry.get("isrc_evidence"):
            lines.append("**ISRC Evidence:**")
            lines.append("")
            lines.append("| Track | ISRC | IFPI Lookup | MusicBrainz |")
            lines.append("|-------|------|-------------|-------------|")
            for ie in entry["isrc_evidence"]:
                ev_urls = {e["source"]: e["url"] for e in ie.get("evidence_urls", [])}
                ifpi_link = f"[Link]({ev_urls.get('IFPI ISRC Search', '#')})"
                mb_link = f"[Link]({ev_urls.get('MusicBrainz ISRC', '#')})"
                lines.append(
                    f"| {ie.get('track', '')} | `{ie['isrc']}` | {ifpi_link} | {mb_link} |"
                )
            lines.append("")

    path.write_text("\n".join(lines))
    logger.info("Evidence Markdown written to %s", path)
    return path
