"""Entrypoint for Flask app autodetection.

For production deployments, run this app behind a WSGI server (for example:
`gunicorn app:app`) instead of Flask's built-in development server. On
container/cloud platforms, set `FLASK_HOST=0.0.0.0` so the service is reachable.
"""

import os

from src.webapp import app


if __name__ == "__main__":
    host = os.getenv("FLASK_HOST", "127.0.0.1")
    port = int(os.getenv("FLASK_PORT", "5000"))
    if host == "0.0.0.0":
        print("Warning: Flask development server is exposed on all interfaces; use a WSGI server in production.")
    app.run(debug=False, host=host, port=port)
