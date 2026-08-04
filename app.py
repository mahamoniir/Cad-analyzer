"""
Standalone Flask entrypoint for the CAD Analyzer web API.

This is a SEPARATE process from:
  - main.py            (the PySide6 desktop app)
  - the LuxScale calculation backend (app.py / ai_routes.py / ies_routes.py,
    documented in LuxSCale/back-end/*.md) — that's a different service
    entirely, reached over HTTP via luxscale_client.py at
    LUXSCALE_INTERNAL_BASE_URL (default http://127.0.0.1:5000)

Run:
    python cad_app.py

Then either:
  - open http://127.0.0.1:5001/ in a browser (serves cad_analyzer.html
    same-origin, so the API base field in the page can stay blank), or
  - open cad_analyzer.html directly and set its API base field to
    http://127.0.0.1:5001

Env vars:
  LUXSCALE_CAD_PORT              port to listen on (default 5001)
  LUXSCALE_INTERNAL_BASE_URL     where the LuxScale /cad_calc backend
                                  lives (default http://127.0.0.1:5000)
  LUXSCALE_CAD_ADMIN_TOKEN       shared secret for the one admin-only
                                  route, GET /api/cad/sessions. Unset =
                                  that route stays closed (fails safe).
  LUXSCALE_CAD_UPLOAD_DIR        where uploaded DWG/DXF files are staged
                                  per-session (default: system temp dir)
  LUXSCALE_CAD_SESSION_TTL_S     how long a parsed session stays in
                                  memory before eviction (default 2h)
  LUXSCALE_ODA_PATH              explicit path to ODAFileConverter.exe,
                                  if it's not in one of DWGReader's
                                  built-in search locations
"""

import os

from flask import Flask, render_template

from cad_routes import register_cad_routes

app = Flask(__name__)

register_cad_routes(app)


@app.route("/")
def index():
    """Serves templates/cad_analyzer.html same-origin, so the page's
    API base field can be left blank. render_template uses Flask's
    default template_folder ('templates/', relative to this file) —
    no extra config needed as long as cad_app.py and templates/ are
    siblings."""
    return render_template("cad_analyzer.html")


@app.route("/healthz")
def healthz():
    return {"status": "ok"}


if __name__ == "__main__":
    port = int(os.environ.get("LUXSCALE_CAD_PORT", 5001))
    app.run(host="127.0.0.1", port=port, debug=True)