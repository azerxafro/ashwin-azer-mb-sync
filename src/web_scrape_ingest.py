"""
web_scrape_ingest.py
~~~~~~~~~~~~~~~~~~~~
Scrape artist discography from publicly available web pages.
No API keys required.

Primary source: Last.fm
  - Artist info:  https://www.last.fm/music/<artist>
  - Album list:   https://www.last.fm/music/<artist>/+albums
  - Album tracks: https://www.last.fm/music/<artist>/<album>

Environment variables:
    ARTIST_NAME         – Artist name (default: "Ashwin Azer")
    LASTFM_ARTIST_URL   – Optional override for the Last.fm artist slug
                          (default: derived from ARTIST_NAME)
"""

from __future__ import annotations

import logging
import os
import re
import time
from typing import Any

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

ARTIST_NAME: str = os.getenv("ARTIST_NAME", "Ashwin Azer")
LASTFM_BASE: str = "https://www.last.fm"

# Rate-limit guard: pause between page requests (seconds)
try:
    _REQUEST_DELAY: float = float(os.getenv("SCRAPE_DELAY", "1.0"))
except ValueError:
    raise ValueError(
        "SCRAPE_DELAY must be a number (e.g. '1.0'). "
        "Check the SCRAPE_DELAY environment variable."
    ) from None

_SESSION: requests.Session | None = None


def _session() -> requests.Session:
    global _SESSION
    if _SESSION is None:
        _SESSION = requests.Session()
        _SESSION.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (compatible; ashwin-azer-mb-sync/1.0; "
                    "+https://github.com/adhithyaraiml2022-arch/ashwin-azer-mb-sync)"
                ),
                "Accept-Language": "en-US,en;q=0.9",
            }
        )
    return _SESSION


def _get(url: str, params: dict[str, Any] | None = None) -> BeautifulSoup:
    """Fetch a page and return a BeautifulSoup object."""
    logger.debug("GET %s", url)
    time.sleep(_REQUEST_DELAY)
    resp = _session().get(url, params=params, timeout=30)
    resp.raise_for_status()
    return BeautifulSoup(resp.text, "lxml")


def _lastfm_artist_slug(artist_name: str) -> str:
    """Convert an artist name to the Last.fm URL slug."""
    slug = os.getenv("LASTFM_ARTIST_URL", "")
    if slug:
        return slug
    # Last.fm uses '+' for spaces in artist slugs
    return artist_name.replace(" ", "+")


# ---------------------------------------------------------------------------
# Last.fm scraping helpers
# ---------------------------------------------------------------------------


def _scrape_artist_info(slug: str) -> dict[str, Any]:
    """Scrape artist profile (name, genres/tags, URL) from Last.fm."""
    url = f"{LASTFM_BASE}/music/{slug}"
    logger.info("Scraping artist info from %s", url)
    soup = _get(url)

    # Artist name from the page <h1>
    name_tag = soup.select_one("h1.header-new-title")
    name: str = name_tag.get_text(strip=True) if name_tag else ARTIST_NAME

    # Genre tags
    genre_tags = soup.select("a.tag")
    genres: list[str] = [t.get_text(strip=True) for t in genre_tags if t.get_text(strip=True)]

    return {
        "id": slug,
        "name": name,
        "genres": genres,
        "url": url,
    }


def _scrape_album_list(slug: str) -> list[dict[str, Any]]:
    """Scrape the list of albums from the Last.fm +albums page."""
    url = f"{LASTFM_BASE}/music/{slug}/+albums"
    logger.info("Scraping album list from %s", url)
    soup = _get(url)

    albums: list[dict[str, Any]] = []
    # Album cards appear in <li class="resource-list--release-list-item ...">
    for item in soup.select("li.resource-list--release-list-item"):
        title_tag = item.select_one("h3.resource-list--release-list-item-name a")
        if not title_tag:
            title_tag = item.select_one(".resource-list--release-list-item-name a")
        if not title_tag:
            continue

        title: str = title_tag.get_text(strip=True)
        href: str = title_tag.get("href", "")
        album_url: str = f"{LASTFM_BASE}{href}" if href.startswith("/") else href

        # Last.fm album slugs are the last segment of the path
        album_slug: str = href.rstrip("/").split("/")[-1]

        # Release date — sometimes shown on the card
        date_tag = item.select_one(".resource-list--release-list-item-date")
        raw_date: str | None = date_tag.get_text(strip=True) if date_tag else None

        # Album type (Last.fm labels some as "Single", "EP", etc.)
        type_tag = item.select_one(".resource-list--release-list-item-type")
        raw_type: str | None = type_tag.get_text(strip=True) if type_tag else None

        albums.append(
            {
                "slug": album_slug,
                "title": title,
                "url": album_url,
                "raw_date": raw_date,
                "raw_type": raw_type,
            }
        )

    return albums


