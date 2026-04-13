# ashwin-azer-mb-sync

A Python CLI tool that ingests artist metadata from **Spotify** and **Apple Music** for the artist [Ashwin Azer](https://open.spotify.com/artist/6M1VSmwtcuwS1DnvXTGk7P), normalizes it to be compatible with the [MusicBrainz](https://musicbrainz.org) data model, and generates human-readable reports with pre-filled MusicBrainz edit-form links to assist with **manual** submissions.

> ⚠️ **MusicBrainz does not allow automated edits.** All generated links are for manual submission by a logged-in MusicBrainz editor.

---

## Features

- 🎵 **Spotify ingestion** — artist profile, full discography, track ISRCs via the [Spotify Web API](https://developer.spotify.com/documentation/web-api)
- 🍎 **Apple Music ingestion** — artist profile, albums, tracks, ISRCs via the [Apple Music API](https://developer.apple.com/documentation/applemusicapi)
- 🔀 **Metadata normalization** — unified schema compatible with the MusicBrainz data model; merged view from both sources
- 📄 **MusicBrainz reports** — JSON + Markdown with pre-filled `/release/add` edit URLs and missing-field warnings
- 🗂️ **Evidence packs** — structured JSON/Markdown citation bundles (source URLs, ISRC lookup links) to back up MusicBrainz edits
- ⚙️ **GitHub Actions** — optional scheduled workflow that runs the pipeline weekly and opens/updates a GitHub Issue with results

---

## Artist IDs

| Source | Artist | ID / URL |
|--------|--------|----------|
| Spotify | Ashwin Azer | [`6M1VSmwtcuwS1DnvXTGk7P`](https://open.spotify.com/artist/6M1VSmwtcuwS1DnvXTGk7P) |
| Apple Music | Ashwin Azer | [`1497428225`](https://music.apple.com/in/artist/ashwin-azer/1497428225) |

---

## Prerequisites

- Python 3.10 or later
- A **Spotify Developer** account — [Create an app](https://developer.spotify.com/dashboard)
- An **Apple Developer** account with a [MusicKit key](https://developer.apple.com/account/resources/authkeys/list) (`.p8` file)

---

## Quick Start

### 1. Clone the repository

```bash
git clone https://github.com/adhithyaraiml2022-arch/ashwin-azer-mb-sync.git
cd ashwin-azer-mb-sync
```

### 2. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment variables

```bash
cp .env.example .env
```

Open `.env` and fill in your credentials (see [Environment Variables](#environment-variables) below).

### 4. Run the tool

```bash
# Ingest from both Spotify and Apple Music, generate merged report
python -m src.main all

# Ingest from Spotify only
python -m src.main spotify

# Ingest from Apple Music only
python -m src.main apple

# Also generate an evidence pack
python -m src.main all --evidence
```

Reports are written to the `reports/` directory; evidence packs to `evidence_packs/`.

---

## Environment Variables

Copy `.env.example` to `.env` and fill in the values below.

| Variable | Required | Description |
|----------|----------|-------------|
| `SPOTIFY_CLIENT_ID` | ✅ for Spotify | Spotify app client ID |
| `SPOTIFY_CLIENT_SECRET` | ✅ for Spotify | Spotify app client secret |
| `APPLE_TEAM_ID` | ✅ for Apple | Apple Developer Team ID |
| `APPLE_KEY_ID` | ✅ for Apple | MusicKit key ID |
| `APPLE_PRIVATE_KEY_PATH` | ✅ for Apple | Path to the `.p8` private key file |
| `SPOTIFY_ARTIST_ID` | ❌ | Spotify artist ID (default: `6M1VSmwtcuwS1DnvXTGk7P`) |
| `APPLE_MUSIC_ARTIST_ID` | ❌ | Apple Music artist ID (default: `1497428225`) |
| `APPLE_MUSIC_STOREFRONT` | ❌ | Apple Music country code (default: `in`) |
| `ARTIST_MBID` | ❌ | MusicBrainz MBID for the artist if already known |
| `REPORTS_DIR` | ❌ | Output directory for reports (default: `reports`) |
| `EVIDENCE_DIR` | ❌ | Output directory for evidence packs (default: `evidence_packs`) |

### Obtaining Spotify credentials

1. Go to <https://developer.spotify.com/dashboard> and sign in.
2. Click **Create app** and fill in the name and redirect URI (any valid URL).
3. Copy the **Client ID** and **Client Secret** into your `.env`.

### Obtaining Apple Music (MusicKit) credentials

1. Sign in to <https://developer.apple.com/account>.
2. Navigate to **Certificates, Identifiers & Profiles → Keys**.
3. Click **+** to create a new key, enable **MusicKit**, and download the `.p8` file.
4. Note your **Team ID** (top right of the Apple Developer portal) and the **Key ID** shown after creation.
5. Set `APPLE_PRIVATE_KEY_PATH` to the full path of the downloaded `.p8` file.

---

## Output Files

### `reports/mb_report_<timestamp>.json`

Machine-readable JSON with:
- Artist metadata from both sources
- All release candidates with normalized fields
- Pre-filled MusicBrainz `/release/add` URLs
- Missing-field warnings per release
- Full track listings with ISRCs

### `reports/mb_report_<timestamp>.md`

Human-readable Markdown summary suitable for posting in GitHub Issues or MusicBrainz edit notes.

### `evidence_packs/evidence_pack_<timestamp>.json` / `.md`

Structured citation bundles containing:
- Source URLs (Spotify, Apple Music) for each release
- ISRC lookup links (IFPI, MusicBrainz) for each track

---

## GitHub Actions Workflow

The workflow at `.github/workflows/sync.yml` runs automatically every **Monday at 02:00 UTC** (or on demand via `workflow_dispatch`).

### Required GitHub Secrets

Add the following secrets in **Settings → Secrets and variables → Actions**:

| Secret | Description |
|--------|-------------|
| `SPOTIFY_CLIENT_ID` | Spotify app client ID |
| `SPOTIFY_CLIENT_SECRET` | Spotify app client secret |
| `APPLE_TEAM_ID` | Apple Developer Team ID |
| `APPLE_KEY_ID` | MusicKit key ID |
| `APPLE_PRIVATE_KEY` | Contents of the `.p8` private key file (paste the full text) |

The workflow will:
1. Run the full ingestion and normalization pipeline.
2. Upload reports and evidence packs as workflow artifacts (retained for 30 days).
3. Open (or update) a GitHub Issue labelled `mb-sync` with the Markdown report.

---

## Project Structure

```
ashwin-azer-mb-sync/
├── .env.example                 # Template for environment variables
├── .gitignore
├── requirements.txt
├── README.md
├── src/
│   ├── __init__.py
│   ├── main.py                  # CLI entry point
│   ├── spotify_ingest.py        # Spotify Web API ingestion
│   ├── apple_music_ingest.py    # Apple Music API ingestion
│   ├── normalize.py             # Metadata normalization & merging
│   ├── mb_report.py             # MusicBrainz report generation
│   └── evidence_pack.py         # Evidence pack generation
├── tests/
│   ├── __init__.py
│   └── test_normalize.py        # Unit tests for normalization logic
└── .github/
    └── workflows/
        └── sync.yml             # Scheduled GitHub Actions workflow
```

---

## Testing

```bash
pip install -r requirements.txt
pytest tests/ -v
```

The test suite covers all normalization and merge logic and does **not** require API credentials.

---

## Security Notes

- **Never commit your `.env` file** — it is listed in `.gitignore`.
- **Never share API keys or private key files** in issues, PRs, or chat.
- The tool makes only **read** requests to Spotify and Apple Music APIs.
- No credentials are sent to MusicBrainz; the generated edit URLs are for manual use by a logged-in editor.

---

## Contributing

- Open a draft pull request early for visibility and feedback.
- Run `pytest tests/ -v` before pushing.
- Keep commits small and reference related issues in commit messages.

---

## License

To be determined. Add a `LICENSE` file and update this section accordingly.
