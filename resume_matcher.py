"""
resume_matcher.py
------------------
Text extraction, skill matching, weighted role scoring, JD comparison,
and experience-level signals.
"""

import os
import re

try:
    import pdfplumber
except ImportError:
    pdfplumber = None

try:
    import docx
except ImportError:
    docx = None

from roles_data import (
    ROLES, SKILL_VOCABULARY, SKILL_ALIASES, SOFT_SKILLS, SKILL_TIPS, DEV_TIPS,
)

EMAIL_RE = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
PHONE_RE = re.compile(r"(\+?\d[\d\-\s()]{8,}\d)")
BULLET_RE = re.compile(r"^\s*[-•*\u2022\u25CF\u2013]\s+")
YEARS_RE = re.compile(r"\b(\d{1,2})(?:\s*\+)?\s*(?:years?|yrs?)\b", re.IGNORECASE)
SENIORITY_RE = {
    "junior": re.compile(r"\b(?:junior|jr\.?|entry[- ]level|graduate)\b", re.I),
    "mid": re.compile(r"\b(?:mid[- ]level|midlevel|intermediate)\b", re.I),
    "senior": re.compile(r"\b(?:senior|sr\.?|lead|principal|staff|manager|director|head)\b", re.I),
}
SECTION_HEADERS = ["experience", "education", "skills", "projects", "certifications", "summary"]
CORE_SECTIONS = ["experience", "education", "skills"]


class UnsupportedFileType(Exception):
    pass


class ScannedPDFError(UnsupportedFileType):
    pass


def extract_text(file_path: str) -> str:
    ext = os.path.splitext(file_path)[1].lower()

    if ext == ".pdf":
        if pdfplumber is None:
            raise RuntimeError("pdfplumber is not installed. Run: pip install pdfplumber")
        chunks = []
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                chunks.append(page.extract_text() or "")
        text = "\n".join(chunks).strip()
        if not text:
            raise ScannedPDFError(
                "This PDF appears to be scanned/image-only. OCR is not enabled, so please upload a text-based PDF, DOCX, or TXT file."
            )
        return text

    if ext == ".docx":
        if docx is None:
            raise RuntimeError("python-docx is not installed. Run: pip install python-docx")
        document = docx.Document(file_path)
        return "\n".join(p.text for p in document.paragraphs)

    if ext == ".txt":
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()

    raise UnsupportedFileType(f"Unsupported file type: {ext}. Use .pdf, .docx, or .txt")


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower()).strip()


def _pattern_for(term: str):
    # Boundaries work well for word-like skills; allow punctuation-heavy terms
    # such as C++, C#, CI/CD and Node.js without false substring matches.
    escaped = re.escape(term.lower())
    if re.search(r"[^a-z0-9]", term):
        return re.compile(r"(?<![a-z0-9])" + escaped + r"(?![a-z0-9])", re.I)
    return re.compile(r"\b" + escaped + r"\b", re.I)


_SKILL_PATTERNS = {skill: _pattern_for(skill) for skill in SKILL_VOCABULARY}
_ALIAS_PATTERNS = {alias: _pattern_for(alias) for alias in SKILL_ALIASES}


def find_skills(text: str, skill_list=None) -> set:
    """Detect canonical skills and their aliases."""
    skill_list = list(skill_list or SKILL_VOCABULARY)
    text_norm = normalize(text)
    found = set()

    for skill in skill_list:
        pattern = _SKILL_PATTERNS.get(skill) or _pattern_for(skill)
        if pattern.search(text_norm):
            found.add(skill)

    # Only add aliases that resolve to skills in the requested list.
    allowed = set(skill_list)
    for alias, canonical in SKILL_ALIASES.items():
        if canonical in allowed and _ALIAS_PATTERNS[alias].search(text_norm):
            found.add(canonical)
    return found


