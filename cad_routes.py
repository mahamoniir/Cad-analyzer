"""
CAD analysis blueprint — mounts /api/cad/*

Follows the same conventions as luxscale/ies_routes.py:
  - upload -> session_id, subsequent calls keyed by that session_id
  - in-memory session store with TTL eviction (same pattern as _ADMIN_TOKENS
    in app.py)
  - no persistence to disk beyond the uploaded source file itself

ASSUMPTIONS (flag/confirm against the real app.py / ies_routes.py before
wiring this in — I don't have those two files yet):
  - Blueprints are registered the way ai_routes.py is registered, i.e. a
    register_cad_routes(app) function called from app.py, OR a plain
    Blueprint object registered with app.register_blueprint(). Both are
    provided below — use whichever matches your existing pattern and
    delete the other.
  - Admin-gated endpoints (session listing) reuse whatever admin-check
    helper app.py exposes. Placeholder `_admin_ok()` below needs to be
    swapped for the real one (same sys.modules trick ai_routes.py uses,
    per the docs, to avoid the circular-import / duplicate-module bug).
  - /cad_calc is called over HTTP via LuxScaleClient.cad_calc()
    (root luxscale_client.py) with the room polygon vertices, rather
    than importing the calculation backend in-process.
"""

from __future__ import annotations

import os
import sys
import time
import uuid
import shutil
import tempfile
import threading
from pathlib import Path

from flask import Blueprint, request, jsonify
from werkzeug.utils import secure_filename

# DWGReader lives in cad_analyzer/dwg_reader.py
from cad_analyzer.dwg_reader import DWGReader

# Root-level client — NOT cad_analyzer/luxscale_client.py (stale duplicate,
# see prior discussion; delete that file once this is wired in).
from luxscale_client import LuxScaleClient


cad_bp = Blueprint("cad_bp", __name__, url_prefix="/api/cad")

# =========================================================
# CONFIG
# =========================================================

ALLOWED_EXTENSIONS = {".dwg", ".dxf"}

# Where uploaded source files are copied to before DWGReader touches them.
# Each session gets its own subdirectory, deleted on eviction.
UPLOAD_ROOT = Path(
    os.environ.get("LUXSCALE_CAD_UPLOAD_DIR", tempfile.gettempdir())
) / "luxscale_cad_sessions"

# How long an uploaded/parsed session stays in memory before being evicted.
SESSION_TTL_S = int(os.environ.get("LUXSCALE_CAD_SESSION_TTL_S", 60 * 60 * 2))  # 2h default

# Optional explicit path to ODAFileConverter.
# - Local (Windows): prefer a path that actually exists on this machine
#   (hardcoding a Windows path in env/code breaks Railway deploy).
# - Deploy (Linux/Docker): Dockerfile sets LUXSCALE_ODA_PATH to the
#   xvfb wrapper; that path exists in the container so it is used.
# If nothing resolves here, DWGReader.find_oda_converter() searches.
def _resolve_oda_path() -> str | None:
    env_path = os.environ.get("LUXSCALE_ODA_PATH")
    if env_path and Path(env_path).exists():
        return env_path

    # Local Windows installs — never force these on Linux deploy.
    if sys.platform == "win32":
        for candidate in (
            r"C:\Program Files\ODA\ODAFileConverter\ODAFileConverter.exe",
            r"C:\Program Files\ODA\ODAFileConverter 27.1.0\ODAFileConverter.exe",
            r"C:\Program Files (x86)\ODA\ODAFileConverter\ODAFileConverter.exe",
        ):
            if Path(candidate).exists():
                return candidate
        for base in (
            Path(r"C:\Program Files\ODA"),
            Path(r"C:\Program Files (x86)\ODA"),
        ):
            if not base.is_dir():
                continue
            for exe in base.glob("ODAFileConverter*/ODAFileConverter.exe"):
                return str(exe)

    # Linux deploy fallbacks (when LUXSCALE_ODA_PATH is unset/missing)
    if sys.platform.startswith("linux"):
        for candidate in (
            "/usr/local/bin/ODAFileConverter",
            "/usr/bin/ODAFileConverter",
        ):
            if Path(candidate).exists():
                return candidate

    return None


ODA_PATH = _resolve_oda_path()

# Base URL for LuxScale /cad_calc (and legacy /calculate).
# INTERNAL_API_BASE_URL = os.environ.get("LUXSCALE_INTERNAL_BASE_URL", "http://127.0.0.1:5000")
INTERNAL_API_BASE_URL = os.environ.get("LUXSCALE_INTERNAL_BASE_URL", "https://web-production-8d09d.up.railway.app/")

