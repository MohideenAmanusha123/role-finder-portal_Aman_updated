"""
resume_matcher.py
------------------
Text extraction, skill matching, weighted role scoring, JD comparison,
and experience-level signals.
"""

import os
import re
from datetime import date

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

# --- Experience-from-dates -------------------------------------------------
# Employment date ranges ("Jan 2021 - Present", "2019-2022") are a far more
# reliable signal than scanning for phrases like "5 years", which miss
# experience that's only implied by the dates themselves. This parses every
# date range found anywhere in the resume, merges overlapping spans (so two
# concurrent roles don't double-count), and sums the total months covered.
_MONTH_NAMES = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
}
_MONTH_RE = r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*"
_DATE_TOKEN_RE = rf"(?:{_MONTH_RE}[\s.,-]+)?(\d{{4}})"
_DATE_RANGE_RE = re.compile(
    rf"({_MONTH_RE}[\s.,-]+)?(\d{{4}})\s*(?:[-–—]|to|through)\s*"
    rf"(present|current|(?:{_MONTH_RE}[\s.,-]+)?\d{{4}})",
    re.I,
)


def _month_index(month_word, year_str):
    """Convert an optional month name + a year string into an absolute
    month index (year*12 + month), defaulting to June when no month is
    given so a bare year doesn't systematically bias toward either end
    of that year.
    """
    year = int(year_str)
    month = 6
    if month_word:
        # "sept" is the only month name where the first-3-letters key
        # ("sep") is ambiguous with "sep" itself, both map to the same
        # index anyway, so a straightforward first-3-letters lookup is
        # safe for every month name this regex can capture.
        key = re.sub(r"[^a-z]", "", month_word.lower())[:3]
        month = _MONTH_NAMES.get(key, 6)
    return year * 12 + month


def _years_from_date_ranges(text: str):
    """Return (total_years, range_count) from every employment-style date
    range found in the text, or (None, 0) if none were found. Overlapping
    ranges (e.g. two roles held concurrently, or an internship inside a
    degree's date range) are merged rather than summed, so total months
    reflect calendar time covered, not raw addition.
    """
    if not text:
        return None, 0

    today_index = date.today().year * 12 + date.today().month
    intervals = []

    for match in _DATE_RANGE_RE.finditer(text):
        start_month_word, start_year, end_raw = match.group(1), match.group(2), match.group(3)
        start_index = _month_index(start_month_word, start_year)

        if end_raw.lower() in ("present", "current"):
            end_index = today_index
        else:
            end_match = re.match(rf"(?:({_MONTH_RE})[\s.,-]+)?(\d{{4}})", end_raw, re.I)
            if not end_match:
                continue
            end_index = _month_index(end_match.group(1), end_match.group(2))

        if end_index < start_index:
            continue  # malformed/reversed range -- skip rather than guess
        if end_index - start_index > 720:  # sanity cap: no single range > 60 years
            continue
        intervals.append((start_index, end_index))

    if not intervals:
        return None, 0

    intervals.sort()
    merged = [intervals[0]]
    for start, end in intervals[1:]:
        last_start, last_end = merged[-1]
        if start <= last_end:
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))

    total_months = sum(end - start for start, end in merged)
    return round(total_months / 12, 1), len(intervals)


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
        MAX_PAGES = 40  # resumes are short; this bounds worst-case extraction time
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages[:MAX_PAGES]:
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
    # A short list of single-token skill names that are also common,
    # everyday English words in a form the "s"/"es" suffix would produce
    # (e.g. "go" -> "goes", the verb) -- these keep exact matching only,
    # so the plural-tolerance above doesn't trade a false negative for a
    # much more likely false positive.
    _PLURAL_SUFFIX_DENYLIST = {"go"}
    if term.lower() in _PLURAL_SUFFIX_DENYLIST:
        return re.compile(r"\b" + escaped + r"\b", re.I)
    # Single-token skills (no spaces, no punctuation) tolerate a trailing
    # "s" or "es" -- this is deliberately NOT semantic/embedding matching
    # (that would need a paid API call per analysis, undermining the
    # rate-limiting/cost-control work done elsewhere); it's a small,
    # deterministic widening of exact matching to catch the single most
    # common miss: someone writing the plural ("APIs", "dashboards") where
    # the vocabulary entry is singular. Multi-word phrases are left exact,
    # since guessing at plural boundaries inside a phrase risks false
    # positives that a single trailing "s" on one word does not.
    return re.compile(r"\b" + escaped + r"(?:es|s)?\b", re.I)


_SKILL_PATTERNS = {skill: _pattern_for(skill) for skill in SKILL_VOCABULARY}
_ALIAS_PATTERNS = {alias: _pattern_for(alias) for alias in SKILL_ALIASES}