def detect_experience_signal(text: str) -> dict:
    years = [int(x) for x in YEARS_RE.findall(text or "")]
    explicit = []
    for level, pattern in SENIORITY_RE.items():
        if pattern.search(text or ""):
            explicit.append(level)

    if explicit:
        if "senior" in explicit:
            level = "senior"
        elif "junior" in explicit:
            level = "junior"
        else:
            level = explicit[0]
        source = "seniority terms"
    elif years:
        max_years = max(years)
        level = "junior" if max_years < 2 else ("mid" if max_years < 5 else "senior")
        source = "years of experience"
    else:
        level, source = "unknown", "not detected"

    return {
        "years": max(years) if years else None,
        "level": level,
        "source": source,
        "terms": sorted(set(explicit)),
    }


def experience_modifier(signal: dict, role_info: dict) -> float:
    target = role_info.get("level", "mid")
    detected = signal.get("level", "unknown")
    if detected == "unknown":
        return 0.0
    if detected == target:
        return 5.0
    if {detected, target} == {"junior", "senior"}:
        return -5.0
    return 2.0


def resume_health_check(text: str) -> dict:
    return {
        "has_email": bool(EMAIL_RE.search(text)),
        "has_phone": bool(PHONE_RE.search(text)),
        "word_count": len(text.split()),
        "sections_found": [s for s in SECTION_HEADERS if s in text.lower()],
    }


def _weighted_match(resume_skills: set, role_info: dict) -> dict:
    required = set(role_info.get("required", role_info.get("skills", [])))
    preferred = set(role_info.get("preferred", []))
    # Backward compatibility for any old/custom role that only has "skills".
    if not required and not preferred:
        required = set(role_info.get("skills", []))

    matched_required = resume_skills & required
    matched_preferred = resume_skills & preferred
    missing_required = required - resume_skills
    missing_preferred = preferred - resume_skills

    required_ratio = len(matched_required) / len(required) if required else 0.0
    preferred_ratio = len(matched_preferred) / len(preferred) if preferred else 0.0

    if required and preferred:
        base_score = required_ratio * 70 + preferred_ratio * 30
    elif required:
        base_score = required_ratio * 100
    elif preferred:
        base_score = preferred_ratio * 100
    else:
        base_score = 0.0

    return {
        "required": sorted(required),
        "preferred": sorted(preferred),
        "matched_required": sorted(matched_required),
        "matched_preferred": sorted(matched_preferred),
        "missing_required": sorted(missing_required),
        "missing_preferred": sorted(missing_preferred),
        "base_score": base_score,
    }


def compute_role_match(resume_skills: set, role_name: str, experience=None) -> dict:
    role_info = ROLES[role_name]
    match = _weighted_match(resume_skills, role_info)
    signal = experience or {"level": "unknown"}
    modifier = experience_modifier(signal, role_info)
    score = round(max(0.0, min(100.0, match["base_score"] + modifier)), 1)
    matched = sorted(set(match["matched_required"]) | set(match["matched_preferred"]))
    missing = sorted(set(match["missing_required"]) | set(match["missing_preferred"]))

    return {
        "role": role_name,
        "description": role_info["description"],
        "score": score,
        "base_score": round(match["base_score"], 1),
        "experience_modifier": modifier,
        "matched_skills": matched,
        "matched_required": match["matched_required"],
        "matched_preferred": match["matched_preferred"],
        "missing_skills": missing,
        "missing_required": match["missing_required"],
        "missing_preferred": match["missing_preferred"],
        "skill_weights": {"required": 70 if match["preferred"] else 100, "preferred": 30 if match["preferred"] else 0},
        "level": role_info.get("level", "mid"),
    }


def match_roles(resume_text: str, top_n: int = 6) -> tuple:
    resume_skills = find_skills(resume_text, SKILL_VOCABULARY)
    experience = detect_experience_signal(resume_text)
    results = [compute_role_match(resume_skills, role_name, experience) for role_name in ROLES]
    results.sort(key=lambda r: r["score"], reverse=True)
    return results[:top_n], sorted(resume_skills)


