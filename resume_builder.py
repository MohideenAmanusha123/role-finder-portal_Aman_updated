"""
ATS-Friendly Resume Builder

Creates clean, single-column, machine-readable resumes.
Supports PDF and DOCX output.

Important:
- Does not invent experience or achievements.
- Uses only information supplied by the user.
- ATS score is advisory, not a guarantee.
"""

from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    HRFlowable,
    KeepTogether,
)
from docx import Document
from docx.shared import Pt, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.section import WD_SECTION
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
import re


# ------------------------------------------------------------------
# HELPERS
# ------------------------------------------------------------------

def clean(value):
    """Return a safely cleaned string."""
    if value is None:
        return ""

    return str(value).strip()


def clean_list(values):
    """Remove empty values and duplicates while preserving order."""
    if not values:
        return []

    result = []
    seen = set()

    for value in values:
        value = clean(value)

        if not value:
            continue

        key = value.lower()

        if key not in seen:
            seen.add(key)
            result.append(value)

    return result


def escape_pdf_text(value):
    """
    Basic escaping for ReportLab Paragraph.
    """
    value = clean(value)

    value = value.replace("&", "&amp;")
    value = value.replace("<", "&lt;")
    value = value.replace(">", "&gt;")

    return value


def split_lines(text):
    """
    Convert a multiline field into clean bullet-like lines.
    """
    if not text:
        return []

    lines = re.split(r"[\r\n]+", text)

    result = []

    for line in lines:
        line = re.sub(r"^[•●▪◦\-\*]+\s*", "", line.strip())

        if line:
            result.append(line)

    return result


# ------------------------------------------------------------------
# DATA NORMALIZATION
# ------------------------------------------------------------------

def normalize_resume_data(data):
    """
    Normalize frontend JSON into a predictable resume structure.
    """

    data = data or {}

    personal = data.get("personal", {}) or {}

    experience = data.get("experience", []) or []
    education = data.get("education", []) or []
    projects = data.get("projects", []) or []

    normalized = {
        "personal": {
            "name": clean(personal.get("name")),
            "title": clean(personal.get("title")),
            "email": clean(personal.get("email")),
            "phone": clean(personal.get("phone")),
            "location": clean(personal.get("location")),
            "linkedin": clean(personal.get("linkedin")),
            "github": clean(personal.get("github")),
            "portfolio": clean(personal.get("portfolio")),
        },

        "summary": clean(data.get("summary")),

        "skills": clean_list(data.get("skills", [])),

        "experience": [],
        "education": [],
        "projects": [],

        "certifications": clean_list(
            data.get("certifications", [])
        ),

        "achievements": clean_list(
            data.get("achievements", [])
        ),

        "languages": clean_list(
            data.get("languages", [])
        ),
    }

    for item in experience:
        normalized["experience"].append({
            "job_title": clean(item.get("job_title")),
            "company": clean(item.get("company")),
            "location": clean(item.get("location")),
            "start_date": clean(item.get("start_date")),
            "end_date": clean(item.get("end_date")),
            "description": clean(item.get("description")),
            "bullets": split_lines(item.get("description", "")),
        })

    for item in education:
        normalized["education"].append({
            "degree": clean(item.get("degree")),
            "institution": clean(item.get("institution")),
            "location": clean(item.get("location")),
            "start_date": clean(item.get("start_date")),
            "end_date": clean(item.get("end_date")),
            "grade": clean(item.get("grade")),
        })

    for item in projects:
        normalized["projects"].append({
            "name": clean(item.get("name")),
            "description": clean(item.get("description")),
            "technologies": clean_list(
                item.get("technologies", [])
            ),
        })

    return normalized


# ------------------------------------------------------------------
# RESUME TEXT
# ------------------------------------------------------------------

