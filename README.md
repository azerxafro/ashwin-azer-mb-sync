# ashwin-azer-mb-sync

A Python CLI tool that scrapes artist metadata for [Ashwin Azer](https://www.last.fm/music/Ashwin+Azer) from **publicly available web sources** (Last.fm), normalizes it to be compatible with the [MusicBrainz](https://musicbrainz.org) data model, and generates human-readable reports with pre-filled MusicBrainz edit-form links to assist with **manual** submissions.

> ⚠️ **MusicBrainz does not allow automated edits.** All generated links are for manual submission by a logged-in MusicBrainz editor.

---

## Features

- 🌐 **No API keys required** — all data is scraped from publicly accessible web pages (Last.fm)
- 🔀 **Metadata normalization** — unified schema compatible with the MusicBrainz data model
- 📄 **MusicBrainz reports** — JSON + Markdown with pre-filled `/release/add` edit URLs and missing-field warnings
- 🗂️ **Evidence packs** — structured JSON/Markdown citation bundles (source URLs, ISRC lookup links) to back up MusicBrainz edits
- ⚙️ **GitHub Actions** — optional scheduled workflow that runs the pipeline weekly and opens/updates a GitHub Issue with results

---

## Artist

| Source | Artist | URL |
|--------|--------|-----|
| Last.fm | Ashwin Azer | [last.fm/music/Ashwin+Azer](https://www.last.fm/music/Ashwin+Azer) |

---

## Prerequisites

- Python 3.10 or later
- No API accounts or credentials needed

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

### 3. (Optional) Configure environment variables

```bash
cp .env.example .env
```

The defaults work out of the box for Ashwin Azer. Edit `.env` only if you want to change the artist or output directories.

### 4. Run the tool

```bash
# Scrape public sources and generate report
python -m src.main web

# Also generate an evidence pack
python -m src.main web --evidence
```

Reports are written to the `reports/` directory; evidence packs to `evidence_packs/`.

---

## Environment Variables

Copy `.env.example` to `.env` and optionally override the values below.

| Variable | Required | Description |
|----------|----------|-------------|
| `ARTIST_NAME` | ❌ | Artist name to look up (default: `Ashwin Azer`) |
| `LASTFM_ARTIST_URL` | ❌ | Override the Last.fm URL slug if auto-detection fails |
| `SCRAPE_DELAY` | ❌ | Seconds to pause between page requests (default: `1.0`) |
| `ARTIST_MBID` | ❌ | MusicBrainz MBID for the artist if already known |
| `REPORTS_DIR` | ❌ | Output directory for reports (default: `reports`) |
| `EVIDENCE_DIR` | ❌ | Output directory for evidence packs (default: `evidence_packs`) |

---

## Output Files

### `reports/mb_report_<timestamp>.json`

Machine-readable JSON with:
- Artist metadata from Last.fm
- All release candidates with normalized fields
- Pre-filled MusicBrainz `/release/add` URLs
- Missing-field warnings per release
- Full track listings

### `reports/mb_report_<timestamp>.md`

Human-readable Markdown summary suitable for posting in GitHub Issues or MusicBrainz edit notes.

### `evidence_packs/evidence_pack_<timestamp>.json` / `.md`

Structured citation bundles containing:
- Source URLs (Last.fm) for each release
- ISRC lookup links (IFPI, MusicBrainz) for each track where ISRCs are available

---

## GitHub Actions Workflow

The workflow at `.github/workflows/sync.yml` runs automatically every **Monday at 02:00 UTC** (or on demand via `workflow_dispatch`).

No secrets are required. The workflow will:
1. Run the full scraping and normalization pipeline.
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
│   ├── web_scrape_ingest.py     # Last.fm web scraping (no API keys)
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

The test suite covers all normalization and merge logic and does **not** require any credentials.

---

## Security Notes

- **Never commit your `.env` file** — it is listed in `.gitignore`.
- The tool makes only **read** requests to public web pages.
- No credentials are sent to MusicBrainz; the generated edit URLs are for manual use by a logged-in editor.

---

## Contributing

- Open a draft pull request early for visibility and feedback.
- Run `pytest tests/ -v` before pushing.
- Keep commits small and reference related issues in commit messages.

---

## License

To be determined. Add a `LICENSE` file and update this section accordingly.