MAX_UPLOAD_BYTES = int(os.environ.get("LUXSCALE_CAD_MAX_UPLOAD_BYTES", 50 * 1024 * 1024))  # 50MB


# =========================================================
# SESSION STORE  (in-memory, mirrors _ADMIN_TOKENS pattern)
# =========================================================

_CAD_SESSIONS = {}
_CAD_SESSIONS_LOCK = threading.Lock()


def _purge_expired_sessions():
    now = time.time()
    expired = []

    with _CAD_SESSIONS_LOCK:
        for session_id, session in _CAD_SESSIONS.items():
            if now - session["created_at"] > SESSION_TTL_S:
                expired.append(session_id)
        for session_id in expired:
            _CAD_SESSIONS.pop(session_id, None)

    for session_id in expired:
        _cleanup_session_files(session_id)


def _cleanup_session_files(session_id):
    session_dir = UPLOAD_ROOT / session_id
    shutil.rmtree(session_dir, ignore_errors=True)


def _get_session_or_404(session_id):
    _purge_expired_sessions()
    with _CAD_SESSIONS_LOCK:
        session = _CAD_SESSIONS.get(session_id)
    return session


def _get_cached_rooms(session):
    """Room detection runs ONCE per session and is cached here. Every
    route (including calculate_room) reads from this instead of calling
    reader.detect_rooms() again, so a room id shown to the browser at
    upload time is guaranteed to still resolve later — detect_rooms()
    assigns ids by list position, so two independently-run detections
    aren't guaranteed to agree if anything upstream (candidate ordering,
    label matching) isn't perfectly deterministic."""
    if "rooms" not in session:
        reader = session["reader"]
        session["rooms"] = reader.detect_rooms()
        session["unmatched_labels"] = list(reader.unmatched_labels)
    return session["rooms"]


# =========================================================
# ADMIN CHECK PLACEHOLDER
# =========================================================

def _admin_ok():
    """This blueprint runs in its own standalone Flask process (see
    cad_app.py) — it does NOT share a process with the LuxScale backend
    at LUXSCALE_INTERNAL_BASE_URL, so there's no _ADMIN_TOKENS dict to
    reach into. Auth here is a simple shared secret instead: set
    LUXSCALE_CAD_ADMIN_TOKEN and pass it back as the X-Admin-Token
    header. If the env var is unset, the admin-only endpoint is closed
    entirely (fails safe) rather than silently open.
    """
    expected = os.environ.get("LUXSCALE_CAD_ADMIN_TOKEN")
    if not expected:
        return False

    provided = request.headers.get("X-Admin-Token")
    return bool(provided) and provided == expected


# =========================================================
# HELPERS
# =========================================================

def _new_session_dir(session_id):
    session_dir = UPLOAD_ROOT / session_id
    session_dir.mkdir(parents=True, exist_ok=True)
    return session_dir


def _room_by_id(rooms, room_id):
    for room in rooms:
        if str(room.get("id")) == str(room_id):
            return room
    return None


# =========================================================
# POST /api/cad/upload
# =========================================================

@cad_bp.route("/upload", methods=["POST"])
def upload_cad_file():
    if "file" not in request.files:
        return jsonify({"status": "error", "message": "No file part named 'file' in request."}), 400

    uploaded = request.files["file"]
    if not uploaded or not uploaded.filename:
        return jsonify({"status": "error", "message": "No file selected."}), 400

    filename = secure_filename(uploaded.filename)
    extension = Path(filename).suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:
        return jsonify({
            "status": "error",
            "message": f"Unsupported file type '{extension}'. Allowed: {sorted(ALLOWED_EXTENSIONS)}",
        }), 400

    session_id = uuid.uuid4().hex
    session_dir = _new_session_dir(session_id)
    saved_path = session_dir / filename

    uploaded.save(str(saved_path))

    if saved_path.stat().st_size > MAX_UPLOAD_BYTES:
        _cleanup_session_files(session_id)
        return jsonify({
            "status": "error",
            "message": f"File exceeds max upload size of {MAX_UPLOAD_BYTES} bytes.",
        }), 413

    try:
        reader = DWGReader(str(saved_path), oda_path=ODA_PATH)
        reader.load()
    except Exception as error:
        _cleanup_session_files(session_id)
        return jsonify({"status": "error", "message": str(error)}), 400

    with _CAD_SESSIONS_LOCK:
        _CAD_SESSIONS[session_id] = {
            "reader": reader,
            "created_at": time.time(),
            "original_filename": filename,
        }

    return jsonify({
        "status": "success",
        "session_id": session_id,
        "summary": reader.get_summary(),
    })