def build_resume_text(data):
    """
    Build a plain-text representation.

    This is useful for:
    - ATS analysis
    - keyword matching
    - previews
    - testing
    """

    data = normalize_resume_data(data)

    lines = []

    personal = data["personal"]

    if personal["name"]:
        lines.append(personal["name"])

    if personal["title"]:
        lines.append(personal["title"])

    contact = [
        personal["email"],
        personal["phone"],
        personal["location"],
        personal["linkedin"],
        personal["github"],
        personal["portfolio"],
    ]

    contact = [item for item in contact if item]

    if contact:
        lines.append(" | ".join(contact))

    if data["summary"]:
        lines.extend([
            "",
            "PROFESSIONAL SUMMARY",
            data["summary"],
        ])

    if data["skills"]:
        lines.extend([
            "",
            "SKILLS",
            ", ".join(data["skills"]),
        ])

    if data["experience"]:
        lines.extend([
            "",
            "PROFESSIONAL EXPERIENCE",
        ])

        for item in data["experience"]:

            heading = " | ".join(
                [
                    x for x in [
                        item["job_title"],
                        item["company"],
                    ]
                    if x
                ]
            )

            if heading:
                lines.append(heading)

            date_range = " - ".join(
                [
                    x for x in [
                        item["start_date"],
                        item["end_date"],
                    ]
                    if x
                ]
            )

            if date_range:
                lines.append(date_range)

            lines.extend(
                [f"• {bullet}" for bullet in item["bullets"]]
            )

    if data["education"]:
        lines.extend([
            "",
            "EDUCATION",
        ])

        for item in data["education"]:

            heading = " | ".join(
                [
                    x for x in [
                        item["degree"],
                        item["institution"],
                    ]
                    if x
                ]
            )

            if heading:
                lines.append(heading)

            details = " | ".join(
                [
                    x for x in [
                        item["location"],
                        item["start_date"],
                        item["end_date"],
                        item["grade"],
                    ]
                    if x
                ]
            )

            if details:
                lines.append(details)

    if data["projects"]:
        lines.extend([
            "",
            "PROJECTS",
        ])

        for item in data["projects"]:

            if item["name"]:
                lines.append(item["name"])

            if item["description"]:
                lines.append(item["description"])

            if item["technologies"]:
                lines.append(
                    "Technologies: "
                    + ", ".join(item["technologies"])
                )

    if data["certifications"]:
        lines.extend([
            "",
            "CERTIFICATIONS",
        ])

        for item in data["certifications"]:
            lines.append(f"• {item}")

    if data["achievements"]:
        lines.extend([
            "",
            "ACHIEVEMENTS",
        ])

        for item in data["achievements"]:
            lines.append(f"• {item}")

    if data["languages"]:
        lines.extend([
            "",
            "LANGUAGES",
        ])

        for item in data["languages"]:
            lines.append(f"• {item}")

    return "\n".join(lines)


# ------------------------------------------------------------------
# ATS SCORE
# ------------------------------------------------------------------

def calculate_builder_ats_score(data, job_description=""):
    """
    Advisory ATS score.

    Components:
    - completeness
    - standard sections
    - keyword match when JD is supplied
    - content density
    """

    data = normalize_resume_data(data)

    score = 0
    checks = []

    personal = data["personal"]

    # Contact information - 20
    contact_fields = [
        personal["name"],
        personal["email"],
        personal["phone"],
        personal["location"],
    ]

    contact_count = sum(
        1 for value in contact_fields if value
    )

    contact_score = int(
        (contact_count / len(contact_fields)) * 20
    )

    score += contact_score

    checks.append({
        "name": "Contact information",
        "score": contact_score,
        "max": 20,
    })

    # Summary - 10
    summary_score = 10 if data["summary"] else 0
    score += summary_score

    checks.append({
        "name": "Professional summary",
        "score": summary_score,
        "max": 10,
    })

    # Skills - 15
    skills_score = 15 if data["skills"] else 0
    score += skills_score

    checks.append({
        "name": "Skills",
        "score": skills_score,
        "max": 15,
    })

    # Experience - 20
    experience_score = 20 if data["experience"] else 0
    score += experience_score

    checks.append({
        "name": "Professional experience",
        "score": experience_score,
        "max": 20,
    })

    # Education - 10
    education_score = 10 if data["education"] else 0
    score += education_score

    checks.append({
        "name": "Education",
        "score": education_score,
        "max": 10,
    })

    # Projects / certifications / achievements - 10
    additional = (
        bool(data["projects"])
        or bool(data["certifications"])
        or bool(data["achievements"])
    )

    additional_score = 10 if additional else 0
    score += additional_score

    checks.append({
        "name": "Additional sections",
        "score": additional_score,
        "max": 10,
    })

    # JD keyword match - 15
    keyword_score = 0

    if job_description.strip() and data["skills"]:

        jd_lower = job_description.lower()

        matched = 0

        for skill in data["skills"]:

            if skill.lower() in jd_lower:
                matched += 1

        if data["skills"]:
            keyword_score = int(
                min(
                    matched / len(data["skills"]),
                    1
                ) * 15
            )

    elif not job_description.strip():

        # Give the builder a neutral baseline.
        keyword_score = 15

    score += keyword_score

    checks.append({
        "name": "Job-description keyword alignment",
        "score": keyword_score,
        "max": 15,
    })

    score = max(0, min(100, score))

    recommendations = []

    if not personal["email"]:
        recommendations.append(
            "Add a professional email address."
        )

    if not personal["phone"]:
        recommendations.append(
            "Add a phone number."
        )

    if not data["summary"]:
        recommendations.append(
            "Add a concise professional summary."
        )

    if not data["skills"]:
        recommendations.append(
            "Add relevant technical and professional skills."
        )

    if not data["experience"]:
        recommendations.append(
            "Add your professional experience."
        )

    if not data["education"]:
        recommendations.append(
            "Add your education details."
        )

    if job_description.strip() and keyword_score < 10:
        recommendations.append(
            "Consider adding relevant keywords from the job description "
            "only where they accurately reflect your experience."
        )

    return {
        "score": score,
        "checks": checks,
        "recommendations": recommendations,
    }


