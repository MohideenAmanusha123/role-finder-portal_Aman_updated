"""
resume_importer.py
-------------------
Turns raw resume text (from an uploaded PDF/DOCX/TXT) into the structured
shape the ATS Resume Builder expects.

This is inherently best-effort: it infers section boundaries, job titles,
companies, and dates from plain-text layout using regex heuristics. Real
resumes vary a lot (two-column layouts, creative formats, PDF text that gets
reordered on extraction), so nothing here should be treated as ground truth.

`parse_resume_for_builder()` returns both the best-guess structured data AND
a `parse_notes` list describing what it wasn't confident about, so the
caller (the web UI) can show the user a "please review these fields" prompt
before anything gets built from them, rather than silently shipping a
mis-parsed resume.
"""

import re


def _parse_experience_entries(lines):
    month = r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*"
    date_token = rf"(?:{month}[\s.-]+)?(?:\d{{1,2}}[\s./-]+)?\d{{4}}"
    date_separator = r"(?:[-–—]|to|through)"
    date_range = rf"{date_token}\s*{date_separator}\s*(?:present|current|{date_token})"
    date_pattern = re.compile(
        rf"^\s*{date_range}\s*$",
        re.I,
    )
    inline_date_pattern = re.compile(
        rf"(?P<start>{date_token})\s*{date_separator}\s*"
        rf"(?P<end>present|current|{date_token})",
        re.I,
    )
    labelled_date_pattern = re.compile(
        rf"^(?:start\s+date|from)\s*:\s*(?P<start>{date_token})\s*(?:[,;|]\s*)?"
        rf"(?:end\s+date|to)\s*:\s*(?P<end>present|current|{date_token})$",
        re.I,
    )

    def split_header(value):
        value = value.strip(" -–—|")
        if not value:
            return []
        parts = [
            part.strip()
            for part in re.split(r"\s*\|\s*|\s+[—–]\s+|\s+at\s+|\s+@\s+", value, flags=re.I)
            if part.strip()
        ]
        return parts[-2:]

    date_positions = [
        (index, inline_date_pattern.search(line))
        for index, line in enumerate(lines)
        if date_pattern.match(line) or inline_date_pattern.search(line) or labelled_date_pattern.match(line)
    ]
    if date_positions:
        entries = []
        previous_date = None
        for position, (date_index, date_match) in enumerate(date_positions):
            between = lines[(previous_date + 1) if previous_date is not None else 0:date_index]
            date_line = lines[date_index]
            labelled_match = labelled_date_pattern.match(date_line)
            if labelled_match:
                date_match = labelled_match
                start_date = labelled_match.group("start")
                end_date = labelled_match.group("end")
                inline_prefix = ""
                inline_suffix = ""
            else:
                inline_prefix = date_line[:date_match.start()].strip(" -–—|")
                inline_suffix = date_line[date_match.end():].strip(" -–—|")
                start_date = date_match.group("start")
                end_date = date_match.group("end")
            inline_header = split_header(inline_prefix)
            if inline_header:
                header = inline_header[-2:]
                body = between
            else:
                header = between[-2:]
                body = between[:-len(header)] if header else between
                if len(header) == 1:
                    header = split_header(header[0])
            if entries and body:
                entries[-1]["description"] = "\n".join(body)
            entries.append({
                "job_title": header[0] if header else "",
                "company": header[1] if len(header) > 1 else "",
                "start_date": start_date.strip(),
                "end_date": end_date.strip(),
                "description": inline_suffix,
            })
            previous_date = date_index
        trailing = lines[previous_date + 1:] if previous_date is not None else []
        if trailing and entries:
            entries[-1]["description"] = "\n".join(
                [entries[-1]["description"], *trailing]
            ).strip()
        return entries

    return [{
        "job_title": lines[0] if lines else "",
        "company": lines[1] if len(lines) > 1 else "",
        "description": "\n".join(lines[2:]),
    }] if lines else []


HEADING_PATTERNS = {
    "summary": re.compile(r"^(?:professional\s+)?summary|profile|objective$", re.I),
    "skills": re.compile(r"^(?:technical\s+)?skills|core\s+competencies|technologies$", re.I),
    "experience": re.compile(r"^(?:work\s+)?experience|employment\s+history|professional\s+experience$", re.I),
    "education": re.compile(r"^education|academic\s+background$", re.I),
    "projects": re.compile(r"^projects?$", re.I),
    "certifications": re.compile(r"^certifications?|licenses?$", re.I),
    "achievements": re.compile(r"^achievements?|awards?$", re.I),
    "languages": re.compile(r"^languages?$", re.I),
}