# =========================================================
# GET /api/cad/summary/<session_id>
# =========================================================

@cad_bp.route("/summary/<session_id>", methods=["GET"])
def get_summary(session_id):
    session = _get_session_or_404(session_id)
    if session is None:
        return jsonify({"status": "error", "message": "Unknown or expired session_id."}), 404

    return jsonify({"status": "success", "summary": session["reader"].get_summary()})


# =========================================================
# GET /api/cad/rooms/<session_id>
# =========================================================

@cad_bp.route("/rooms/<session_id>", methods=["GET"])
def get_rooms(session_id):
    session = _get_session_or_404(session_id)
    if session is None:
        return jsonify({"status": "error", "message": "Unknown or expired session_id."}), 404

    reader = session["reader"]
    rooms = _get_cached_rooms(session)

    return jsonify({
        "status": "success",
        "rooms": rooms,
        "unmatched_labels": [
            {"text": label["text"], "position": list(label["position"])}
            for label in session["unmatched_labels"]
        ],
    })


# =========================================================
# GET /api/cad/doors/<session_id>
# =========================================================

@cad_bp.route("/doors/<session_id>", methods=["GET"])
def get_doors(session_id):
    session = _get_session_or_404(session_id)
    if session is None:
        return jsonify({"status": "error", "message": "Unknown or expired session_id."}), 404

    return jsonify({"status": "success", "doors": session["reader"].detect_doors()})


# =========================================================
# GET /api/cad/draw-data/<session_id>
# =========================================================

@cad_bp.route("/draw-data/<session_id>", methods=["GET"])
def get_draw_data(session_id):
    session = _get_session_or_404(session_id)
    if session is None:
        return jsonify({"status": "error", "message": "Unknown or expired session_id."}), 404

    reader = session["reader"]
    rooms = _get_cached_rooms(session)

    entities = []
    for entity in reader.entities:
        data = reader.entity_to_draw_data(entity)
        if data:
            entities.append(data)

    draw_data = {
        "layers": reader.layers,
        "rooms": rooms,
        "doors": reader.detect_doors(),
        "entities": entities,
        "unmatched_labels": [
            {"text": label["text"], "position": list(label["position"])}
            for label in session["unmatched_labels"]
        ],
    }

    return jsonify({"status": "success", "draw_data": draw_data})


# =========================================================
# GET /api/cad/places   (legacy proxy — prefer standards picker)
# =========================================================

@cad_bp.route("/places", methods=["GET"])
def get_places_proxy():
    client = LuxScaleClient(INTERNAL_API_BASE_URL)

    try:
        data = client.get_places()
    except RuntimeError as error:
        return jsonify({"status": "error", "message": str(error)}), 502

    return jsonify(data)


# =========================================================
# Standards picker proxies (same-origin for the browser UI)
# =========================================================

@cad_bp.route("/standards/categories", methods=["GET"])
def standards_categories_proxy():
    client = LuxScaleClient(INTERNAL_API_BASE_URL)
    try:
        data = client.get_standards_categories()
    except RuntimeError as error:
        return jsonify({"status": "error", "message": str(error)}), 502
    return jsonify(data)


@cad_bp.route("/standards/categories/<path:category>/tasks", methods=["GET"])
def standards_tasks_proxy(category):
    client = LuxScaleClient(INTERNAL_API_BASE_URL)
    try:
        data = client.get_standards_tasks(category)
    except ValueError as error:
        return jsonify({"status": "error", "message": str(error)}), 400
    except RuntimeError as error:
        return jsonify({"status": "error", "message": str(error)}), 502
    return jsonify(data)


@cad_bp.route("/standards/detect", methods=["POST"])
def standards_detect_proxy():
    body = request.get_json(silent=True) or {}
    text = (body.get("text") or "").strip()
    limit = body.get("limit", 5)
    if not text:
        return jsonify({"status": "error", "message": "'text' is required."}), 400

    client = LuxScaleClient(INTERNAL_API_BASE_URL)
    try:
        data = client.detect_standards(text, limit=limit)
    except ValueError as error:
        return jsonify({"status": "error", "message": str(error)}), 400
    except RuntimeError as error:
        return jsonify({"status": "error", "message": str(error)}), 502
    return jsonify(data)