# ------------------------------------------------------------------
# PDF
# ------------------------------------------------------------------

def generate_ats_pdf(data):
    """
    Generate an ATS-friendly PDF.
    """

    data = normalize_resume_data(data)

    output = BytesIO()

    document = SimpleDocTemplate(
        output,
        pagesize=A4,
        rightMargin=14 * mm,
        leftMargin=14 * mm,
        topMargin=10 * mm,
        bottomMargin=10 * mm,
        title=data["personal"]["name"] or "ATS Resume",
        author="Role Finder Portal",
    )

    styles = getSampleStyleSheet()

    name_style = ParagraphStyle(
        "ResumeName",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=17,
        leading=19,
        alignment=TA_CENTER,
        spaceAfter=2,
    )

    title_style = ParagraphStyle(
        "ResumeTitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9.5,
        leading=11,
        alignment=TA_CENTER,
        spaceAfter=3,
    )

    contact_style = ParagraphStyle(
        "ResumeContact",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=9.5,
        alignment=TA_CENTER,
        spaceAfter=4,
    )

    section_style = ParagraphStyle(
        "ResumeSection",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=11,
        spaceBefore=5,
        spaceAfter=2,
    )

    body_style = ParagraphStyle(
        "ResumeBody",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=10,
        spaceAfter=1.5,
    )

    job_title_style = ParagraphStyle(
        "JobTitle",
        parent=body_style,
        fontName="Helvetica-Bold",
        spaceAfter=1,
    )

    story = []

    personal = data["personal"]

    if personal["name"]:
        story.append(
            Paragraph(
                escape_pdf_text(personal["name"]),
                name_style
            )
        )

    if personal["title"]:
        story.append(
            Paragraph(
                escape_pdf_text(personal["title"]),
                title_style
            )
        )

    contact = [
        personal["email"],
        personal["phone"],
        personal["location"],
        personal["linkedin"],
        personal["github"],
        personal["portfolio"],
    ]

    contact = [
        escape_pdf_text(value)
        for value in contact
        if value
    ]

    if contact:
        story.append(
            Paragraph(
                " | ".join(contact),
                contact_style
            )
        )

    def add_section(title):
        story.append(
            Paragraph(
                escape_pdf_text(title.upper()),
                section_style
            )
        )

        story.append(
            HRFlowable(
                width="100%",
                thickness=0.6,
                spaceBefore=0,
                spaceAfter=3,
            )
        )

    # Summary
    if data["summary"]:

        add_section("Professional Summary")

        story.append(
            Paragraph(
                escape_pdf_text(data["summary"]),
                body_style
            )
        )

    # Skills
    if data["skills"]:

        add_section("Skills")

        story.append(
            Paragraph(
                escape_pdf_text(
                    ", ".join(data["skills"])
                ),
                body_style
            )
        )

    # Experience
    if data["experience"]:

        add_section("Professional Experience")

        for item in data["experience"]:

            heading = " | ".join(
                [
                    escape_pdf_text(x)
                    for x in [
                        item["job_title"],
                        item["company"],
                    ]
                    if x
                ]
            )

            date_range = " - ".join(
                [
                    escape_pdf_text(x)
                    for x in [
                        item["start_date"],
                        item["end_date"],
                    ]
                    if x
                ]
            )

            block = []

            if heading:
                block.append(
                    Paragraph(
                        heading,
                        job_title_style
                    )
                )

            if date_range:
                block.append(
                    Paragraph(
                        date_range,
                        body_style
                    )
                )

            for bullet in item["bullets"]:

                block.append(
                    Paragraph(
                        "• "
                        + escape_pdf_text(bullet),
                        body_style
                    )
                )

            story.append(
                KeepTogether(block)
            )

    # Education
    if data["education"]:

        add_section("Education")

        for item in data["education"]:

            heading = " | ".join(
                [
                    escape_pdf_text(x)
                    for x in [
                        item["degree"],
                        item["institution"],
                    ]
                    if x
                ]
            )

            details = " | ".join(
                [
                    escape_pdf_text(x)
                    for x in [
                        item["location"],
                        item["start_date"],
                        item["end_date"],
                        item["grade"],
                    ]
                    if x
                ]
            )

            if heading:
                story.append(
                    Paragraph(
                        heading,
                        job_title_style
                    )
                )

            if details:
                story.append(
                    Paragraph(
                        details,
                        body_style
                    )
                )

    # Projects
    if data["projects"]:

        add_section("Projects")

        for item in data["projects"]:

            if item["name"]:
                story.append(
                    Paragraph(
                        escape_pdf_text(item["name"]),
                        job_title_style
                    )
                )

            if item["description"]:
                story.append(
                    Paragraph(
                        escape_pdf_text(
                            item["description"]
                        ),
                        body_style
                    )
                )

            if item["technologies"]:
                story.append(
                    Paragraph(
                        "Technologies: "
                        + escape_pdf_text(
                            ", ".join(
                                item["technologies"]
                            )
                        ),
                        body_style
                    )
                )

    # Certifications
    if data["certifications"]:

        add_section("Certifications")

        for item in data["certifications"]:
            story.append(
                Paragraph(
                    "• " + escape_pdf_text(item),
                    body_style
                )
            )

    # Achievements
    if data["achievements"]:

        add_section("Achievements")

        for item in data["achievements"]:
            story.append(
                Paragraph(
                    "• " + escape_pdf_text(item),
                    body_style
                )
            )

    # Languages
    if data["languages"]:

        add_section("Languages")

        story.append(
            Paragraph(
                escape_pdf_text(
                    ", ".join(data["languages"])
                ),
                body_style
            )
        )

    document.build(story)

    output.seek(0)

    return output


