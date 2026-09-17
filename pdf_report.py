"""
pdf_report.py
--------------
Builds a downloadable PDF version of a resume analysis result: ATS score,
role matches, and (if chosen) the target-role action plan.

Kept print-friendly on purpose — white background, dark text, gold used only
for rules/headings — rather than mirroring the site's dark theme, since a
report meant to be printed or attached to an application shouldn't burn ink
on a black background.
"""

import io
from datetime import datetime

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, ListFlowable, ListItem,
)
from reportlab.lib.enums import TA_LEFT

GOLD = colors.HexColor("#8A6D1F")
INK = colors.HexColor("#20201C")
INK_SOFT = colors.HexColor("#65605A")
HAIRLINE = colors.HexColor("#D8D2C2")
GREEN = colors.HexColor("#2F6F4F")
RED = colors.HexColor("#A6402A")


def _styles():
    base = getSampleStyleSheet()
    styles = {
        "mark": ParagraphStyle("mark", parent=base["Normal"], fontName="Helvetica",
                                fontSize=9, textColor=INK_SOFT, spaceAfter=2),
        "title": ParagraphStyle("title", parent=base["Title"], fontName="Helvetica-Bold",
                                 fontSize=22, textColor=INK, alignment=TA_LEFT, spaceAfter=2),
        "subtitle": ParagraphStyle("subtitle", parent=base["Normal"], fontName="Helvetica",
                                    fontSize=10, textColor=INK_SOFT, spaceAfter=16),
        "h2": ParagraphStyle("h2", parent=base["Heading2"], fontName="Helvetica-Bold",
                              fontSize=14, textColor=INK, spaceBefore=18, spaceAfter=8),
        "h3": ParagraphStyle("h3", parent=base["Heading3"], fontName="Helvetica-Bold",
                              fontSize=11, textColor=GOLD, spaceBefore=12, spaceAfter=4),
        "body": ParagraphStyle("body", parent=base["Normal"], fontName="Helvetica",
                                fontSize=10, textColor=INK, leading=14),
        "body_soft": ParagraphStyle("body_soft", parent=base["Normal"], fontName="Helvetica",
                                     fontSize=9.5, textColor=INK_SOFT, leading=13),
        "score_big": ParagraphStyle("score_big", parent=base["Normal"], fontName="Helvetica-Bold",
                                     fontSize=32, textColor=INK, leading=34),
        "tag": ParagraphStyle("tag", parent=base["Normal"], fontName="Helvetica",
                               fontSize=9, textColor=INK_SOFT, leading=13),
    }
    return styles


def _rating_color(rating):
    if rating in ("Excellent", "Good"):
        return GREEN
    if rating == "Needs Work":
        return GOLD
    return RED


def _tier_label(score):
    if score >= 70:
        return "STRONG FIT", GREEN
    if score >= 40:
        return "MODERATE FIT", GOLD
    return "LOW FIT", INK_SOFT


def _skill_line(skills, styles):
    if not skills:
        return Paragraph("None", styles["body_soft"])
    return Paragraph(", ".join(skills), styles["tag"])