@cad_bp.route("/standards/resolve-by-task", methods=["POST"])
def standards_resolve_by_task_proxy():
    body = request.get_json(silent=True) or {}
    category = (body.get("category") or "").strip()
    task = (body.get("task_or_activity") or "").strip()
    if not category or not task:
        return jsonify({
            "status": "error",
            "message": "'category' and 'task_or_activity' are required.",
        }), 400

    client = LuxScaleClient(INTERNAL_API_BASE_URL)
    try:
        data = client.resolve_standard_by_task(
            category=category,
            task_or_activity=task,
            ref_no_hint=body.get("ref_no_hint"),
        )
    except RuntimeError as error:
        return jsonify({"status": "error", "message": str(error)}), 502
    return jsonify(data)


# =========================================================
# POST /api/cad/calculate/<session_id>/room/<room_id>
# =========================================================

@cad_bp.route("/calculate/<session_id>/room/<room_id>", methods=["POST"])
def calculate_room(session_id, room_id):
    session = _get_session_or_404(session_id)
    if session is None:
        return jsonify({"status": "error", "message": "Unknown or expired session_id."}), 404

    body = request.get_json(silent=True) or {}

    place = (body.get("place") or "").strip()
    height = body.get("height")
    standard_ref_no = (body.get("standard_ref_no") or "").strip() or None
    project_name = body.get("project_name", "CAD Lighting Analysis")
    fast = bool(body.get("fast", False))

    if height is None:
        return jsonify({"status": "error", "message": "'height' is required."}), 400

    if not standard_ref_no and not place:
        return jsonify({
            "status": "error",
            "message": "Select a standard task (standard_ref_no) or provide place.",
        }), 400

    rooms = _get_cached_rooms(session)
    room = _room_by_id(rooms, room_id)

    if room is None:
        return jsonify({"status": "error", "message": f"No room with id '{room_id}' in this session."}), 404

    vertices = room.get("points") or []
    if len(vertices) < 3:
        return jsonify({
            "status": "error",
            "message": "Room polygon must have at least 3 vertices.",
        }), 400

    client = LuxScaleClient(INTERNAL_API_BASE_URL)

    try:
        result = client.cad_calc(
            vertices=vertices,
            height=height,
            place=place,
            standard_ref_no=standard_ref_no,
            project_name=project_name,
            fast=fast,
        )
    except ValueError as error:
        return jsonify({"status": "error", "message": str(error)}), 400
    except RuntimeError as error:
        return jsonify({"status": "error", "message": str(error)}), 502

    return jsonify({"status": "success", "room": room, "result": result})


# =========================================================
# DELETE /api/cad/session/<session_id>   (explicit early cleanup)
# =========================================================

@cad_bp.route("/session/<session_id>", methods=["DELETE"])
def delete_session(session_id):
    with _CAD_SESSIONS_LOCK:
        existed = _CAD_SESSIONS.pop(session_id, None) is not None

    if existed:
        _cleanup_session_files(session_id)
        return jsonify({"status": "success", "deleted": True})

    return jsonify({"status": "error", "message": "Unknown session_id."}), 404


# =========================================================
# GET /api/cad/sessions   (admin — list active sessions)
# =========================================================

@cad_bp.route("/sessions", methods=["GET"])
def list_sessions():
    if not _admin_ok():
        return jsonify({"status": "error", "message": "Admin auth required."}), 401

    _purge_expired_sessions()
    with _CAD_SESSIONS_LOCK:
        sessions = [
            {
                "session_id": session_id,
                "original_filename": session["original_filename"],
                "created_at": session["created_at"],
                "age_seconds": round(time.time() - session["created_at"], 1),
            }
            for session_id, session in _CAD_SESSIONS.items()
        ]

    return jsonify({"status": "success", "sessions": sessions})


# =========================================================
# REGISTRATION HELPER  (mirrors register_ai_routes(app) pattern)
# =========================================================

def register_cad_routes(app):
    """Call from app.py the same way register_ai_routes(app) is called:

        from cad_routes import register_cad_routes
        register_cad_routes(app)

    If your codebase instead registers blueprints directly
    (app.register_blueprint(ies_bp) style), skip this function and use:

        from cad_routes import cad_bp
        app.register_blueprint(cad_bp)
    """
    UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
    app.register_blueprint(cad_bp)