# ------------------------------------------------------------------
# DOCX
# ------------------------------------------------------------------

def remove_table_borders(table):
    """
    Ensure tables aren't used for resume layout.
    This helper is retained for future compatibility.
    """
    tbl = table._tbl

    tblPr = tbl.tblPr

    borders = tblPr.first_child_found_in("w:tblBorders")

    if borders is None:
        borders = OxmlElement("w:tblBorders")
        tblPr.append(borders)

    for edge in (
        "top",
        "left",
        "bottom",
        "right",
        "insideH",
        "insideV",
    ):
        tag = "w:" + edge

        element = borders.find(qn(tag))

        if element is None:
            element = OxmlElement(tag)
            borders.append(element)

        element.set(qn("w:val"), "nil")


def add_docx_heading(document, title):
    paragraph = document.add_paragraph()

    paragraph.paragraph_format.space_before = Pt(5)
    paragraph.paragraph_format.space_after = Pt(2)

    run = paragraph.add_run(title.upper())

    run.bold = True
    run.font.name = "Arial"
    run.font.size = Pt(10)

    return paragraph


def add_docx_body(document, text, bold=False):
    paragraph = document.add_paragraph()

    paragraph.paragraph_format.space_after = Pt(1)

    run = paragraph.add_run(text)

    run.bold = bold
    run.font.name = "Arial"
    run.font.size = Pt(8.5)

    return paragraph


