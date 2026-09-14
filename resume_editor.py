"""
resume_editor.py
----------------
Conservatively edits a resume's Skills and Summary sections using only
skills/applications the user confirms. Supports a structured preview/diff.
"""

import io
import re
from html import escape

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable, ListFlowable, ListItem
from docx import Document
from docx.shared import Pt, RGBColor

from roles_data import SKILL_APPLICATIONS

INK = colors.HexColor("#20201C")
INK_SOFT = colors.HexColor("#65605A")
GOLD = colors.HexColor("#8A6D1F")
HAIRLINE = colors.HexColor("#D8D2C2")

BULLET_RE = re.compile(r"^\s*[-•*\u2022\u25CF\u2013]\s+")
SECTION_HEADER_PATTERN = re.compile(
    r"^\s*(summary|objective|profile|experience|work experience|professional experience|"
    r"education|skills|technical skills|projects|certifications|achievements)\s*:?\s*$",
    re.IGNORECASE,
)
HEADER_MAP = {
    "summary": "Summary", "objective": "Summary", "profile": "Summary",
    "experience": "Experience", "work experience": "Experience",
    "professional experience": "Experience", "education": "Education",
    "skills": "Skills", "technical skills": "Skills", "projects": "Projects",
    "certifications": "Certifications", "achievements": "Achievements",
}
ACRONYM_MAP = {
    "sql": "SQL", "aws": "AWS", "gcp": "GCP", "api": "API", "rest api": "REST API",
    "qa": "QA", "ui": "UI", "ux": "UX", "ci/cd": "CI/CD", "html": "HTML", "css": "CSS",
    "sql server": "SQL Server", "node.js": "Node.js", "power bi": "Power BI",
}


def format_skill_label(skill: str) -> str:
    return ACRONYM_MAP.get(skill.lower(), skill.title())


def _split_sections(text: str):
    lines, preamble, sections = text.splitlines(), [], []
    current_header, current_lines, started = None, [], False
    for raw_line in lines:
        stripped = raw_line.strip()
        m = SECTION_HEADER_PATTERN.match(stripped) if stripped else None
        if m:
            if not started:
                preamble = current_lines
            else:
                sections.append((current_header, current_lines))
            current_header = HEADER_MAP.get(m.group(1).lower(), m.group(1).title())
            current_lines, started = [], True
        else:
            current_lines.append(raw_line)
    if started:
        sections.append((current_header, current_lines))
    else:
        preamble = current_lines
    return preamble, sections


def _section_text(sections, header):
    for h, lines in sections:
        if h == header:
            return " ".join(l.strip() for l in lines if l.strip())
    return ""


def rewrite_summary(original_summary: str, skills, applications) -> str:
    """Rewrite without claiming unverified experience or inventing projects."""
    labels = [format_skill_label(s) for s in skills]
    apps = [a for vals in (applications or {}).values() for a in vals if a]
    apps = list(dict.fromkeys(apps))
    if original_summary.strip():
        base = re.sub(r"\s+", " ", original_summary).strip()
        addition = f" Core skills include {', '.join(labels)}." if labels else ""
        if apps:
            addition += f" Confirmed applications/tools include {', '.join(apps)}."
        return (base + addition).strip()
    if not labels:
        return ""
    text = f"Professional with skills in {', '.join(labels)}."
    if apps:
        text += f" Confirmed applications/tools include {', '.join(apps)}."
    return text


