"""
roles_data.py
--------------
Defines the roles this portal can match a resume against, and the skill
vocabulary used to detect skills inside resume text.

To add a new role: add an entry to ROLES with a "skills" list (drawn from,
or extending, SKILL_VOCABULARY) and a one-line "description".
"""

import json
import os

# Master list of recognizable skills/keywords across roles.
# Extend this as you add more roles or want finer-grained matching.
SKILL_VOCABULARY = [
    "python", "java", "javascript", "typescript", "c++", "c#", "go", "sql", "nosql",
    "react", "angular", "vue", "node.js", "express", "django", "flask", "spring",
    "aws", "azure", "gcp", "docker", "kubernetes", "terraform", "ansible",
    "git", "ci/cd", "jenkins", "linux", "bash", "rest api", "graphql", "microservices",
    "machine learning", "deep learning", "data analysis", "data visualization",
    "pandas", "numpy", "tensorflow", "pytorch", "scikit-learn", "statistics",
    "excel", "power bi", "tableau", "sql server", "etl", "data pipelines",
    "agile", "scrum", "jira", "confluence", "project management", "roadmapping",
    "stakeholder management", "product strategy", "user research", "a/b testing",
    "communication", "leadership", "problem solving", "customer support",
    "ticketing systems", "zendesk", "salesforce", "crm", "customer success",
    "onboarding", "account management", "html", "css", "sass", "figma",
    "ui design", "ux design", "responsive design", "accessibility",
    "mongodb", "mysql", "postgresql", "redis", "unit testing", "test automation",
    "selenium", "manual testing", "bug tracking", "api testing", "load testing",
    "network administration", "windows server", "active directory", "vmware",
    "monitoring", "incident management", "sla management", "escalation handling",
    "financial analysis", "financial reporting", "budgeting", "forecasting",
    "accounting", "bookkeeping", "auditing", "risk management", "compliance",
    "procurement", "business analysis", "operations management", "sales",
    "marketing", "content writing", "recruiting", "human resources",
    "process improvement", "conflict resolution",
]

# Skills that are behavioral/interpersonal rather than tool-based — used to
# split a role's missing skills into "skill development" vs "personal
# development" recommendations.
SOFT_SKILLS = {
    "communication", "leadership", "problem solving", "stakeholder management",
    "user research", "project management", "account management", "customer success",
    "onboarding", "escalation handling", "sla management", "incident management",
    "agile", "scrum", "a/b testing", "roadmapping", "product strategy",
    "customer support",
}

# Concrete, hands-on suggestions for closing a technical/tool skill gap.
# Skills not listed here fall back to a generic template.
SKILL_TIPS = {
    "sql": "Practice writing queries against a real dataset — joins, aggregations, and window functions come up constantly in interviews.",
    "python": "Build one small end-to-end script or automation (e.g. a report generator) — a working project speaks louder than a bullet point.",
    "git": "Get comfortable with branches, merges, and pull requests — most teams expect this as table stakes, not a taught skill.",
    "docker": "Containerize one of your own projects, even a simple one, so you can speak to it concretely in interviews.",
    "kubernetes": "Start with a managed cluster (e.g. a free-tier GKE/EKS trial) and deploy a small containerized app to see the concepts in action.",
    "aws": "Work through AWS's free-tier tutorials for the services relevant to this role (EC2, S3, Lambda) rather than just reading about them.",
    "azure": "Use Azure's free-tier sandbox to complete one hands-on module relevant to this role.",
    "gcp": "Use Google Cloud's free-tier credits to complete one hands-on project.",
    "rest api": "Build or consume a small REST API, even a toy project, so you can talk through request/response design confidently.",
    "linux": "Spend time in a Linux terminal daily — navigating, permissions, process management — until it's second nature.",
    "bash": "Automate one repetitive task you already do manually with a short shell script.",
    "excel": "Practice pivot tables, VLOOKUP/XLOOKUP, and core formulas on a real dataset until they're fast, not fiddly.",
    "tableau": "Build one dashboard from a public dataset end-to-end so you have a concrete example ready to discuss.",
    "power bi": "Build one report from a public dataset so you have a real example to walk through.",
    "selenium": "Automate a test for a simple public website to get hands-on with locators and waits.",
    "jira": "Use Jira, or a free equivalent, to track a personal project — boards, sprints, and issue types.",
    "figma": "Recreate an interface you like in Figma to build fluency with components and layout.",
    "zendesk": "If you don't have access to Zendesk, walk through its documentation and trial account to learn the ticket workflow.",
}