def build_pdf_report(data: dict) -> io.BytesIO:
    styles = _styles()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=letter,
        leftMargin=0.75 * inch, rightMargin=0.75 * inch,
        topMargin=0.7 * inch, bottomMargin=0.7 * inch,
    )
    story = []

    # ---- Header ----
    story.append(Paragraph("ROLE FINDER", styles["mark"]))
    story.append(Paragraph("Resume Analysis Report", styles["title"]))
    filename = data.get("filename", "resume")
    generated = datetime.now().strftime("%d %b %Y")
    story.append(Paragraph(f"{filename} &middot; generated {generated}", styles["subtitle"]))
    story.append(HRFlowable(width="100%", thickness=1, color=HAIRLINE, spaceAfter=14))

    # ---- ATS score ----
    ats = data.get("ats", {})
    story.append(Paragraph("ATS Compatibility", styles["h2"]))

    score_color = _rating_color(ats.get("rating", ""))
    score_table = Table(
        [[
            Paragraph(f'<font color="{score_color.hexval()}">{ats.get("score", 0)}</font><font size="14">/100</font>', styles["score_big"]),
            Paragraph(f'<b>{ats.get("rating", "")}</b><br/>Applicant Tracking System compatibility', styles["body"]),
        ]],
        colWidths=[2.2 * inch, 4.1 * inch],
    )
    score_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(score_table)
    story.append(Spacer(1, 8))

    issues = ats.get("issues", [])
    if issues:
        story.append(Paragraph("Issues to fix:", styles["h3"]))
        story.append(ListFlowable(
            [ListItem(Paragraph(i, styles["body"]), spaceAfter=4) for i in issues],
            bulletType="bullet", start="-",
        ))
    else:
        story.append(Paragraph("No major ATS red flags detected.", styles["body"]))

    # ---- Resume health ----
    health = data.get("health", {})
    story.append(Paragraph("Resume Health Check", styles["h2"]))
    health_rows = [
        ["Email", "Found" if health.get("has_email") else "Not found"],
        ["Phone", "Found" if health.get("has_phone") else "Not found"],
        ["Word count", str(health.get("word_count", "-"))],
        ["Sections detected", ", ".join(health.get("sections_found", [])) or "None"],
    ]
    health_table = Table(health_rows, colWidths=[1.8 * inch, 4.5 * inch])
    health_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9.5),
        ("TEXTCOLOR", (0, 0), (0, -1), INK),
        ("TEXTCOLOR", (1, 0), (1, -1), INK_SOFT),
        ("LINEBELOW", (0, 0), (-1, -2), 0.5, HAIRLINE),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(health_table)

    # ---- Target role plan (if chosen) ----
    plan = data.get("target_plan")
    if plan:
        story.append(Paragraph(f"Your Plan for {plan['role']}", styles["h2"]))
        story.append(Paragraph(
            f"<b>{plan['score']}%</b> of this role's skills matched right now", styles["body"]
        ))
        story.append(Spacer(1, 4))
        story.append(Paragraph("<b>Matched skills:</b>", styles["h3"]))
        story.append(_skill_line(plan.get("matched_skills", []), styles))
        story.append(Paragraph("<b>Missing skills:</b>", styles["h3"]))
        story.append(_skill_line(plan.get("missing_skills", []), styles))

        if plan.get("skill_development"):
            story.append(Paragraph("Skills to Develop", styles["h3"]))
            story.append(ListFlowable(
                [ListItem(Paragraph(f"<b>{item['skill']}</b> — {item['tip']}", styles["body"]), spaceAfter=5)
                 for item in plan["skill_development"]],
                bulletType="bullet", start="-",
            ))

        if plan.get("personal_development"):
            story.append(Paragraph("Personal Development", styles["h3"]))
            story.append(ListFlowable(
                [ListItem(Paragraph(f"<b>{item['skill']}</b> — {item['tip']}", styles["body"]), spaceAfter=5)
                 for item in plan["personal_development"]],
                bulletType="bullet", start="-",
            ))

        if plan.get("resume_changes"):
            story.append(Paragraph("Resume Changes to Make", styles["h3"]))
            story.append(ListFlowable(
                [ListItem(Paragraph(c, styles["body"]), spaceAfter=5) for c in plan["resume_changes"]],
                bulletType="bullet", start="-",
            ))
    else:
        focus_skills = data.get("focus_skills", [])
        if focus_skills:
            story.append(Paragraph("Focus on These Skills Next", styles["h2"]))
            story.append(ListFlowable(
                [ListItem(Paragraph(
                    f"<b>{item['skill']}</b> — helps with: {', '.join(item['helps_with'])}",
                    styles["body"]), spaceAfter=5)
                 for item in focus_skills],
                bulletType="bullet", start="-",
            ))

    # ---- Role matches table ----
    roles = data.get("roles", [])
    if roles:
        story.append(Paragraph("Role Matches", styles["h2"]))
        rows = [["Role", "Score", "Fit"]]
        row_colors = []
        for role in roles:
            label, color = _tier_label(role["score"])
            rows.append([role["role"], f'{role["score"]}%', label])
            row_colors.append(color)

        role_table = Table(rows, colWidths=[3.3 * inch, 1.0 * inch, 1.7 * inch])
        table_style = [
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9.5),
            ("TEXTCOLOR", (0, 0), (-1, 0), INK),
            ("LINEBELOW", (0, 0), (-1, 0), 1, INK),
            ("LINEBELOW", (0, 1), (-1, -2), 0.5, HAIRLINE),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]
        for i, color in enumerate(row_colors, start=1):
            table_style.append(("TEXTCOLOR", (2, i), (2, i), color))
        role_table.setStyle(TableStyle(table_style))
        story.append(role_table)

    story.append(Spacer(1, 16))
    story.append(HRFlowable(width="100%", thickness=0.5, color=HAIRLINE, spaceAfter=6))
    story.append(Paragraph(
        "Matches are based on keyword detection, not a full read of your experience — "
        "use them as a starting point.", styles["body_soft"]
    ))

    doc.build(story)
    buf.seek(0)
    return buf