def compute_skill_match(resume_skills: set, target_skills: set, role_name="Job Description Match", description="Pasted job description") -> dict:
    target_skills = set(target_skills)
    matched = resume_skills & target_skills
    missing = target_skills - resume_skills
    score = round(len(matched) / len(target_skills) * 100, 1) if target_skills else 0.0
    return {
        "role": role_name,
        "description": description,
        "score": score,
        "base_score": score,
        "experience_modifier": 0.0,
        "matched_skills": sorted(matched),
        "matched_required": sorted(matched),
        "matched_preferred": [],
        "missing_skills": sorted(missing),
        "missing_required": sorted(missing),
        "missing_preferred": [],
        "skill_weights": {"required": 100, "preferred": 0},
        "level": "unknown",
    }


def calculate_ats_score(text: str, health: dict, resume_skills: set, best_role_score_frac: float) -> dict:
    issues, breakdown = [], {}

    contact_pts = (8 if health["has_email"] else 0) + (7 if health["has_phone"] else 0)
    if not health["has_email"]:
        issues.append("No email address detected — add one so recruiters and ATS parsers can find you.")
    if not health["has_phone"]:
        issues.append("No phone number detected — include one near the top of your resume.")
    breakdown["contact_info"] = contact_pts

    found_core = [s for s in CORE_SECTIONS if s in health["sections_found"]]
    section_pts = len(found_core) * 6
    for s in CORE_SECTIONS:
        if s not in found_core:
            issues.append(f"Add a clearly labeled '{s.title()}' section — ATS software looks for standard headings.")
    breakdown["section_structure"] = section_pts

    wc = health["word_count"]
    if 300 <= wc <= 1100:
        length_pts = 12
    elif wc < 150:
        length_pts = 0
        issues.append("Resume looks very short — ATS and recruiters may read this as incomplete. Aim for 400-800 words.")
    elif wc < 300:
        length_pts = 6
        issues.append("Resume is on the shorter side — consider adding more detail to your experience bullets.")
    else:
        length_pts = 6
        issues.append("Resume is quite long — consider trimming to the most relevant content.")
    breakdown["length"] = length_pts

    ratio = bullet_usage_ratio(text)
    if ratio >= 0.15:
        bullet_pts = 15
    elif ratio > 0:
        bullet_pts = 8
        issues.append("Use bullet points more consistently in your experience section — ATS parsers and recruiters both scan bullets faster than paragraphs.")
    else:
        bullet_pts = 0
        issues.append("No bullet points detected — switch dense paragraphs into scannable bullet points.")
    breakdown["bullet_usage"] = bullet_pts

    variety_pts = round(min(len(resume_skills), 10) * 1.5, 1)
    if len(resume_skills) < 5:
        issues.append("Few recognizable skill keywords were found — list your tools and technologies explicitly, not just implied by job titles.")
    breakdown["keyword_variety"] = variety_pts

    role_pts = round(best_role_score_frac * 25, 1)
    breakdown["role_keyword_match"] = role_pts

    total = min(round(contact_pts + section_pts + length_pts + bullet_pts + variety_pts + role_pts, 1), 100.0)
    rating = "Excellent" if total >= 80 else ("Good" if total >= 60 else ("Needs Work" if total >= 40 else "Poor"))
    return {"score": total, "rating": rating, "breakdown": breakdown, "issues": issues}


def bullet_usage_ratio(text: str) -> float:
    lines = [l for l in text.splitlines() if l.strip()]
    if not lines:
        return 0.0
    return len([l for l in lines if BULLET_RE.match(l)]) / len(lines)