# Suggestions for building a soft/behavioral skill through everyday practice.
DEV_TIPS = {
    "communication": "Look for chances to present or write summaries for non-technical stakeholders — it's the fastest way to build this skill visibly.",
    "leadership": "Volunteer to lead a small project or mentor a colleague, even informally, and note the outcome on your resume.",
    "problem solving": "Keep a short log of tricky problems you've solved and how — concrete examples matter more than the label itself.",
    "stakeholder management": "Practice by managing communication for a cross-team task, even a small one, and document how you kept people aligned.",
    "user research": "Run a handful of informal user interviews or feedback sessions on any project you're involved in.",
    "project management": "Take ownership of planning and tracking one project end-to-end, however small.",
    "account management": "Take on ownership of a client or internal relationship, even informally, and track the outcomes.",
    "customer success": "Look for chances to follow up with customers after their issue is resolved, to build a habit of proactive care.",
    "onboarding": "Volunteer to help onboard a new teammate or customer and document the process you used.",
    "escalation handling": "Ask to shadow or take on escalated tickets to build direct experience handling high-stakes issues.",
    "sla management": "Track your own response/resolution times against a target for a few weeks to build the habit.",
    "incident management": "Volunteer for on-call or incident-response rotations if available, even in a supporting role.",
    "agile": "Join or observe a few sprint ceremonies — standups, retros, planning — to get comfortable with the rhythm.",
    "scrum": "Look for exposure to a Scrum team's ceremonies, or a short certification if it's genuinely useful for the role.",
    "a/b testing": "Run a small experiment, even on a side project, to get hands-on with hypothesis framing and reading results.",
    "roadmapping": "Practice by sketching a rough roadmap for a project you're close to, even informally.",
    "product strategy": "Practice articulating the 'why' behind a product decision you've observed or been part of.",
    "customer support": "Take on a few support tickets or customer questions directly, even outside your usual role, to build direct experience.",
}

