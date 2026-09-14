"""
app.py
Flask web portal for resume analysis, JD matching, custom roles, and resume generation.
"""
import os
import re
import tempfile

from flask import Flask, render_template, request, jsonify, send_file
from resume_matcher import analyze_resume, analyze_text, UnsupportedFileType, ScannedPDFError, find_skills
from roles_data import ROLES, SKILL_VOCABULARY, SKILL_APPLICATIONS, add_custom_role
from pdf_report import build_pdf_report
from resume_editor import build_edited_resume, render_edited_resume_pdf, render_edited_resume_docx

app = Flask(__name__)
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024


def safe_base(filename):
    base = os.path.splitext(filename or "resume")[0]
    return re.sub(r"[^A-Za-z0-9_-]+", "_", base).strip("_") or "resume"


def improved_filename(filename, ext):
    return f"{safe_base(filename)}_improved_resume.{ext}"


@app.route("/")
def index():
    return render_template("index.html", roles=list(ROLES.keys()), applications=SKILL_APPLICATIONS)


def _analyze_uploaded(file, target_role, job_description=""):
    if file is None or not file.filename:
        raise ValueError("Please select a resume file.")
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError("Please upload a .pdf, .docx, or .txt file.")

    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
        file.save(tmp.name)
        tmp_path = tmp.name
    try:
        result = analyze_resume(tmp_path, target_role=target_role, job_description=job_description)
        result["filename"] = file.filename
        return result
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass


@app.route("/analyze", methods=["POST"])
def analyze():
    if "resume" not in request.files:
        return jsonify({"error": "No file was uploaded."}), 400
    target_role = request.form.get("target_role", "").strip() or None
    if target_role not in ROLES:
        target_role = None
    jd = request.form.get("job_description", "").strip()
    try:
        return jsonify(_analyze_uploaded(request.files["resume"], target_role, jd))
    except ScannedPDFError as e:
        return jsonify({"error": str(e)}), 400
    except (UnsupportedFileType, ValueError) as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"Could not process this file: {e}"}), 500


@app.route("/analyze-text", methods=["POST"])
def analyze_text_route():
    data = request.get_json(silent=True) or {}
    resume_text = (data.get("resume_text") or "").strip()
    jd = (data.get("job_description") or "").strip()
    target_role = (data.get("target_role") or "").strip() or None
    if not resume_text:
        return jsonify({"error": "Resume text is missing."}), 400
    if target_role not in ROLES:
        target_role = None
    try:
        result = analyze_text(resume_text, target_role=target_role, job_description=jd)
        result["filename"] = data.get("filename", "pasted_resume.txt")
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": f"Could not analyze the text: {e}"}), 500


@app.route("/custom-role", methods=["POST"])
def custom_role():
    data = request.get_json(silent=True) or {}
    name = (data.get("role_name") or "").strip()
    jd = (data.get("job_description") or "").strip()
    if not name or not jd:
        return jsonify({"error": "Provide both a role name and job description."}), 400
    skills = sorted(find_skills(jd, SKILL_VOCABULARY))
    try:
        result = add_custom_role(name, jd, skills)
        return jsonify(result)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"Could not save the custom role: {e}"}), 500


@app.route("/download-report", methods=["POST"])
def download_report():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "No analysis data was provided."}), 400
    try:
        pdf_buffer = build_pdf_report(data)
    except Exception as e:
        return jsonify({"error": f"Could not build the PDF: {e}"}), 500
    safe_name = safe_base(data.get("filename", "resume"))
    return send_file(pdf_buffer, mimetype="application/pdf", as_attachment=True,
                     download_name=f"role_finder_report_{safe_name}.pdf")


def _build_edited(data):
    original_text = (data.get("resume_text") or "").strip()
    if not original_text:
        raise ValueError("Original resume text is missing — please re-upload and try again.")
    return build_edited_resume(
        original_text,
        data.get("matched_skills", []),
        data.get("confirmed_skills", []),
        data.get("applications", {}),
    )


@app.route("/preview-resume", methods=["POST"])
def preview_resume():
    data = request.get_json(silent=True) or {}
    try:
        edited = _build_edited(data)
        return jsonify({"diff": edited["diff"], "changes": edited["changes"]})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"Could not build the preview: {e}"}), 500


@app.route("/generate-resume", methods=["POST"])
def generate_resume():
    data = request.get_json(silent=True) or {}
    fmt = data.get("format", "pdf")
    if fmt not in {"pdf", "docx"}:
        return jsonify({"error": "Format must be pdf or docx."}), 400
    try:
        edited = _build_edited(data)
        if fmt == "docx":
            buf, mimetype, ext = (
                render_edited_resume_docx(edited),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "docx",
            )
        else:
            buf, mimetype, ext = render_edited_resume_pdf(edited), "application/pdf", "pdf"
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"Could not build the resume: {e}"}), 500

    return send_file(buf, mimetype=mimetype, as_attachment=True,
                     download_name=improved_filename(data.get("filename", "resume"), ext))


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "0").lower() in {"1", "true", "yes", "on"}
    app.run(host="0.0.0.0", port=port, debug=debug)
