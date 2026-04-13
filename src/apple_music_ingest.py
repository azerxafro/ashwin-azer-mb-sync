"""
apple_music_ingest.py
~~~~~~~~~~~~~~~~~~~~~
Pull artist metadata from the Apple Music API using MusicKit developer tokens.

Required environment variables:
    APPLE_TEAM_ID            – Apple Developer Team ID
    APPLE_KEY_ID             – MusicKit key ID (starts with a 10-char code)
    APPLE_PRIVATE_KEY_PATH   – Path to the .p8 private key file
    APPLE_MUSIC_ARTIST_ID    – Target Apple Music artist ID (default: Ashwin Azer)
    APPLE_MUSIC_STOREFRONT   – Apple Music storefront country code (default: "in")

Reference: https://developer.apple.com/documentation/applemusicapi
"""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import Any

import jwt
import requests

logger = logging.getLogger(__name__)

APPLE_MUSIC_BASE_URL = "https://api.music.apple.com/v1"
APPLE_MUSIC_ARTIST_ID = os.getenv("APPLE_MUSIC_ARTIST_ID", "1497428225")
APPLE_MUSIC_STOREFRONT = os.getenv("APPLE_MUSIC_STOREFRONT", "in")


def _generate_developer_token() -> str:
    """
    Generate a short-lived Apple Music developer token (JWT) signed with the
    MusicKit private key.
    """
    team_id = os.environ["APPLE_TEAM_ID"]
    key_id = os.environ["APPLE_KEY_ID"]
    private_key_path = Path(os.environ["APPLE_PRIVATE_KEY_PATH"])

    private_key = private_key_path.read_text()

    now = int(time.time())
    payload = {
        "iss": team_id,
        "iat": now,
        "exp": now + 3600,  # token valid for 1 hour
    }
    token: str = jwt.encode(
        payload,
        private_key,
        algorithm="ES256",
        headers={"kid": key_id},
    )
    return token


def _headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {_generate_developer_token()}"}


def _get(path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    url = f"{APPLE_MUSIC_BASE_URL}/{path}"
    response = requests.get(url, headers=_headers(), params=params, timeout=30)
    response.raise_for_status()
    return response.json()


def fetch_artist(
    artist_id: str = APPLE_MUSIC_ARTIST_ID,
    storefront: str = APPLE_MUSIC_STOREFRONT,
) -> dict[str, Any]:
    """Fetch an artist's profile from Apple Music."""
    logger.info(
        "Fetching Apple Music artist profile for %s (storefront: %s)",
        artist_id,
        storefront,
    )
    data = _get(
        f"catalog/{storefront}/artists/{artist_id}",
        params={"include": "albums"},
    )
    return data


def fetch_albums(
    artist_id: str = APPLE_MUSIC_ARTIST_ID,
    storefront: str = APPLE_MUSIC_STOREFRONT,
) -> list[dict[str, Any]]:
    """Fetch all albums for an artist, handling pagination."""
    logger.info("Fetching Apple Music albums for artist %s", artist_id)
    albums: list[dict[str, Any]] = []
    url = f"catalog/{storefront}/artists/{artist_id}/albums"
    params: dict[str, Any] = {"limit": 25}

    while url:
        data = _get(url, params=params)
        albums.extend(data.get("data", []))
        next_href: str | None = data.get("next")
        if next_href:
            # next is a full path like /v1/catalog/...
            url = next_href.lstrip("/v1/")
            params = {}
        else:
            url = ""

    return albums


def fetch_album_tracks(
    album_id: str,
    storefront: str = APPLE_MUSIC_STOREFRONT,
) -> list[dict[str, Any]]:
    """Fetch all tracks for a given album."""
    logger.info("Fetching Apple Music tracks for album %s", album_id)
    tracks: list[dict[str, Any]] = []
    url = f"catalog/{storefront}/albums/{album_id}/tracks"
    params: dict[str, Any] = {"limit": 25}

    while url:
        data = _get(url, params=params)
        tracks.extend(data.get("data", []))
        next_href: str | None = data.get("next")
        if next_href:
            url = next_href.lstrip("/v1/")
            params = {}
        else:
            url = ""

    return tracks


def fetch_full_discography(
    artist_id: str = APPLE_MUSIC_ARTIST_ID,
    storefront: str = APPLE_MUSIC_STOREFRONT,
) -> dict[str, Any]:
    """
    Fetch artist profile, all albums, and all tracks.
    Returns a structured dict ready for normalization.
    """
    artist_raw = fetch_artist(artist_id, storefront)
    artist_attrs = {}
    if artist_raw.get("data"):
        artist_attrs = artist_raw["data"][0].get("attributes", {})

    albums_raw = fetch_albums(artist_id, storefront)
    discography: list[dict[str, Any]] = []

    for album in albums_raw:
        album_id = album["id"]
        album_attrs = album.get("attributes", {})
        tracks_raw = fetch_album_tracks(album_id, storefront)

        tracks: list[dict[str, Any]] = []
        for track in tracks_raw:
            track_attrs = track.get("attributes", {})
            tracks.append(
                {
                    "id": track["id"],
                    "title": track_attrs.get("name"),
                    "track_number": track_attrs.get("trackNumber"),
                    "disc_number": track_attrs.get("discNumber"),
                    "duration_ms": track_attrs.get("durationInMillis"),
                    "isrc": track_attrs.get("isrc"),
                    "apple_music_url": track_attrs.get("url"),
                    "composers": track_attrs.get("composerName"),
                    "genre_names": track_attrs.get("genreNames", []),
                }
            )

        discography.append(
            {
                "id": album_id,
                "title": album_attrs.get("name"),
                "type": album_attrs.get("albumType") or album_attrs.get("playlistType"),
                "release_date": album_attrs.get("releaseDate"),
                "total_tracks": album_attrs.get("trackCount"),
                "record_label": album_attrs.get("recordLabel"),
                "upc": album_attrs.get("upc"),
                "apple_music_url": album_attrs.get("url"),
                "artwork_url": (album_attrs.get("artwork") or {}).get("url"),
                "genre_names": album_attrs.get("genreNames", []),
                "tracks": tracks,
            }
        )

    return {
        "source": "apple_music",
        "artist": {
            "id": artist_id,
            "name": artist_attrs.get("name"),
            "genre_names": artist_attrs.get("genreNames", []),
            "artwork_url": (artist_attrs.get("artwork") or {}).get("url"),
            "apple_music_url": artist_attrs.get("url"),
        },
        "discography": discography,
    }