def build_interview_question_pdf(data: dict) -> io.BytesIO:
    """Build a PDF of interview questions for missing skills and selected roles."""
    styles = _styles()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=letter,
        leftMargin=0.75 * inch, rightMargin=0.75 * inch,
        topMargin=0.7 * inch, bottomMargin=0.7 * inch,
    )
    story = []

    story.append(Paragraph("ROLE FINDER", styles["mark"]))
    story.append(Paragraph("Interview Question Pack", styles["title"]))
    generated = datetime.now().strftime("%d %b %Y")
    story.append(Paragraph(f"Generated {generated}", styles["subtitle"]))
    story.append(HRFlowable(width="100%", thickness=1, color=HAIRLINE, spaceAfter=14))

    pack_mode = (data.get("question_pack") or "standard").lower()
    limit = 24 if pack_mode == "full" else 12

    target_plan = data.get("target_plan") or {}
    comparison_roles = data.get("comparison_roles") or []
    if target_plan and target_plan.get("interview_questions"):
        question_sets = target_plan["interview_questions"]
        title = f"Target role: {target_plan.get('role', 'Role')}"
    elif comparison_roles:
        question_sets = {}
        for role in comparison_roles:
            role_name = role.get("role") or "Target role"
            missing = role.get("missing_skills") or []
            if not missing:
                continue
            question_sets[role_name] = {
                skill: [
                    f"Tell me about a time you used {skill} in a {role_name} context.",
                    f"How do you measure success when working with {skill} in a {role_name} environment?",
                    f"Describe a challenge involving {skill} and how you handled it.",
                    f"What would you do differently if the scale of {skill} changed unexpectedly in {role_name}?",
                    f"How do you prioritize quality and speed when working with {skill}?",
                    f"What metrics tell you your use of {skill} is improving results?",
                    f"Describe a time when {skill} helped you navigate ambiguity or change.",
                    f"How do you communicate the value of {skill} to non-experts in a {role_name} setting?",
                ]
                for skill in missing[:3]
            }
        title = "Comparison roles"
    else:
        question_sets = data.get("interview_questions") or {}
        title = "Interview preparation"

    story.append(Paragraph(title, styles["h2"]))

    if not question_sets:
        story.append(Paragraph("No interview questions were available for this analysis set yet.", styles["body"]))
        doc.build(story)
        buf.seek(0)
        return buf

    for section_title, skills in question_sets.items():
        if isinstance(skills, dict):
            if not skills:
                continue
            story.append(Paragraph(f"{section_title}", styles["h3"]))
            for skill, questions in skills.items():
                story.append(Paragraph(f"<b>{skill}</b>", styles["body"]))
                story.append(ListFlowable(
                    [ListItem(Paragraph(q, styles["body"]), spaceAfter=5) for q in questions[:limit]],
                    bulletType="bullet",
                    start="-",
                ))
        else:
            story.append(Paragraph(f"{section_title}", styles["h3"]))
            question_list = list(skills)[:limit]
            story.append(ListFlowable(
                [ListItem(Paragraph(q, styles["body"]), spaceAfter=5) for q in question_list],
                bulletType="bullet",
                start="-",
            ))
        story.append(Spacer(1, 12))

    story.append(Spacer(1, 8))
    story.append(HRFlowable(width="100%", thickness=0.5, color=HAIRLINE, spaceAfter=8))
    story.append(Paragraph(
        "Use these questions to practice, structure your examples, and sharpen your answers before interviews.",
        styles["body_soft"],
    ))

    doc.build(story)
    buf.seek(0)
    return buf
