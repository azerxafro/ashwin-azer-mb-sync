"""Entrypoint for Flask app autodetection.

For production deployments, run this app behind a WSGI server (for example:
`gunicorn app:app`) instead of Flask's built-in development server.
"""

import os

from src.webapp import app


if __name__ == "__main__":
    host = os.getenv("FLASK_HOST", "127.0.0.1")
    port = int(os.getenv("FLASK_PORT", "5000"))
    app.run(debug=False, host=host, port=port)