ROLES = {
    "Technical Support Engineer": {
        "description": "Front-line troubleshooting, ticket resolution, and customer-facing technical help.",
        "level": "mid",
        "required": ["customer support", "ticketing systems", "sql", "rest api", "communication", "problem solving", "incident management", "escalation handling"],
        "preferred": ["zendesk", "linux", "bash", "jira"],
    },
    "Backend Developer": {
        "description": "Building and maintaining server-side logic, APIs, and databases.",
        "level": "mid",
        "required": ["python", "java", "sql", "nosql", "rest api", "git", "unit testing"],
        "preferred": ["node.js", "graphql", "microservices", "docker", "postgresql", "mongodb", "redis"],
    },
    "Frontend Developer": {
        "description": "Building user-facing interfaces and interactive web experiences.",
        "level": "mid",
        "required": ["javascript", "typescript", "react", "html", "css", "responsive design", "git"],
        "preferred": ["angular", "vue", "sass", "accessibility", "figma"],
    },
    "DevOps Engineer": {
        "description": "Automating infrastructure, deployment pipelines, and system reliability.",
        "level": "mid",
        "required": ["aws", "docker", "kubernetes", "terraform", "ci/cd", "linux", "git", "monitoring"],
        "preferred": ["azure", "gcp", "ansible", "jenkins", "bash"],
    },
    "Data Analyst": {
        "description": "Turning raw data into reports and insights that drive decisions.",
        "level": "junior",
        "required": ["sql", "excel", "data analysis", "statistics", "data visualization"],
        "preferred": ["power bi", "tableau", "python", "pandas", "numpy", "etl", "data pipelines"],
    },
    "HR Executive": {
        "description": "Managing recruitment, employee support, compliance, and people operations with strong stakeholder coordination.",
        "level": "mid",
        "required": ["human resources", "recruiting", "communication", "stakeholder management", "compliance", "conflict resolution"],
        "preferred": ["onboarding", "project management", "excel", "conflict resolution"],
    },
    "Operations Coordinator": {
        "description": "Keeping teams, workflows, and service processes efficient, organized, and aligned with business goals.",
        "level": "mid",
        "required": ["operations management", "process improvement", "project management", "communication", "excel", "problem solving"],
        "preferred": ["sla management", "procurement", "budgeting", "business analysis", "stakeholder management"],
    },
    "QA Engineer": {
        "description": "Ensuring software quality through manual and automated testing.",
        "level": "mid",
        "required": ["manual testing", "test automation", "bug tracking", "api testing", "sql", "git"],
        "preferred": ["selenium", "load testing", "jira"],
    },
    "Product Manager": {
        "description": "Defining product direction and coordinating teams to ship it.",
        "level": "mid",
        "required": ["product strategy", "roadmapping", "stakeholder management", "user research", "communication", "leadership"],
        "preferred": ["a/b testing", "agile", "scrum", "jira"],
    },
    "Customer Success Manager": {
        "description": "Driving retention and growth through strong customer relationships.",
        "level": "mid",
        "required": ["customer success", "account management", "onboarding", "communication", "stakeholder management", "problem solving"],
        "preferred": ["crm", "salesforce"],
    },
    "System Administrator": {
        "description": "Maintaining servers, networks, and IT infrastructure.",
        "level": "mid",
        "required": ["linux", "windows server", "active directory", "network administration", "monitoring", "incident management"],
        "preferred": ["vmware", "bash", "sla management"],
    },
    "Machine Learning Engineer": {
        "description": "Building and deploying models that learn from data.",
        "level": "mid",
        "required": ["python", "machine learning", "deep learning", "tensorflow", "pytorch", "scikit-learn", "pandas", "numpy"],
        "preferred": ["statistics", "sql", "docker"],
    },
    "Financial Analyst": {
        "description": "Analyzing financial performance, budgets, forecasts, and business decisions.",
        "level": "mid",
        "required": ["excel", "financial analysis", "financial reporting", "budgeting", "forecasting", "communication"],
        "preferred": ["accounting", "power bi", "data visualization", "sql", "business analysis"],
    },
    "Accountant": {
        "description": "Preparing accurate financial records, reconciliations, and compliance reports.",
        "level": "mid",
        "required": ["accounting", "bookkeeping", "excel", "financial reporting", "auditing", "compliance"],
        "preferred": ["financial analysis", "budgeting", "forecasting", "sql"],
    },
    "Business Analyst": {
        "description": "Translating business needs into measurable processes, requirements, and improvements.",
        "level": "mid",
        "required": ["business analysis", "data analysis", "communication", "stakeholder management", "problem solving"],
        "preferred": ["sql", "excel", "project management", "process improvement", "jira"],
    },
    "Operations Manager": {
        "description": "Improving day-to-day operations, service delivery, and team performance.",
        "level": "mid",
        "required": ["operations management", "project management", "communication", "leadership", "problem solving"],
        "preferred": ["budgeting", "procurement", "sla management", "excel", "business analysis"],
    },
    "Sales and Marketing Professional": {
        "description": "Growing customer relationships, pipeline, and brand engagement through commercial strategy.",
        "level": "mid",
        "required": ["sales", "communication", "customer success", "account management", "problem solving"],
        "preferred": ["marketing", "crm", "salesforce", "content writing", "data analysis"],
    },
    "Human Resources Specialist": {
        "description": "Supporting recruitment, employee relations, onboarding, and people operations.",
        "level": "mid",
        "required": ["human resources", "recruiting", "communication", "onboarding", "stakeholder management"],
        "preferred": ["project management", "compliance", "excel", "conflict resolution"],
    },
}

# Backward-compatible application/tool aliases. Aliases normalize shorthand and
# common application wording to a canonical skill.
SKILL_ALIASES = {
    "js": "javascript",
    "ts": "typescript",
    "k8s": "kubernetes",
    "mongo": "mongodb",
    "postgres": "postgresql",
    "postgres db": "postgresql",
    "ms excel": "excel",
    "microsoft excel": "excel",
    "powerbi": "power bi",
    "restful api": "rest api",
    "restful apis": "rest api",
    "ci cd": "ci/cd",
    "continuous integration": "ci/cd",
    "continuous deployment": "ci/cd",
}

