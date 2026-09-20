"""
app.py

Flask web portal for resume analysis, JD matching, custom roles, and resume generation.
"""

import os
import re
import tempfile

from flask import Flask, render_template, request, jsonify, send_file, session

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from resume_builder import (
    normalize_resume_data,
    build_resume_text,
    calculate_builder_ats_score,
    generate_ats_pdf,
    generate_ats_docx,
)

from resume_matcher import (
    analyze_text,
    extract_text,
    UnsupportedFileType,
    ScannedPDFError,
    find_skills,
)

from roles_data import (
    SKILL_VOCABULARY,
    SKILL_APPLICATIONS,
    build_custom_role,
    merge_roles,
    MAX_CUSTOM_ROLES_PER_SESSION,
)

from pdf_report import build_pdf_report, build_interview_question_pdf

from resume_editor import (
    build_edited_resume,
    render_edited_resume_pdf,
    render_edited_resume_docx,
)

from resume_importer import parse_resume_for_builder

from file_safety import sniff_mismatch, run_with_timeout, ExtractionTimeout

app = Flask(__name__)

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}

app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024

# A stable SECRET_KEY is required so sessions (and the custom roles stored
# in them — see _session_roles() below) survive across requests/workers.
# Set SECRET_KEY in the environment for any real deployment; without it,
# every new process gets its own random key and existing sessions/cookies
# from other workers or a previous deploy silently stop decrypting, which
# just means "you lose your session's custom roles" rather than anything
# unsafe — but it's still worth setting explicitly.
app.secret_key = os.environ.get("SECRET_KEY") or os.urandom(32)

EXTRACTION_TIMEOUT_SECONDS = 15

# Rate limiting. `memory://` keeps counts in-process, which is fine for a
# single instance but is NOT shared across gunicorn workers or dynos — each
# worker enforces its own limit independently, so the *effective* ceiling is
# roughly (limit x worker count). That's still far better than no limiting
# at all, and it's a one-line swap to a shared backend later:
#   RATELIMIT_STORAGE_URI=redis://<host>:6379
limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"],
    storage_uri=os.environ.get("RATELIMIT_STORAGE_URI", "memory://"),
)


def _session_roles():
    """Base role catalog merged with THIS visitor's session-scoped custom
    roles. Never touches the global ROLES dict — see roles_data.merge_roles.
    """
    return merge_roles(session.get("custom_roles"))


def safe_base(filename):
    base = os.path.splitext(filename or "resume")[0]
    return re.sub(r"[^A-Za-z0-9_-]+", "_", base).strip("_") or "resume"


def improved_filename(filename, ext):
    return f"{safe_base(filename)}_improved_resume.{ext}"



@app.route("/import-resume", methods=["POST"])
@limiter.limit("15 per minute")
def import_resume():
    if "resume" not in request.files:
        return jsonify({"success": False, "error": "Please select an existing resume file."}), 400
    file = request.files["resume"]
    if not file.filename:
        return jsonify({"success": False, "error": "Please select an existing resume file."}), 400
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return jsonify({"success": False, "error": "Please upload a .pdf, .docx, or .txt file."}), 400
    if sniff_mismatch(file, ext):
        return jsonify({
            "success": False,
            "error": f"This file's contents don't look like a {ext} file. Please re-export it and try again.",
        }), 400

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            file.save(tmp.name)
            tmp_path = tmp.name
        text = run_with_timeout(extract_text, args=(tmp_path,), timeout=EXTRACTION_TIMEOUT_SECONDS)
        resume_data, parse_notes = parse_resume_for_builder(
            text, find_skills, SKILL_VOCABULARY, normalize_resume_data
        )
        return jsonify({
            "success": True,
            "resume": resume_data,
            "parse_notes": parse_notes,
            "filename": file.filename,
        })
    except ExtractionTimeout as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    except ScannedPDFError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    except (UnsupportedFileType, ValueError) as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"success": False, "error": f"Could not import this resume: {exc}"}), 500
    finally:
        if tmp_path:
            try:
                os.remove(tmp_path)
            except OSError:
                pass


