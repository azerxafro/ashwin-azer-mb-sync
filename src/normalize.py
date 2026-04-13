"""
normalize.py
~~~~~~~~~~~~
Normalize raw metadata from Spotify and Apple Music into a unified schema
compatible with the MusicBrainz data model.

MusicBrainz entity reference:
    https://musicbrainz.org/doc/MusicBrainz_Entity
"""

from __future__ import annotations

import re
from typing import Any

# Mapping of Spotify/Apple Music album type strings to MusicBrainz release types
_RELEASE_TYPE_MAP: dict[str, str] = {
    # Spotify
    "album": "Album",
    "single": "Single",
    "compilation": "Compilation",
    "ep": "EP",
    # Apple Music
    "lp": "Album",
    "studio": "Album",
    "soundtrack": "Soundtrack",
    "live": "Live",
    "remix": "Remix",
}


def _map_release_type(raw_type: str | None) -> str:
    if not raw_type:
        return "Album"
    return _RELEASE_TYPE_MAP.get(raw_type.lower(), raw_type.capitalize())


def _clean_title(title: str | None) -> str:
    if not title:
        return ""
    # Strip leading/trailing whitespace; collapse internal runs of spaces
    return re.sub(r" {2,}", " ", title.strip())


def _duration_ms_to_seconds(ms: int | None) -> int | None:
    if ms is None:
        return None
    return ms // 1000


def _parse_release_date(raw: str | None, precision: str | None = None) -> dict[str, str | None]:
    """
    Return a dict with year, month, day extracted from an ISO-8601 date string.
    Apple Music always provides full dates; Spotify may give year-only strings
    and signals precision via release_date_precision.
    """
    result: dict[str, str | None] = {"year": None, "month": None, "day": None}
    if not raw:
        return result

    parts = raw.split("-")
    result["year"] = parts[0] if len(parts) >= 1 else None
    result["month"] = parts[1] if len(parts) >= 2 else None
    result["day"] = parts[2] if len(parts) >= 3 else None

    # Respect Spotify's precision signal
    if precision == "year":
        result["month"] = None
        result["day"] = None
    elif precision == "month":
        result["day"] = None

    return result


# ---------------------------------------------------------------------------
# Public normalization helpers
# ---------------------------------------------------------------------------


def normalize_track(raw: dict[str, Any], source: str) -> dict[str, Any]:
    """
    Normalize a single track dict from either Spotify or Apple Music into a
    canonical track schema for MusicBrainz comparison.
    """
    return {
        "source": source,
        "source_id": raw.get("id"),
        "title": _clean_title(raw.get("title")),
        "track_number": raw.get("track_number"),
        "disc_number": raw.get("disc_number"),
        "duration_seconds": _duration_ms_to_seconds(raw.get("duration_ms")),
        "isrc": raw.get("isrc").upper() if raw.get("isrc") else None,
        "artists": raw.get("artists", []),
        "composers": raw.get("composers"),
        "url": raw.get("spotify_url") or raw.get("apple_music_url"),
    }


def normalize_release(raw: dict[str, Any], source: str) -> dict[str, Any]:
    """
    Normalize a single album/release dict into a canonical release schema.
    """
    tracks = [normalize_track(t, source) for t in raw.get("tracks", [])]

    date_info = _parse_release_date(
        raw.get("release_date"),
        raw.get("release_date_precision"),
    )

    return {
        "source": source,
        "source_id": raw.get("id"),
        "title": _clean_title(raw.get("title")),
        "type": _map_release_type(raw.get("type")),
        "release_date": date_info,
        "total_tracks": raw.get("total_tracks"),
        "label": raw.get("label") or raw.get("record_label"),
        "upc": raw.get("upc").strip() if raw.get("upc") else None,
        "url": raw.get("spotify_url") or raw.get("apple_music_url"),
        "artwork_url": (
            raw.get("images", [{}])[0].get("url")
            if raw.get("images")
            else raw.get("artwork_url")
        ),
        "tracks": tracks,
    }


def normalize_artist(raw: dict[str, Any], source: str) -> dict[str, Any]:
    """Normalize an artist dict."""
    return {
        "source": source,
        "source_id": raw.get("id"),
        "name": _clean_title(raw.get("name")),
        "genres": raw.get("genres") or raw.get("genre_names", []),
        "url": raw.get("spotify_url") or raw.get("apple_music_url"),
    }


def normalize_source_data(raw: dict[str, Any]) -> dict[str, Any]:
    """
    Top-level normalization: accepts the output of either
    ``spotify_ingest.fetch_full_discography`` or
    ``apple_music_ingest.fetch_full_discography`` and returns a
    unified representation.
    """
    source = raw.get("source", "unknown")
    artist = normalize_artist(raw.get("artist", {}), source)
    releases = [normalize_release(album, source) for album in raw.get("discography", [])]
    return {
        "source": source,
        "artist": artist,
        "releases": releases,
    }


def merge_sources(
    spotify_data: dict[str, Any],
    apple_data: dict[str, Any],
) -> dict[str, Any]:
    """
    Merge normalized Spotify and Apple Music data into a single unified view,
    de-duplicating releases by ISRC where possible and preferring the source
    with more complete metadata.
    """
    # Index Spotify releases by (title, type) for O(1) lookup
    spotify_releases = {
        (r["title"].lower(), r["type"]): r for r in spotify_data.get("releases", [])
    }

    merged_releases: list[dict[str, Any]] = []
    seen_keys: set[tuple[str, str]] = set()

    for apple_release in apple_data.get("releases", []):
        key = (apple_release["title"].lower(), apple_release["type"])
        spotify_release = spotify_releases.get(key)

        if spotify_release:
            # Merge: prefer Apple Music for label/UPC, Spotify for ISRC on tracks
            merged = {**spotify_release}
            merged["apple_source_id"] = apple_release["source_id"]
            merged["apple_url"] = apple_release["url"]
            if apple_release.get("label") and not merged.get("label"):
                merged["label"] = apple_release["label"]
            if apple_release.get("upc") and not merged.get("upc"):
                merged["upc"] = apple_release["upc"]
            # Enrich tracks with ISRC from Apple Music where Spotify is missing
            for s_track in merged.get("tracks", []):
                for a_track in apple_release.get("tracks", []):
                    if s_track["title"].lower() == a_track["title"].lower():
                        if not s_track.get("isrc") and a_track.get("isrc"):
                            s_track["isrc"] = a_track["isrc"]
                        break
            merged_releases.append(merged)
        else:
            merged_releases.append(apple_release)
        seen_keys.add(key)

    # Add any Spotify-only releases
    for key, s_release in spotify_releases.items():
        if key not in seen_keys:
            merged_releases.append(s_release)

    artist_name = (
        spotify_data.get("artist", {}).get("name")
        or apple_data.get("artist", {}).get("name")
    )
    return {
        "artist": {
            "name": artist_name,
            "spotify_id": spotify_data.get("artist", {}).get("source_id"),
            "apple_music_id": apple_data.get("artist", {}).get("source_id"),
            "spotify_url": spotify_data.get("artist", {}).get("url"),
            "apple_music_url": apple_data.get("artist", {}).get("url"),
            "genres": list(
                set(
                    spotify_data.get("artist", {}).get("genres", [])
                    + apple_data.get("artist", {}).get("genres", [])
                )
            ),
        },
        "releases": merged_releases,
    }