def _build_advanced_interview_questions(skill: str, role_name: str) -> list[str]:
    skill_lower = skill.lower()
    soft_markers = (
        "communication", "leadership", "teamwork", "problem solving", "stakeholder",
        "presentation", "collaboration", "negotiation", "conflict", "decision making"
    )

    if skill_lower in SOFT_SKILLS or any(marker in skill_lower for marker in soft_markers):
        return [
            f"Tell me about a time you used {skill} to influence a decision or resolve a conflict in a team setting.",
            f"How do you know when {skill} is working well in a project, and what signals do you monitor?",
            f"Describe a situation where you had to apply {skill} without authority and how you handled it.",
            f"What is your approach to improving {skill} in a fast-moving {role_name} environment?",
            f"Give an example of a trade-off you made when balancing {skill} with speed, quality, or stakeholder demands.",
        ]

    return [
        f"Walk me through a real project where you used {skill} to solve a business or technical problem.",
        f"If a production issue related to {skill} appeared unexpectedly, how would you diagnose and prioritize the root cause?",
        f"What trade-offs or design decisions do you consider when implementing {skill} at scale or in a time-sensitive environment?",
        f"How do you validate the quality and reliability of your work with {skill} before presenting it to stakeholders?",
        f"Describe a time when requirements changed while you were working with {skill}. How did you adapt and communicate the impact?",
        f"How would you explain the value of {skill} to a non-technical stakeholder in a {role_name} role?",
    ]


def _learning_profile(skill: str) -> tuple[str, str, dict]:
    skill_lower = skill.lower()
    if any(marker in skill_lower for marker in ("leadership", "communication", "negotiation", "stakeholder", "teamwork")):
        return "1-2 weeks", "Practice", {
            "beginner": "Learn the core concepts and vocabulary.",
            "intermediate": "Use it in a small team or stakeholder scenario.",
            "advanced": "Lead a complex situation and measure the outcome.",
        }
    if any(marker in skill_lower for marker in ("excel", "sql", "python", "java", "javascript", "cloud", "aws", "azure", "power bi", "tableau")):
        return "3-6 weeks", "Build", {
            "beginner": "Complete the fundamentals and guided exercises.",
            "intermediate": "Build a practical project using realistic data or workflows.",
            "advanced": "Optimize, troubleshoot, and explain production-level decisions.",
        }
    return "2-4 weeks", "Apply", {
        "beginner": "Learn the terminology, concepts, and basic workflow.",
        "intermediate": "Complete a hands-on project with feedback.",
        "advanced": "Handle edge cases and teach or lead the practice.",
    }


def build_skill_roadmap(current_skills: set, missing_skills: list, missing_required: list, missing_preferred: list, optional_skills=None) -> list:
    required = set(missing_required)
    preferred = set(missing_preferred)
    priority_rank = {"Essential": 0, "Important": 1, "Optional": 2}
    roadmap = []
    for skill in missing_skills:
        priority = "Essential" if skill in required else ("Important" if skill in preferred else "Optional")
        estimated_time, action, levels = _learning_profile(skill)
        roadmap.append({
            "skill": skill,
            "priority": priority,
            "estimated_time": estimated_time,
            "recommended_order": 0,
            "beginner": levels["beginner"],
            "intermediate": levels["intermediate"],
            "advanced": levels["advanced"],
            "action": action,
        })
    roadmap.sort(key=lambda item: (priority_rank[item["priority"]], item["skill"].lower()))
    for index, item in enumerate(roadmap, start=1):
        item["recommended_order"] = index
    return roadmap