@app.route("/ats-resume-builder", methods=["POST"])
@limiter.limit("15 per minute")
def ats_resume_builder():

    try:
        data = request.get_json(silent=True) or {}

        resume_data = normalize_resume_data(
            data.get("resume", data)
        )

        job_description = data.get(
            "job_description",
            ""
        )

        ats_result = calculate_builder_ats_score(
            resume_data,
            job_description
        )

        return jsonify({
            "success": True,
            "resume": resume_data,
            "resume_text": build_resume_text(
                resume_data
            ),
            "ats": ats_result,
        })

    except Exception as exc:

        return jsonify({
            "success": False,
            "error": str(exc),
        }), 400


@app.route("/preview-ats-resume", methods=["POST"])
def preview_ats_resume():

    try:

        data = request.get_json(silent=True) or {}

        resume_data = normalize_resume_data(
            data.get("resume", data)
        )

        job_description = data.get(
            "job_description",
            ""
        )

        ats_result = calculate_builder_ats_score(
            resume_data,
            job_description
        )

        return jsonify({
            "success": True,
            "resume_text": build_resume_text(
                resume_data
            ),
            "ats": ats_result,
        })

    except Exception as exc:

        return jsonify({
            "success": False,
            "error": str(exc),
        }), 400


@app.route("/download-ats-resume", methods=["POST"])
@limiter.limit("15 per minute")
def download_ats_resume():

    try:

        data = request.get_json(silent=True) or {}

        resume_data = normalize_resume_data(
            data.get("resume", data)
        )

        output_format = (
            data.get("format", "pdf")
            .lower()
        )

        name = (
            resume_data["personal"]["name"]
            or "ATS_Resume"
        )

        # Safe filename
        safe_name = re.sub(
            r"[^A-Za-z0-9_-]+",
            "_",
            name
        ).strip("_")

        if not safe_name:
            safe_name = "ATS_Resume"

        if output_format == "pdf":

            template = data.get("template", "classic")
            file_stream = generate_ats_pdf(resume_data, template=template)

            return send_file(
                file_stream,
                mimetype="application/pdf",
                as_attachment=True,
                download_name=(
                    f"{safe_name}_ATS_Resume.pdf"
                ),
            )

        if output_format == "docx":

            file_stream = generate_ats_docx(
                resume_data
            )

            return send_file(
                file_stream,
                mimetype=(
                    "application/vnd.openxmlformats-"
                    "officedocument.wordprocessingml.document"
                ),
                as_attachment=True,
                download_name=(
                    f"{safe_name}_ATS_Resume.docx"
                ),
            )

        return jsonify({
            "success": False,
            "error": "Unsupported format. Use PDF or DOCX.",
        }), 400

    except Exception as exc:

        return jsonify({
            "success": False,
            "error": str(exc),
        }), 500
@app.route("/")
def index():
    return render_template("index.html", roles=list(_session_roles().keys()), applications=SKILL_APPLICATIONS)


def _analyze_uploaded(file, target_role, job_description="", roles=None):
    if file is None or not file.filename:
        raise ValueError("Please select a resume file.")
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError("Please upload a .pdf, .docx, or .txt file.")
    if sniff_mismatch(file, ext):
        raise ValueError(f"This file's contents don't look like a {ext} file. Please re-export it and try again.")

    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
        file.save(tmp.name)
        tmp_path = tmp.name
    try:
        text = run_with_timeout(extract_text, args=(tmp_path,), timeout=EXTRACTION_TIMEOUT_SECONDS)
        result = analyze_text(text, target_role=target_role, job_description=job_description, roles=roles)
        result["filename"] = file.filename
        return result
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass


@app.route("/analyze", methods=["POST"])
@limiter.limit("15 per minute")
def analyze():
    if "resume" not in request.files:
        return jsonify({"error": "No file was uploaded."}), 400
    roles = _session_roles()
    target_role = request.form.get("target_role", "").strip() or None
    if target_role not in roles:
        target_role = None
    jd = request.form.get("job_description", "").strip()
    try:
        return jsonify(_analyze_uploaded(request.files["resume"], target_role, jd, roles=roles))
    except ExtractionTimeout as e:
        return jsonify({"error": str(e)}), 400
    except ScannedPDFError as e:
        return jsonify({"error": str(e)}), 400
    except (UnsupportedFileType, ValueError) as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"Could not process this file: {e}"}), 500


@app.route("/analyze-text", methods=["POST"])
@limiter.limit("15 per minute")
def analyze_text_route():
    data = request.get_json(silent=True) or {}
    resume_text = (data.get("resume_text") or "").strip()
    jd = (data.get("job_description") or "").strip()
    target_role = (data.get("target_role") or "").strip() or None
    if not resume_text:
        return jsonify({"error": "Resume text is missing."}), 400
    roles = _session_roles()
    if target_role not in roles:
        target_role = None
    try:
        result = analyze_text(resume_text, target_role=target_role, job_description=jd, roles=roles)
        result["filename"] = data.get("filename", "pasted_resume.txt")
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": f"Could not analyze the text: {e}"}), 500


@app.route("/custom-role", methods=["POST"])
@limiter.limit("10 per minute")
def custom_role():
    data = request.get_json(silent=True) or {}
    name = (data.get("role_name") or "").strip()
    jd = (data.get("job_description") or "").strip()
    if not name or not jd:
        return jsonify({"error": "Provide both a role name and job description."}), 400
    skills = sorted(find_skills(jd, SKILL_VOCABULARY))
    try:
        clean_name, info = build_custom_role(name, jd, skills)

        # Session-scoped, not global — see roles_data.merge_roles. Cap how
        # many custom roles one session can accumulate; evict the oldest
        # when the cap is hit rather than growing the cookie unbounded.
        custom_roles = session.get("custom_roles", {})
        custom_roles.pop(clean_name, None)  # re-adding replaces, doesn't duplicate
        if len(custom_roles) >= MAX_CUSTOM_ROLES_PER_SESSION:
            oldest = next(iter(custom_roles))
            custom_roles.pop(oldest)
        custom_roles[clean_name] = info
        session["custom_roles"] = custom_roles
        session.modified = True

        return jsonify({"role": clean_name, "skills": info["skills"], "description": info["description"]})
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


@app.route("/download-interview-questions", methods=["POST"])
def download_interview_questions():
    data = request.get_json(silent=True) or {}
    if not data:
        return jsonify({"error": "No interview data was provided."}), 400
    try:
        pdf_buffer = build_interview_question_pdf(data)
    except Exception as e:
        return jsonify({"error": f"Could not build the interview PDF: {e}"}), 500
    safe_name = safe_base(data.get("filename", "resume"))
    return send_file(
        pdf_buffer,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"interview_question_pack_{safe_name}.pdf",
    )


def _build_edited(data):
    original_text = (data.get("resume_text") or "").strip()
    if not original_text:
        raise ValueError("Original resume text is missing — please re-upload and try again.")
    return build_edited_resume(
        original_text,
        data.get("matched_skills", []),
        data.get("confirmed_skills", []),
        data.get("applications", {}),
        data.get("summary_mode", "update"),
        data.get("role_name"),
        data.get("experience_signal"),
    )


@app.route("/preview-resume", methods=["POST"])
@limiter.limit("8 per minute")  # tighter: this can trigger a paid AI summary call
def preview_resume():
    data = request.get_json(silent=True) or {}
    try:
        edited = _build_edited(data)
        return jsonify({
            "diff": edited["diff"],
            "changes": edited["changes"],
            "resume": {"preamble": edited["preamble"], "sections": edited["sections"]},
        })
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"Could not build the preview: {e}"}), 500


@app.route("/generate-resume", methods=["POST"])
@limiter.limit("8 per minute")  # tighter: this can trigger a paid AI summary call
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