# --- Context validation (the third layer, after exact + alias matching) ---
# A skill keyword appearing in the text isn't automatically evidence the
# person has it -- "no experience with Kubernetes" or "not proficient in
# SQL" contain the keyword but mean the opposite. This scans a short window
# of text immediately before each match for a negation cue, and only
# discards *that* occurrence -- if the same skill is mentioned elsewhere in
# the resume without a negation nearby, it still counts.
_NEGATION_RE = re.compile(
    r"\b("
    r"no|not|never|without|"
    r"(?:no|without|lacking?|limited)\s+(?:prior\s+)?(?:hands[- ]on\s+)?"
    r"(?:knowledge|experience|exposure|familiarity)\s+(?:of|with|in)?|"
    r"lack\s+of\s+(?:experience|knowledge)\s*(?:with|in|of)?|"
    r"not\s+(?:yet\s+)?(?:proficient|familiar|experienced|skilled|comfortable)\s+(?:with|in)|"
    r"unfamiliar\s+with"
    r")\s*$",
    re.I,
)
_NEGATION_WINDOW_CHARS = 45


def _has_non_negated_match(pattern, text: str) -> bool:
    """True if `pattern` matches `text` at least once without a negation
    cue in the preceding ~45 characters. Checks every occurrence, not just
    the first, so one negated mention doesn't hide a genuine one elsewhere.
    """
    for match in pattern.finditer(text):
        window_start = max(0, match.start() - _NEGATION_WINDOW_CHARS)
        preceding = text[window_start:match.start()]
        if _NEGATION_RE.search(preceding):
            continue
        return True
    return False


def find_skills(text: str, skill_list=None) -> set:
    """Detect canonical skills and their aliases.

    Three layers, in order: (1) exact vocabulary match, (2) alias/synonym
    match, (3) context validation -- a match preceded by a negation cue
    ("no experience with X") is not counted as evidence of that skill.
    Deliberately does not add a fourth, semantic/embedding layer -- see the
    comment on plural-tolerance in _pattern_for() for why that trade-off
    isn't made here.
    """
    skill_list = list(skill_list or SKILL_VOCABULARY)
    text_norm = normalize(text)
    found = set()

    for skill in skill_list:
        pattern = _SKILL_PATTERNS.get(skill) or _pattern_for(skill)
        if _has_non_negated_match(pattern, text_norm):
            found.add(skill)

    # Only add aliases that resolve to skills in the requested list.
    allowed = set(skill_list)
    for alias, canonical in SKILL_ALIASES.items():
        if canonical in allowed and _has_non_negated_match(_ALIAS_PATTERNS[alias], text_norm):
            found.add(canonical)
    return found


def detect_experience_signal(text: str) -> dict:
    years = [int(x) for x in YEARS_RE.findall(text or "")]
    explicit = []
    for level, pattern in SENIORITY_RE.items():
        if pattern.search(text or ""):
            explicit.append(level)

    date_years, date_range_count = _years_from_date_ranges(text or "")

    # Prefer years calculated from actual employment date ranges over a
    # bare phrase like "5 years" -- dates are what the person actually
    # wrote down as fact, a phrase is more easily stale or exaggerated.
    # Only fall back to the phrase-based figure when no date ranges were
    # found at all.
    if date_years is not None:
        effective_years = date_years
        years_source = "employment dates"
    elif years:
        effective_years = max(years)
        years_source = "years of experience"
    else:
        effective_years = None
        years_source = None

    if explicit:
        if "senior" in explicit:
            level = "senior"
        elif "junior" in explicit:
            level = "junior"
        else:
            level = explicit[0]
        source = "seniority terms"
    elif effective_years is not None:
        level = "junior" if effective_years < 2 else ("mid" if effective_years < 5 else "senior")
        source = years_source
    else:
        level, source = "unknown", "not detected"

    return {
        "years": effective_years,
        "level": level,
        "source": source,
        "terms": sorted(set(explicit)),
        "date_ranges_found": date_range_count,
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

    # Configurable per role (see roles_data.py / a custom role's "weights"),
    # defaulting to 70/30 for any role that doesn't specify one. This was
    # previously hardcoded here, meaning every role -- regardless of how
    # much precision vs. breadth actually matters for it -- was scored the
    # same way with no way to see or change that.
    weights = role_info.get("weights") or {}
    required_weight = weights.get("required", 70)
    preferred_weight = weights.get("preferred", 30)

    if required and preferred:
        base_score = required_ratio * required_weight + preferred_ratio * preferred_weight
        weights_used = {"required": required_weight, "preferred": preferred_weight}
    elif required:
        base_score = required_ratio * 100
        weights_used = {"required": 100, "preferred": 0}
    elif preferred:
        base_score = preferred_ratio * 100
        weights_used = {"required": 0, "preferred": 100}
    else:
        base_score = 0.0
        weights_used = {"required": 0, "preferred": 0}

    return {
        "required": sorted(required),
        "preferred": sorted(preferred),
        "matched_required": sorted(matched_required),
        "matched_preferred": sorted(matched_preferred),
        "missing_required": sorted(missing_required),
        "missing_preferred": sorted(missing_preferred),
        "base_score": base_score,
        "weights_used": weights_used,
    }


def compute_role_match(resume_skills: set, role_name: str, experience=None, roles: dict = None) -> dict:
    role_catalog = roles if roles is not None else ROLES
    role_info = role_catalog[role_name]
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
        "skill_weights": match["weights_used"],
        "level": role_info.get("level", "mid"),
    }


