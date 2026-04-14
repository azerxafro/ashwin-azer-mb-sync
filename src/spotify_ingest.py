"""
spotify_ingest.py
~~~~~~~~~~~~~~~~~
Pull artist metadata from the Spotify Web API using the spotipy library.

Required environment variables:
    SPOTIFY_CLIENT_ID      – Spotify app client ID
    SPOTIFY_CLIENT_SECRET  – Spotify app client secret
    SPOTIFY_ARTIST_ID      – Target artist Spotify ID (default: Ashwin Azer)
"""

from __future__ import annotations

import logging
import os
from typing import Any

import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

logger = logging.getLogger(__name__)

SPOTIFY_ARTIST_ID = os.getenv("SPOTIFY_ARTIST_ID", "6M1VSmwtcuwS1DnvXTGk7P")


def _client() -> spotipy.Spotify:
    """Return an authenticated Spotify client using the Client Credentials flow."""
    client_id = os.environ.get("SPOTIFY_CLIENT_ID")
    if not client_id:
        raise KeyError("SPOTIFY_CLIENT_ID")
    client_secret = os.environ.get("SPOTIFY_CLIENT_SECRET")
    if not client_secret:
        raise KeyError("SPOTIFY_CLIENT_SECRET")
    auth_manager = SpotifyClientCredentials(
        client_id=client_id,
        client_secret=client_secret,
    )
    return spotipy.Spotify(auth_manager=auth_manager)


def fetch_artist(artist_id: str = SPOTIFY_ARTIST_ID) -> dict[str, Any]:
    """Fetch artist profile from Spotify."""
    sp = _client()
    logger.info("Fetching Spotify artist profile for %s", artist_id)
    artist = sp.artist(artist_id)
    return artist


def fetch_albums(
    artist_id: str = SPOTIFY_ARTIST_ID,
    album_types: tuple[str, ...] = ("album", "single", "compilation"),
) -> list[dict[str, Any]]:
    """Fetch all albums/singles for an artist, handling pagination."""
    sp = _client()
    logger.info("Fetching Spotify albums for artist %s", artist_id)
    results: list[dict[str, Any]] = []
    response = sp.artist_albums(
        artist_id,
        album_type=",".join(album_types),
        limit=50,
    )
    while response:
        results.extend(response.get("items", []))
        response = sp.next(response) if response.get("next") else None
    return results


def fetch_album_tracks(album_id: str) -> list[dict[str, Any]]:
    """Fetch all tracks for a given album, handling pagination."""
    sp = _client()
    results: list[dict[str, Any]] = []
    response = sp.album_tracks(album_id, limit=50)
    while response:
        results.extend(response.get("items", []))
        response = sp.next(response) if response.get("next") else None
    return results


def fetch_full_discography(artist_id: str = SPOTIFY_ARTIST_ID) -> dict[str, Any]:
    """
    Fetch artist profile, all albums, and all tracks (with ISRC codes where
    available).  Returns a structured dict ready for normalization.
    """
    artist_data = fetch_artist(artist_id)
    albums = fetch_albums(artist_id)

    discography: list[dict[str, Any]] = []
    sp = _client()

    for album_stub in albums:
        album_id = album_stub["id"]
        # Fetch full album to get tracks with ISRC
        full_album: dict[str, Any] = sp.album(album_id)
        tracks_raw = fetch_album_tracks(album_id)

        tracks: list[dict[str, Any]] = []
        for track in tracks_raw:
            # ISRC lives inside external_ids on the full track object
            full_track = sp.track(track["id"])
            isrc = full_track.get("external_ids", {}).get("isrc")
            tracks.append(
                {
                    "id": track["id"],
                    "title": track["name"],
                    "track_number": track.get("track_number"),
                    "disc_number": track.get("disc_number"),
                    "duration_ms": track.get("duration_ms"),
                    "isrc": isrc,
                    "spotify_url": track.get("external_urls", {}).get("spotify"),
                    "artists": [a["name"] for a in track.get("artists", [])],
                }
            )

        discography.append(
            {
                "id": album_id,
                "title": full_album["name"],
                "type": full_album.get("album_type"),
                "release_date": full_album.get("release_date"),
                "release_date_precision": full_album.get("release_date_precision"),
                "total_tracks": full_album.get("total_tracks"),
                "label": full_album.get("label"),
                "upc": full_album.get("external_ids", {}).get("upc"),
                "spotify_url": full_album.get("external_urls", {}).get("spotify"),
                "images": full_album.get("images", []),
                "tracks": tracks,
            }
        )

    return {
        "source": "spotify",
        "artist": {
            "id": artist_data["id"],
            "name": artist_data["name"],
            "genres": artist_data.get("genres", []),
            "popularity": artist_data.get("popularity"),
            "followers": artist_data.get("followers", {}).get("total"),
            "spotify_url": artist_data.get("external_urls", {}).get("spotify"),
            "images": artist_data.get("images", []),
        },
        "discography": discography,
    }
