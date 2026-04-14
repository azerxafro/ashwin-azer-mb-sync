"""
webapp.py
~~~~~~~~~
Flask web application — frontend UI for the Ashwin Azer MusicBrainz sync tool.

Usage:
    python -m src.webapp               # development server on http://localhost:5000
    flask --app src.webapp run         # alternative

Environment variables (same as the CLI):
    ARTIST_NAME, LASTFM_ARTIST_URL, SCRAPE_DELAY, ARTIST_MBID,
    REPORTS_DIR, EVIDENCE_DIR
"""

from __future__ import annotations

import json
import logging
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv()

from flask import Flask, abort, jsonify, redirect, render_template, request, url_for  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)

REPORTS_DIR = Path(os.getenv("REPORTS_DIR", "reports"))
EVIDENCE_DIR = Path(os.getenv("EVIDENCE_DIR", "evidence_packs"))

app = Flask(__name__, template_folder="templates")

# ---------------------------------------------------------------------------
# Background job state
# ---------------------------------------------------------------------------

_job_lock = threading.Lock()
_job_state: dict[str, Any] = {
    "running": False,
    "last_status": None,  # "ok" | "error"
    "last_message": "",
    "last_finished_at": None,
}


def _background_scrape(generate_evidence: bool) -> None:
    """Run the full scrape + report pipeline in a background thread."""
    global _job_state
    try:
        from src.normalize import normalize_source_data
        from src.mb_report import build_report, write_json_report, write_markdown_report
        from src.evidence_pack import build_evidence_pack, write_evidence_pack, write_evidence_markdown
        from src.web_scrape_ingest import fetch_full_discography

        logger.info("Background scrape started (evidence=%s)", generate_evidence)
        raw = fetch_full_discography()
        merged = normalize_source_data(raw)
        report = build_report(merged)
        write_json_report(report, REPORTS_DIR)
        write_markdown_report(report, REPORTS_DIR)
        if generate_evidence:
            pack = build_evidence_pack(report)
            write_evidence_pack(pack, EVIDENCE_DIR)
            write_evidence_markdown(pack, EVIDENCE_DIR)

        with _job_lock:
            _job_state["last_status"] = "ok"
            _job_state["last_message"] = "Scrape completed successfully."
            _job_state["last_finished_at"] = datetime.now(timezone.utc).isoformat()
        logger.info("Background scrape finished OK")
    except Exception as exc:  # noqa: BLE001
        logger.error("Background scrape failed: %s", exc, exc_info=True)
        with _job_lock:
            _job_state["last_status"] = "error"
            _job_state["last_message"] = str(exc)
            _job_state["last_finished_at"] = datetime.now(timezone.utc).isoformat()
    finally:
        with _job_lock:
            _job_state["running"] = False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _list_reports() -> list[dict[str, Any]]:
    """Return metadata for all JSON reports, newest first."""
    if not REPORTS_DIR.exists():
        return []
    reports = []
    for p in sorted(REPORTS_DIR.glob("mb_report_*.json"), reverse=True):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            reports.append(
                {
                    "filename": p.name,
                    "generated_at": data.get("generated_at", ""),
                    "artist_name": data.get("artist", {}).get("name", "Unknown"),
                    "release_count": len(data.get("release_candidates", [])),
                }
            )
        except Exception:  # noqa: BLE001
            pass
    return reports


def _load_report(filename: str) -> dict[str, Any]:
    """Load and return a report dict by filename, or raise 404."""
    reports_dir = REPORTS_DIR.resolve()
    path = (reports_dir / filename).resolve()
    # Ensure the resolved path is strictly inside REPORTS_DIR (prevent traversal)
    if not path.is_relative_to(reports_dir) or not path.is_file():
        abort(404)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        abort(500)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.route("/")
def index() -> str:
    reports = _list_reports()
    with _job_lock:
        job = dict(_job_state)
    return render_template("index.html", reports=reports, job=job)


@app.route("/run", methods=["POST"])
def run_scrape():
    generate_evidence = request.form.get("evidence") == "1"
    with _job_lock:
        if _job_state["running"]:
            pass  # silently ignore duplicate starts
        else:
            _job_state["running"] = True
            _job_state["last_status"] = None
            _job_state["last_message"] = ""
            t = threading.Thread(
                target=_background_scrape,
                args=(generate_evidence,),
                daemon=True,
            )
            t.start()
    return redirect(url_for("index"))


@app.route("/report/<filename>")
def view_report(filename: str) -> str:
    report = _load_report(filename)
    return render_template("report.html", report=report, filename=filename)


@app.route("/status")
def status():
    """JSON endpoint for polling job status."""
    with _job_lock:
        return jsonify(dict(_job_state))


# ---------------------------------------------------------------------------
# Dev entry point
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    app.run(debug=False, host="127.0.0.1", port=5000)
