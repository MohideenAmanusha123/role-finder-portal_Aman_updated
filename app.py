"""
app.py

Flask web portal for resume analysis, JD matching, custom roles, and resume generation.
"""

import os
import re
import tempfile

from flask import Flask, render_template, request, jsonify, send_file

from resume_builder import (
    normalize_resume_data,
    build_resume_text,
    calculate_builder_ats_score,
    generate_ats_pdf,
    generate_ats_docx,
)

from resume_matcher import (
    analyze_resume,
    analyze_text,
    extract_text,
    UnsupportedFileType,
    ScannedPDFError,
    find_skills,
)

from roles_data import (
    ROLES,
    SKILL_VOCABULARY,
    SKILL_APPLICATIONS,
    add_custom_role,
)

from pdf_report import build_pdf_report

from resume_editor import (
    build_edited_resume,
    render_edited_resume_pdf,
    render_edited_resume_docx,
)

app = Flask(__name__)

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}

app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024


def safe_base(filename):
    base = os.path.splitext(filename or "resume")[0]
    return re.sub(r"[^A-Za-z0-9_-]+", "_", base).strip("_") or "resume"


def improved_filename(filename, ext):
    return f"{safe_base(filename)}_improved_resume.{ext}"


def _parse_resume_for_builder(text):
    lines = [line.strip() for line in (text or "").splitlines() if line.strip()]
    joined = "\n".join(lines)
    email_match = re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", joined)
    phone_match = re.search(r"(?<!\d)(?:\+?\d[\d\s().-]{8,}\d)(?!\d)", joined)
    link_match = re.search(r"https?://(?:www\.)?(?:linkedin\.com|github\.com)/[^\s|]+", joined, re.I)

    heading_patterns = {
        "summary": re.compile(r"^(?:professional\s+)?summary|profile|objective$", re.I),
        "skills": re.compile(r"^(?:technical\s+)?skills|core\s+competencies|technologies$", re.I),
        "experience": re.compile(r"^(?:work\s+)?experience|employment\s+history|professional\s+experience$", re.I),
        "education": re.compile(r"^education|academic\s+background$", re.I),
        "projects": re.compile(r"^projects?$", re.I),
        "certifications": re.compile(r"^certifications?|licenses?$", re.I),
        "achievements": re.compile(r"^achievements?|awards?$", re.I),
        "languages": re.compile(r"^languages?$", re.I),
    }
    sections = {}
    current = None
    for line in lines:
        matched = next((name for name, pattern in heading_patterns.items() if pattern.match(line)), None)
        if matched:
            current = matched
            sections.setdefault(current, [])
        elif current:
            sections[current].append(line)

    contact_line = next((line for line in lines if email_match and email_match.group(0) in line), "")
    name = next((line for line in lines if line != contact_line and not re.search(r"@|https?://|\+?\d[\d\s().-]{8,}\d", line)), "")
    skill_text = " ".join(sections.get("skills", []))
    skills = sorted(find_skills(skill_text, SKILL_VOCABULARY))
    for raw_skill in re.split(r"[,|;/•·]", skill_text):
        raw_skill = raw_skill.strip()
        if raw_skill and raw_skill.lower() not in {skill.lower() for skill in skills}:
            skills.append(raw_skill)

    summary = " ".join(sections.get("summary", []))
    experience_lines = sections.get("experience", [])
    education_lines = sections.get("education", [])
    project_lines = sections.get("projects", [])
    certifications = sections.get("certifications", [])
    achievements = sections.get("achievements", [])
    languages = [item.strip() for item in re.split(r"[,|;/]", " ".join(sections.get("languages", []))) if item.strip()]

    return normalize_resume_data({
        "personal": {
            "name": name,
            "email": email_match.group(0) if email_match else "",
            "phone": phone_match.group(0).strip() if phone_match else "",
            "linkedin": link_match.group(0) if link_match else "",
        },
        "summary": summary,
        "skills": skills,
        "experience": [{
            "job_title": experience_lines[0] if experience_lines else "",
            "description": "\n".join(experience_lines[1:]),
        }] if experience_lines else [],
        "education": [{
            "degree": education_lines[0] if education_lines else "",
            "institution": education_lines[1] if len(education_lines) > 1 else "",
            "description": "\n".join(education_lines[2:]),
        }] if education_lines else [],
        "projects": [{
            "name": project_lines[0] if project_lines else "",
            "description": "\n".join(project_lines[1:]),
        }] if project_lines else [],
        "certifications": certifications,
        "achievements": achievements,
        "languages": languages,
    })


@app.route("/import-resume", methods=["POST"])
def import_resume():
    if "resume" not in request.files:
        return jsonify({"success": False, "error": "Please select an existing resume file."}), 400
    file = request.files["resume"]
    if not file.filename:
        return jsonify({"success": False, "error": "Please select an existing resume file."}), 400
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return jsonify({"success": False, "error": "Please upload a .pdf, .docx, or .txt file."}), 400

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            file.save(tmp.name)
            tmp_path = tmp.name
        text = extract_text(tmp_path)
        return jsonify({"success": True, "resume": _parse_resume_for_builder(text), "filename": file.filename})
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

            file_stream = generate_ats_pdf(
                resume_data
            )

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
        data.get("summary_mode", "update"),
        data.get("role_name"),
        data.get("experience_signal"),
    )


@app.route("/preview-resume", methods=["POST"])
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