def _parse_duration(duration_str: str | None) -> int | None:
    """
    Convert a duration string like "3:42" or "3m 42s" to milliseconds.
    Returns None if parsing fails.
    """
    if not duration_str:
        return None
    duration_str = duration_str.strip()
    # "M:SS" or "MM:SS"
    m = re.match(r"^(\d+):(\d{2})$", duration_str)
    if m:
        minutes, seconds = int(m.group(1)), int(m.group(2))
        return (minutes * 60 + seconds) * 1000
    # "Xm Ys"
    m = re.match(r"^(\d+)m\s*(\d+)s$", duration_str)
    if m:
        minutes, seconds = int(m.group(1)), int(m.group(2))
        return (minutes * 60 + seconds) * 1000
    return None


def _parse_release_year(raw_date: str | None) -> str | None:
    """Extract a 4-digit year from a raw date string."""
    if not raw_date:
        return None
    m = re.search(r"\b(\d{4})\b", raw_date)
    return m.group(1) if m else None


def _scrape_album_tracks(
    artist_slug: str,
    album_stub: dict[str, Any],
) -> dict[str, Any]:
    """Scrape a single album page and return a structured album dict."""
    album_url = album_stub["url"]
    logger.info("Scraping album tracks from %s", album_url)
    soup = _get(album_url)

    # Release date from the album page (more reliable than the list card)
    release_year: str | None = (
        _parse_release_year(album_stub["raw_date"]) if album_stub.get("raw_date") else None
    )
    if not release_year:
        date_tag = soup.select_one(".catalogue-metadata-description")
        if date_tag:
            release_year = _parse_release_year(date_tag.get_text())

    # Album type
    raw_type: str | None = album_stub.get("raw_type")

    # Track list — rows in <tbody class="chartlist">
    tracks: list[dict[str, Any]] = []
    for pos, row in enumerate(soup.select("tr.chartlist-row"), start=1):
        title_tag = row.select_one(".chartlist-name a") or row.select_one(
            ".chartlist-name span"
        )
        if not title_tag:
            continue
        title: str = title_tag.get_text(strip=True)

        duration_tag = row.select_one(".chartlist-duration")
        duration_str: str | None = (
            duration_tag.get_text(strip=True) if duration_tag else None
        )
        duration_ms: int | None = _parse_duration(duration_str)

        # Track number from the explicit rank cell, or use enumeration
        rank_tag = row.select_one(".chartlist-index")
        track_number: int = pos
        if rank_tag:
            raw_rank = rank_tag.get_text(strip=True)
            if raw_rank.isdigit():
                track_number = int(raw_rank)

        tracks.append(
            {
                "id": f"{album_stub['slug']}_{track_number}",
                "title": title,
                "track_number": track_number,
                "disc_number": 1,
                "duration_ms": duration_ms,
                "isrc": None,  # Not available from public scraping
                "url": album_url,
            }
        )

    return {
        "id": album_stub["slug"],
        "title": album_stub["title"],
        "type": raw_type,
        "release_date": release_year,
        "release_date_precision": "year" if release_year else None,
        "total_tracks": len(tracks) or None,
        "label": None,
        "upc": None,
        "url": album_url,
        "tracks": tracks,
    }


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def fetch_full_discography(artist_name: str = ARTIST_NAME) -> dict[str, Any]:
    """
    Scrape artist profile, all albums, and all tracks from Last.fm.
    Returns a structured dict compatible with normalize_source_data().
    """
    slug = _lastfm_artist_slug(artist_name)

    artist_info = _scrape_artist_info(slug)
    album_list = _scrape_album_list(slug)

    discography: list[dict[str, Any]] = []
    for album_stub in album_list:
        try:
            album = _scrape_album_tracks(slug, album_stub)
            discography.append(album)
        except requests.HTTPError as exc:
            logger.warning(
                "Skipping album %r — HTTP %s", album_stub["title"], exc.response.status_code
            )

    return {
        "source": "web_scrape",
        "artist": artist_info,
        "discography": discography,
    }