# Applications/tools associated with a canonical skill. These are presented for
# user confirmation; the matcher never assumes that a user has used them.
SKILL_APPLICATIONS = {
    "excel": ["Microsoft Excel", "Google Sheets", "LibreOffice Calc"],
    "sql": ["MySQL", "PostgreSQL", "Microsoft SQL Server", "Oracle Database"],
    "python": ["VS Code", "PyCharm", "Jupyter Notebook"],
    "javascript": ["VS Code", "Node.js", "Chrome DevTools"],
    "java": ["IntelliJ IDEA", "Eclipse", "Maven"],
    "docker": ["Docker Desktop", "Docker Compose"],
    "kubernetes": ["kubectl", "Minikube", "Amazon EKS", "Google GKE"],
    "aws": ["AWS Console", "AWS CLI"],
    "azure": ["Azure Portal", "Azure CLI"],
    "gcp": ["Google Cloud Console", "gcloud CLI"],
    "git": ["GitHub", "GitLab", "Bitbucket"],
    "jira": ["Jira", "Jira Service Management"],
    "zendesk": ["Zendesk Support"],
    "power bi": ["Microsoft Power BI"],
    "tableau": ["Tableau Desktop", "Tableau Cloud"],
    "mongodb": ["MongoDB Compass", "MongoDB Atlas"],
    "postgresql": ["pgAdmin", "psql"],
    "mysql": ["MySQL Workbench"],
    "terraform": ["Terraform CLI", "HCP Terraform"],
    "jenkins": ["Jenkins"],
    "selenium": ["Selenium WebDriver"],
    "react": ["React DevTools", "Vite"],
    "node.js": ["npm", "Node.js"],
    "figma": ["Figma"],
}

# Keep the old "skills" field available to callers while making required vs
# preferred explicit for weighted scoring.
for _role_info in ROLES.values():
    _role_info["skills"] = list(dict.fromkeys(_role_info["required"] + _role_info.get("preferred", [])))


CUSTOM_ROLES_FILE = os.path.join(os.path.dirname(__file__), "custom_roles.json")


def _load_custom_roles(custom_roles_path=None):
    path = custom_roles_path or CUSTOM_ROLES_FILE
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def _save_custom_roles(custom_roles, custom_roles_path=None):
    path = custom_roles_path or CUSTOM_ROLES_FILE
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(custom_roles, handle, indent=2, ensure_ascii=False)


for _custom_name, _custom_info in _load_custom_roles().items():
    normalized = {
        "description": _custom_info.get("description", f"Custom role created from a pasted job description ({len(_custom_info.get('required', []))} recognized skills)."),
        "level": _custom_info.get("level", "mid"),
        "required": list(_custom_info.get("required", [])),
        "preferred": list(_custom_info.get("preferred", [])),
        "skills": list(_custom_info.get("skills", _custom_info.get("required", []))),
        "custom": True,
    }
    ROLES[_custom_name] = normalized


def add_custom_role(role_name: str, jd_text: str, extracted_skills=None, custom_roles_path=None) -> dict:
    """Add a JD-derived role to ROLES and persist it to a JSON file."""
    import re as _re
    clean_name = _re.sub(r"\s+", " ", (role_name or "").strip())[:80]
    if not clean_name:
        raise ValueError("Role name is required.")
    skills = sorted(set(extracted_skills or []))
    if not skills:
        raise ValueError("No recognized skills were found in the job description.")
    info = {
        "description": f"Custom role created from a pasted job description ({len(skills)} recognized skills).",
        "level": "mid",
        "required": skills,
        "preferred": [],
        "skills": skills,
        "custom": True,
    }
    ROLES[clean_name] = info

    custom_roles = _load_custom_roles(custom_roles_path)
    custom_roles[clean_name] = info
    _save_custom_roles(custom_roles, custom_roles_path)
    return {"role": clean_name, "skills": skills, "description": info["description"]}
