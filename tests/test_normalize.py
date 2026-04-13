"""
Tests for normalize.py — verifies the core normalization and merge logic
without requiring any API credentials.
"""

from __future__ import annotations

import pytest

from src.normalize import (
    _clean_title,
    _duration_ms_to_seconds,
    _map_release_type,
    _parse_release_date,
    merge_sources,
    normalize_release,
    normalize_source_data,
    normalize_track,
)


# ---------------------------------------------------------------------------
# _clean_title
# ---------------------------------------------------------------------------


def test_clean_title_strips_whitespace():
    assert _clean_title("  Hello World  ") == "Hello World"


def test_clean_title_collapses_internal_spaces():
    assert _clean_title("Hello  World") == "Hello World"


def test_clean_title_none():
    assert _clean_title(None) == ""


# ---------------------------------------------------------------------------
# _duration_ms_to_seconds
# ---------------------------------------------------------------------------


def test_duration_ms_to_seconds_basic():
    assert _duration_ms_to_seconds(60000) == 60


def test_duration_ms_to_seconds_none():
    assert _duration_ms_to_seconds(None) is None


def test_duration_ms_to_seconds_truncates():
    # 1500ms → 1s (integer truncation)
    assert _duration_ms_to_seconds(1500) == 1


# ---------------------------------------------------------------------------
# _map_release_type
# ---------------------------------------------------------------------------


def test_map_release_type_album():
    assert _map_release_type("album") == "Album"


def test_map_release_type_single():
    assert _map_release_type("single") == "Single"


def test_map_release_type_unknown():
    assert _map_release_type("bootleg") == "Bootleg"


def test_map_release_type_none():
    assert _map_release_type(None) == "Album"


# ---------------------------------------------------------------------------
# _parse_release_date
# ---------------------------------------------------------------------------


def test_parse_release_date_full():
    result = _parse_release_date("2023-05-19")
    assert result == {"year": "2023", "month": "05", "day": "19"}


def test_parse_release_date_year_only():
    result = _parse_release_date("2021")
    assert result == {"year": "2021", "month": None, "day": None}


def test_parse_release_date_precision_year():
    result = _parse_release_date("2021-03-01", precision="year")
    assert result["month"] is None
    assert result["day"] is None


def test_parse_release_date_precision_month():
    result = _parse_release_date("2021-03-01", precision="month")
    assert result["month"] == "03"
    assert result["day"] is None


def test_parse_release_date_none():
    result = _parse_release_date(None)
    assert result == {"year": None, "month": None, "day": None}


# ---------------------------------------------------------------------------
# normalize_track
# ---------------------------------------------------------------------------


def _sample_spotify_track() -> dict:
    return {
        "id": "abc123",
        "title": "Starlight",
        "track_number": 1,
        "disc_number": 1,
        "duration_ms": 210000,
        "isrc": "INXXX2300001",
        "artists": ["Ashwin Azer"],
        "spotify_url": "https://open.spotify.com/track/abc123",
    }


def test_normalize_track_spotify():
    raw = _sample_spotify_track()
    track = normalize_track(raw, "spotify")
    assert track["source"] == "spotify"
    assert track["title"] == "Starlight"
    assert track["duration_seconds"] == 210
    assert track["isrc"] == "INXXX2300001"
    assert track["url"] == "https://open.spotify.com/track/abc123"


def test_normalize_track_isrc_uppercased():
    raw = {**_sample_spotify_track(), "isrc": "inxxx2300001"}
    track = normalize_track(raw, "spotify")
    assert track["isrc"] == "INXXX2300001"


def test_normalize_track_no_isrc():
    raw = {**_sample_spotify_track(), "isrc": None}
    track = normalize_track(raw, "spotify")
    assert track["isrc"] is None


# ---------------------------------------------------------------------------
# normalize_release
# ---------------------------------------------------------------------------


def _sample_spotify_release() -> dict:
    return {
        "id": "release_001",
        "title": " Moonrise EP ",
        "type": "single",
        "release_date": "2023-06-15",
        "release_date_precision": "day",
        "total_tracks": 1,
        "label": "Independent",
        "upc": "123456789012",
        "spotify_url": "https://open.spotify.com/album/release_001",
        "images": [{"url": "https://example.com/art.jpg"}],
        "tracks": [_sample_spotify_track()],
    }