def build_edited_resume(original_text: str, matched_skills, confirmed_skills, applications=None) -> dict:
    preamble, sections = _split_sections(original_text)
    changes = []
    applications = applications or {}
    all_skills = sorted(set(matched_skills or []) | set(confirmed_skills or []))
    skills_line = ", ".join(format_skill_label(s) for s in all_skills) if all_skills else ""

    skills_idx = next((i for i, (h, _) in enumerate(sections) if h == "Skills"), None)
    if skills_idx is not None:
        sections[skills_idx] = ("Skills", [skills_line] if skills_line else sections[skills_idx][1])
        changes.append("Updated the Skills section with matched and user-confirmed skills.")
    elif skills_line:
        insert_at = next((i for i, (h, _) in enumerate(sections) if h == "Experience"), None)
        if insert_at is None:
            insert_at = next((i for i, (h, _) in enumerate(sections) if h == "Education"), None)
        sections.insert(insert_at if insert_at is not None else len(sections), ("Skills", [skills_line]))
        changes.append("Added a new Skills section.")

    if confirmed_skills:
        labels = ", ".join(format_skill_label(s) for s in sorted(confirmed_skills))
        changes.append(f"Included skills you confirmed you know: {labels}.")

    original_summary = _section_text(_split_sections(original_text)[1], "Summary")
    new_summary = rewrite_summary(original_summary, all_skills, applications)
    summary_idx = next((i for i, (h, _) in enumerate(sections) if h == "Summary"), None)
    if new_summary:
        if summary_idx is not None:
            sections[summary_idx] = ("Summary", [new_summary])
            changes.append("Rewrote the Summary to reflect the confirmed skills and applications.")
        else:
            insert_at = 0
            sections.insert(insert_at, ("Summary", [new_summary]))
            changes.append("Added a Summary based only on confirmed skills and applications.")

    diff = {
        "skills_added": [format_skill_label(s) for s in sorted(set(confirmed_skills or []))],
        "applications": applications,
        "summary_before": original_summary,
        "summary_after": new_summary,
        "changes": changes,
    }
    return {"preamble": preamble, "sections": sections, "changes": changes, "diff": diff}


def render_edited_resume_pdf(edited: dict) -> io.BytesIO:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter, leftMargin=.75*inch, rightMargin=.75*inch, topMargin=.7*inch, bottomMargin=.7*inch)
    styles = {
        "name": ParagraphStyle("name", fontName="Helvetica-Bold", fontSize=18, textColor=INK, leading=22, spaceAfter=6),
        "contact": ParagraphStyle("contact", fontName="Helvetica", fontSize=9.5, textColor=INK_SOFT, spaceAfter=1),
        "header": ParagraphStyle("header", fontName="Helvetica-Bold", fontSize=11.5, textColor=GOLD, spaceBefore=14, spaceAfter=3),
        "body": ParagraphStyle("body", fontName="Helvetica", fontSize=10, textColor=INK, leading=14, spaceAfter=3),
    }
    story = []
    preamble_lines = [l.strip() for l in edited["preamble"] if l.strip()]
    if preamble_lines:
        story.append(Paragraph(escape(preamble_lines[0]), styles["name"]))
        for l in preamble_lines[1:]:
            story.append(Paragraph(escape(l), styles["contact"]))
        story.append(Spacer(1, 10))
    for header, lines in edited["sections"]:
        content = [l.strip() for l in lines if l.strip()]
        if not content:
            continue
        story += [Paragraph(escape(header.upper()), styles["header"]), HRFlowable(width="100%", thickness=.75, color=HAIRLINE, spaceAfter=6)]
        bullets = []
        for l in content:
            if BULLET_RE.match(l):
                bullets.append(ListItem(Paragraph(escape(BULLET_RE.sub("", l)), styles["body"]), spaceAfter=3))
            else:
                if bullets:
                    story.append(ListFlowable(bullets, bulletType="bullet", start="-")); bullets = []
                story.append(Paragraph(escape(l), styles["body"]))
        if bullets:
            story.append(ListFlowable(bullets, bulletType="bullet", start="-"))
        story.append(Spacer(1, 6))
    doc.build(story); buf.seek(0); return buf


def render_edited_resume_docx(edited: dict) -> io.BytesIO:
    doc = Document()
    doc.styles["Normal"].font.name = "Calibri"
    doc.styles["Normal"].font.size = Pt(10.5)
    preamble_lines = [l.strip() for l in edited["preamble"] if l.strip()]
    if preamble_lines:
        p = doc.add_paragraph(); run = p.add_run(preamble_lines[0]); run.bold = True; run.font.size = Pt(18)
        for l in preamble_lines[1:]:
            doc.add_paragraph(l)
        doc.add_paragraph()
    gold = RGBColor(0x8A, 0x6D, 0x1F)
    for header, lines in edited["sections"]:
        content = [l.strip() for l in lines if l.strip()]
        if not content: continue
        h = doc.add_heading(level=2); r = h.add_run(header.upper()); r.font.color.rgb = gold; r.font.size = Pt(12)
        for l in content:
            doc.add_paragraph(BULLET_RE.sub("", l), style="List Bullet" if BULLET_RE.match(l) else None)
    buf = io.BytesIO(); doc.save(buf); buf.seek(0); return buf