def build_role_plan(role_name: str, resume_skills: set, ats_issues: list, experience=None) -> dict:
    match = compute_role_match(resume_skills, role_name, experience)
    missing = match["missing_skills"]
    technical_gaps = [s for s in missing if s not in SOFT_SKILLS]
    soft_gaps = [s for s in missing if s in SOFT_SKILLS]

    skill_development = [
        {"skill": s, "tip": SKILL_TIPS.get(s, f"Get hands-on with {s} through a small project or a short course — direct experience beats reading about it.")}
        for s in technical_gaps
    ]
    personal_development = [
        {"skill": s, "tip": DEV_TIPS.get(s, f"Look for chances to practice {s} in your current role, then note the outcome on your resume.")}
        for s in soft_gaps
    ]

    questions = {}
    for s in missing[:8]:
        questions[s] = _build_advanced_interview_questions(s, role_name)

    resume_changes = list(ats_issues[:3])
    if missing:
        resume_changes.append(
            f"Work these terms into your Experience or Skills section, using the exact phrasing employers use for {role_name}: "
            + ", ".join(missing[:3]) + "."
        )
    resume_changes.append(
        f"Quantify your impact (tickets closed, time saved, users affected) in your bullet points — "
        f"specific numbers stand out for {role_name} roles more than a list of duties."
    )

    return {
        **match,
        "skill_development": skill_development,
        "personal_development": personal_development,
        "resume_changes": resume_changes[:6],
        "interview_questions": questions,
        "current_skills": sorted(resume_skills),
        "skill_roadmap": build_skill_roadmap(
            resume_skills,
            missing,
            match["missing_required"],
            match["missing_preferred"],
        ),
    }


def suggest_focus_skills(role_matches: list, top_n: int = 5) -> list:
    from collections import defaultdict
    impact, unlocks = defaultdict(float), defaultdict(set)
    for role in role_matches:
        weight = 1 + (role["score"] / 100)
        for skill in role["missing_skills"]:
            impact[skill] += weight
            unlocks[skill].add(role["role"])
    ranked = sorted(impact.items(), key=lambda item: item[1], reverse=True)[:top_n]
    return [{"skill": skill, "helps_with": sorted(unlocks[skill])} for skill, _ in ranked]


def analyze_text(resume_text: str, target_role: str = None, job_description: str = None) -> dict:
    resume_text = (resume_text or "").strip()
    health = resume_health_check(resume_text)
    role_matches, detected_skills = match_roles(resume_text)
    resume_skills = set(detected_skills)
    experience = detect_experience_signal(resume_text)

    jd_skills = find_skills(job_description, SKILL_VOCABULARY) if job_description else set()
    if job_description and jd_skills:
        jd_match = compute_skill_match(resume_skills, jd_skills)
        best_frac = jd_match["score"] / 100
    elif target_role and target_role in ROLES:
        best_frac = compute_role_match(resume_skills, target_role, experience)["score"] / 100
    elif role_matches:
        best_frac = role_matches[0]["score"] / 100
    else:
        best_frac = 0.0

    ats = calculate_ats_score(resume_text, health, resume_skills, best_frac)
    result = {
        "health": health,
        "detected_skills": detected_skills,
        "roles": role_matches,
        "ats": ats,
        "resume_text": resume_text,
        "experience_signal": experience,
        "job_description_skills": sorted(jd_skills),
    }

    if job_description and jd_skills:
        result["target_plan"] = {
            **jd_match,
            "skill_development": [
                {"skill": s, "tip": SKILL_TIPS.get(s, f"Get hands-on with {s} through a small project or short course.")}
                for s in jd_match["missing_skills"]
            ],
            "personal_development": [],
            "resume_changes": [
                "Use the exact job-description skill wording where it truthfully reflects your experience.",
                f"Missing JD skills: {', '.join(jd_match['missing_skills'][:6]) or 'None'}.",
                "Quantify outcomes in your experience bullets rather than listing duties only.",
            ],
            "interview_questions": {
                s: _build_advanced_interview_questions(s, jd_match.get("role", "target role"))
                for s in jd_match["missing_skills"][:8]
            },
            "current_skills": sorted(resume_skills),
            "skill_roadmap": build_skill_roadmap(
                resume_skills,
                jd_match["missing_skills"],
                jd_match["missing_required"],
                jd_match["missing_preferred"],
            ),
        }
    elif target_role and target_role in ROLES:
        result["target_plan"] = build_role_plan(target_role, resume_skills, ats["issues"], experience)
    else:
        result["focus_skills"] = suggest_focus_skills(role_matches)

    return result


def analyze_resume(file_path: str, target_role: str = None, job_description: str = None) -> dict:
    return analyze_text(extract_text(file_path), target_role=target_role, job_description=job_description)