def match_roles(resume_text: str, top_n: int = None, roles: dict = None) -> tuple:
    role_catalog = roles if roles is not None else ROLES
    resume_skills = find_skills(resume_text, SKILL_VOCABULARY)
    experience = detect_experience_signal(resume_text)
    results = [compute_role_match(resume_skills, role_name, experience, roles=role_catalog) for role_name in role_catalog]
    results.sort(key=lambda r: r["score"], reverse=True)
    if top_n is None:
        return results, sorted(resume_skills)
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
            f"Describe a project where effective {skill} changed the outcome for the team or customer.",
            f"When {skill} was difficult with a stakeholder, how did you adapt your communication and keep momentum?",
            f"How do you decide when to escalate an issue that requires more {skill} than a single team member can provide?",
            f"What do you do when a team member disagrees with your approach to {skill} and you still need alignment?",
            f"How have you coached or supported someone else to improve their {skill} in practice?",
            f"What metrics or signals tell you that your {skill} is adding value in a role like {role_name}?",
            f"Tell me about a time you had to balance empathy, urgency, and clarity while applying {skill}.",
        ]

    return [
        f"Walk me through a real project where you used {skill} to solve a business or technical problem.",
        f"If a production issue related to {skill} appeared unexpectedly, how would you diagnose and prioritize the root cause?",
        f"What trade-offs or design decisions do you consider when implementing {skill} at scale or in a time-sensitive environment?",
        f"How do you validate the quality and reliability of your work with {skill} before presenting it to stakeholders?",
        f"Describe a time when requirements changed while you were working with {skill}. How did you adapt and communicate the impact?",
        f"How would you explain the value of {skill} to a non-technical stakeholder in a {role_name} role?",
        f"What would you do if the dataset or system conditions around {skill} changed unexpectedly mid-project?",
        f"Give an example where you improved efficiency or accuracy by using {skill} differently than the original process.",
        f"How do you document and maintain quality when working with {skill} across multiple stakeholders or environments?",
        f"Tell me about a time you had to troubleshoot or recover from a mistake involving {skill}.",
        f"Which metrics or outcomes do you use to show that {skill} is actually improving business or operational performance?",
        f"If you had to onboard a new teammate to your workflow around {skill}, how would you structure the training?",
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


def build_role_plan(role_name: str, resume_skills: set, ats_issues: list, experience=None, roles: dict = None) -> dict:
    match = compute_role_match(resume_skills, role_name, experience, roles=roles)
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


def analyze_text(resume_text: str, target_role: str = None, job_description: str = None, roles: dict = None) -> dict:
    role_catalog = roles if roles is not None else ROLES
    resume_text = (resume_text or "").strip()
    health = resume_health_check(resume_text)
    role_matches, detected_skills = match_roles(resume_text, roles=role_catalog)
    resume_skills = set(detected_skills)
    experience = detect_experience_signal(resume_text)

    jd_skills = find_skills(job_description, SKILL_VOCABULARY) if job_description else set()
    if job_description and jd_skills:
        jd_match = compute_skill_match(resume_skills, jd_skills)
        best_frac = jd_match["score"] / 100
    elif target_role and target_role in role_catalog:
        best_frac = compute_role_match(resume_skills, target_role, experience, roles=role_catalog)["score"] / 100
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
    elif target_role and target_role in role_catalog:
        result["target_plan"] = build_role_plan(target_role, resume_skills, ats["issues"], experience, roles=role_catalog)
    else:
        result["focus_skills"] = suggest_focus_skills(role_matches)

    return result


def analyze_resume(file_path: str, target_role: str = None, job_description: str = None, roles: dict = None) -> dict:
    return analyze_text(extract_text(file_path), target_role=target_role, job_description=job_description, roles=roles)