def test_normalize_release_title_cleaned():
    raw = _sample_spotify_release()
    release = normalize_release(raw, "spotify")
    assert release["title"] == "Moonrise EP"


def test_normalize_release_type_mapped():
    raw = _sample_spotify_release()
    release = normalize_release(raw, "spotify")
    assert release["type"] == "Single"


def test_normalize_release_date():
    raw = _sample_spotify_release()
    release = normalize_release(raw, "spotify")
    assert release["release_date"] == {"year": "2023", "month": "06", "day": "15"}


def test_normalize_release_tracks_count():
    raw = _sample_spotify_release()
    release = normalize_release(raw, "spotify")
    assert len(release["tracks"]) == 1


# ---------------------------------------------------------------------------
# normalize_source_data
# ---------------------------------------------------------------------------


def _sample_spotify_source_data() -> dict:
    return {
        "source": "spotify",
        "artist": {
            "id": "6M1VSmwtcuwS1DnvXTGk7P",
            "name": "Ashwin Azer",
            "genres": ["indie"],
            "spotify_url": "https://open.spotify.com/artist/6M1VSmwtcuwS1DnvXTGk7P",
        },
        "discography": [_sample_spotify_release()],
    }


def test_normalize_source_data_structure():
    result = normalize_source_data(_sample_spotify_source_data())
    assert result["source"] == "spotify"
    assert result["artist"]["name"] == "Ashwin Azer"
    assert len(result["releases"]) == 1


# ---------------------------------------------------------------------------
# merge_sources
# ---------------------------------------------------------------------------


def _sample_apple_source_data() -> dict:
    return {
        "source": "apple_music",
        "artist": {
            "source_id": "1497428225",
            "name": "Ashwin Azer",
            "genres": ["Singer/Songwriter"],
            "url": "https://music.apple.com/in/artist/ashwin-azer/1497428225",
        },
        "releases": [
            {
                "source": "apple_music",
                "source_id": "apple_release_001",
                "title": "Moonrise EP",
                "type": "Single",
                "release_date": {"year": "2023", "month": "06", "day": "15"},
                "total_tracks": 1,
                "label": "Sony Music",
                "upc": "123456789012",
                "url": "https://music.apple.com/in/album/moonrise-ep/apple_release_001",
                "artwork_url": "https://example.com/apple_art.jpg",
                "tracks": [
                    {
                        "source": "apple_music",
                        "source_id": "apple_track_001",
                        "title": "Starlight",
                        "track_number": 1,
                        "disc_number": 1,
                        "duration_seconds": 210,
                        "isrc": "INXXX2300001",
                        "url": "https://music.apple.com/in/album/starlight/apple_release_001?i=apple_track_001",
                    }
                ],
            }
        ],
    }


def test_merge_sources_deduplicates():
    spotify = normalize_source_data(_sample_spotify_source_data())
    apple = _sample_apple_source_data()
    merged = merge_sources(spotify, apple)
    # Should only have 1 release (deduplicated by title+type)
    assert len(merged["releases"]) == 1


def test_merge_sources_prefers_apple_label():
    spotify = normalize_source_data(_sample_spotify_source_data())
    # Remove label from Spotify data
    spotify["releases"][0]["label"] = None
    apple = _sample_apple_source_data()
    merged = merge_sources(spotify, apple)
    assert merged["releases"][0]["label"] == "Sony Music"


def test_merge_sources_artist_has_both_ids():
    spotify = normalize_source_data(_sample_spotify_source_data())
    apple = _sample_apple_source_data()
    merged = merge_sources(spotify, apple)
    assert merged["artist"]["spotify_id"] == "6M1VSmwtcuwS1DnvXTGk7P"
    assert merged["artist"]["apple_music_id"] == "1497428225"


def test_merge_sources_spotify_only_release():
    """A release present only in Spotify should still appear in the merged output."""
    spotify = normalize_source_data(_sample_spotify_source_data())
    # Apple data with no releases
    apple_data: dict = {
        "source": "apple_music",
        "artist": {"source_id": "1497428225", "name": "Ashwin Azer"},
        "releases": [],
    }
    merged = merge_sources(spotify, apple_data)
    assert len(merged["releases"]) == 1
    assert merged["releases"][0]["title"] == "Moonrise EP"