EDUCATION_DATES_RE = re.compile(
    r"(?P<start>(?:[A-Za-z]{3,9}\s+)?\d{4})\s*(?:[-–—]|to)\s*"
    r"(?P<end>(?:[A-Za-z]{3,9}\s+)?\d{4}|present|current)",
    re.I,
)


def parse_resume_for_builder(text, find_skills_fn, skill_vocabulary, normalize_resume_data_fn):
    """Best-effort structured parse of raw resume text.

    `find_skills_fn` / `skill_vocabulary` are injected (rather than imported
    directly) to avoid a circular import with resume_matcher/roles_data, and
    to keep this module unit-testable with a fake skill detector.

    Returns (normalized_resume_dict, parse_notes) where parse_notes is a
    list of short human-readable strings flagging sections the parser was
    NOT confident about — the caller should surface these to the user
    before treating the parsed data as final.
    """
    notes = []
    lines = [line.strip() for line in (text or "").splitlines() if line.strip()]
    joined = "\n".join(lines)

    if not lines:
        notes.append("The uploaded file had no readable text — every field below is empty. Please fill them in manually.")

    email_match = re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", joined)
    phone_match = re.search(r"(?<!\d)(?:\+?\d[\d\s().-]{8,}\d)(?!\d)", joined)
    link_match = re.search(r"https?://(?:www\.)?(?:linkedin\.com|github\.com)/[^\s|]+", joined, re.I)
    if not email_match:
        notes.append("No email address was detected — please add it manually.")
    if not phone_match:
        notes.append("No phone number was detected — please add it manually.")

    sections = {}
    current = None
    for line in lines:
        heading, separator, inline_content = line.partition(":")
        heading_candidate = heading.strip() if separator else line
        matched = next(
            (name for name, pattern in HEADING_PATTERNS.items()
             if pattern.fullmatch(heading_candidate) or pattern.match(heading_candidate)),
            None,
        )
        if matched:
            current = matched
            sections.setdefault(current, [])
            if separator and inline_content.strip():
                sections[current].append(inline_content.strip())
        elif current:
            sections[current].append(line)

    for required_section in ("experience", "education", "skills"):
        if required_section not in sections:
            notes.append(f"No '{required_section.title()}' section heading was found — please check that section carefully.")

    contact_line = next((line for line in lines if email_match and email_match.group(0) in line), "")
    name = next(
        (line for line in lines if line != contact_line and not re.search(r"@|https?://|\+?\d[\d\s().-]{8,}\d", line)),
        "",
    )
    if not name:
        notes.append("Could not confidently detect your name from the top of the file — please fill it in.")

    skill_text = " ".join(sections.get("skills", []))
    skills = sorted(find_skills_fn(skill_text, skill_vocabulary))
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

    experience_entries = _parse_experience_entries(experience_lines)
    if experience_lines and not any(e.get("start_date") for e in experience_entries):
        notes.append("Couldn't confidently detect dates in your Experience section — please double-check the date ranges.")

    education_text = education_lines[:]
    education_start = education_end = ""
    if education_text:
        education_match = EDUCATION_DATES_RE.search(education_text[0])
        if education_match:
            education_start = education_match.group("start")
            education_end = education_match.group("end")
            education_text[0] = education_text[0][:education_match.start()].strip(" ,-–—")
    education_text = [line for line in education_text if line]

    resume_data = normalize_resume_data_fn({
        "personal": {
            "name": name,
            "email": email_match.group(0) if email_match else "",
            "phone": phone_match.group(0).strip() if phone_match else "",
            "linkedin": link_match.group(0) if link_match else "",
        },
        "summary": summary,
        "skills": skills,
        "experience": experience_entries,
        "education": [{
            "degree": education_text[0] if education_text else "",
            "institution": education_text[1] if len(education_text) > 1 else "",
            "start_date": education_start,
            "end_date": education_end,
            "description": "\n".join(education_text[2:]),
        }] if education_text else [],
        "projects": [{
            "name": project_lines[0] if project_lines else "",
            "description": "\n".join(project_lines[1:]),
        }] if project_lines else [],
        "certifications": certifications,
        "achievements": achievements,
        "languages": languages,
    })

    return resume_data, notes
