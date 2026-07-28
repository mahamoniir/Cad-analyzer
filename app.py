from __future__ import annotations

import json
import os
import uuid
from pathlib import Path

from flask import (
    Flask,
    flash,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
)
from werkzeug.utils import secure_filename

from cad_analyzer import CADAnalysisError, analyze_dwg_file

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "output"

UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

ALLOWED_EXTENSIONS = {"dwg"}
MAX_CONTENT_LENGTH = 100 * 1024 * 1024  # 100 MB upload cap

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH
app.secret_key = os.environ.get("SECRET_KEY", "sc-dwg-analyzer-dev-key")


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")


@app.route("/analyze", methods=["POST"])
def analyze():
    if "dwg_file" not in request.files:
        flash("No file was submitted.")
        return redirect(url_for("index"))

    uploaded_file = request.files["dwg_file"]

    if uploaded_file.filename == "":
        flash("No file was selected.")
        return redirect(url_for("index"))

    if not allowed_file(uploaded_file.filename):
        flash("Only .dwg files are accepted.")
        return redirect(url_for("index"))

    # Store the upload under a unique job id so concurrent uploads never collide
    job_id = uuid.uuid4().hex[:12]
    original_name = secure_filename(uploaded_file.filename)
    saved_path = UPLOAD_DIR / f"{job_id}-{original_name}"
    uploaded_file.save(saved_path)

    try:
        report, summary = analyze_dwg_file(saved_path)
    except CADAnalysisError as error:
        flash(str(error))
        return redirect(url_for("index"))

    # Persist results so they can be downloaded afterwards
    json_path = OUTPUT_DIR / f"{job_id}.json"
    summary_path = OUTPUT_DIR / f"{job_id}.txt"

    with open(json_path, "w", encoding="utf-8") as file:
        json.dump(report, file, indent=2, ensure_ascii=False)

    with open(summary_path, "w", encoding="utf-8") as file:
        file.write(summary)

    modelspace = report.get("modelspace", {})
    file_info = report.get("file_information", {})

    return render_template(
        "result.html",
        job_id=job_id,
        original_name=original_name,
        dxf_version=file_info.get("dxf_version"),
        acad_release=file_info.get("acad_release"),
        entity_count=modelspace.get("entity_count", 0),
        entity_counts=modelspace.get("entity_counts", {}),
        layer_count=report.get("tables", {}).get("layers", {}).get("count", 0),
        block_count=report.get("blocks", {}).get("count", 0),
        insert_count=report.get("block_references", {}).get("total_insert_entities", 0),
        summary=summary,
    )


@app.route("/download/<job_id>/<file_type>")
def download(job_id: str, file_type: str):
    if file_type == "json":
        filename = f"{job_id}.json"
    elif file_type == "summary":
        filename = f"{job_id}.txt"
    else:
        return "Unknown file type", 404

    return send_from_directory(OUTPUT_DIR, filename, as_attachment=True)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)