def generate_ats_docx(data):
    """
    Generate an ATS-friendly Word document.
    """

    data = normalize_resume_data(data)

    document = Document()

    section = document.sections[0]

    section.top_margin = Inches(0.45)
    section.bottom_margin = Inches(0.45)
    section.left_margin = Inches(0.6)
    section.right_margin = Inches(0.6)

    # Default font
    styles = document.styles

    styles["Normal"].font.name = "Arial"
    styles["Normal"].font.size = Pt(8.5)

    personal = data["personal"]

    # Name
    if personal["name"]:

        paragraph = document.add_paragraph()

        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER

        run = paragraph.add_run(
            personal["name"]
        )

        run.bold = True
        run.font.name = "Arial"
        run.font.size = Pt(17)

    # Title
    if personal["title"]:

        paragraph = document.add_paragraph()

        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER

        run = paragraph.add_run(
            personal["title"]
        )

        run.font.name = "Arial"
        run.font.size = Pt(9.5)

    # Contact
    contact = [
        personal["email"],
        personal["phone"],
        personal["location"],
        personal["linkedin"],
        personal["github"],
        personal["portfolio"],
    ]

    contact = [
        value for value in contact if value
    ]

    if contact:

        paragraph = document.add_paragraph()

        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER

        run = paragraph.add_run(
            " | ".join(contact)
        )

        run.font.name = "Arial"
        run.font.size = Pt(8)

    # Summary
    if data["summary"]:

        add_docx_heading(
            document,
            "Professional Summary"
        )

        add_docx_body(
            document,
            data["summary"]
        )

    # Skills
    if data["skills"]:

        add_docx_heading(
            document,
            "Skills"
        )

        add_docx_body(
            document,
            ", ".join(data["skills"])
        )

    # Experience
    if data["experience"]:

        add_docx_heading(
            document,
            "Professional Experience"
        )

        for item in data["experience"]:

            heading = " | ".join(
                [
                    x for x in [
                        item["job_title"],
                        item["company"],
                    ]
                    if x
                ]
            )

            if heading:
                add_docx_body(
                    document,
                    heading,
                    bold=True
                )

            date_range = " - ".join(
                [
                    x for x in [
                        item["start_date"],
                        item["end_date"],
                    ]
                    if x
                ]
            )

            if date_range:
                add_docx_body(
                    document,
                    date_range
                )

            for bullet in item["bullets"]:

                paragraph = document.add_paragraph(
                    style="List Bullet"
                )

                paragraph.paragraph_format.space_after = Pt(1)

                run = paragraph.add_run(
                    bullet
                )

                run.font.name = "Arial"
                run.font.size = Pt(8.5)

    # Education
    if data["education"]:

        add_docx_heading(
            document,
            "Education"
        )

        for item in data["education"]:

            heading = " | ".join(
                [
                    x for x in [
                        item["degree"],
                        item["institution"],
                    ]
                    if x
                ]
            )

            if heading:
                add_docx_body(
                    document,
                    heading,
                    bold=True
                )

            details = " | ".join(
                [
                    x for x in [
                        item["location"],
                        item["start_date"],
                        item["end_date"],
                        item["grade"],
                    ]
                    if x
                ]
            )

            if details:
                add_docx_body(
                    document,
                    details
                )

    # Projects
    if data["projects"]:

        add_docx_heading(
            document,
            "Projects"
        )

        for item in data["projects"]:

            if item["name"]:
                add_docx_body(
                    document,
                    item["name"],
                    bold=True
                )

            if item["description"]:
                add_docx_body(
                    document,
                    item["description"]
                )

            if item["technologies"]:
                add_docx_body(
                    document,
                    "Technologies: "
                    + ", ".join(
                        item["technologies"]
                    )
                )

    # Certifications
    if data["certifications"]:

        add_docx_heading(
            document,
            "Certifications"
        )

        for item in data["certifications"]:

            paragraph = document.add_paragraph(
                style="List Bullet"
            )

            run = paragraph.add_run(item)

            run.font.name = "Arial"
            run.font.size = Pt(9)

    # Achievements
    if data["achievements"]:

        add_docx_heading(
            document,
            "Achievements"
        )

        for item in data["achievements"]:

            paragraph = document.add_paragraph(
                style="List Bullet"
            )

            run = paragraph.add_run(item)

            run.font.name = "Arial"
            run.font.size = Pt(9)

    # Languages
    if data["languages"]:

        add_docx_heading(
            document,
            "Languages"
        )

        add_docx_body(
            document,
            ", ".join(data["languages"])
        )

    output = BytesIO()

    document.save(output)

    output.seek(0)

    return output