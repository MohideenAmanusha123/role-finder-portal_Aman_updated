# lailnext — Resume intelligence

A Flask resume-analysis app that supports role matching, ATS scoring, pasted job descriptions, weighted skills, experience-level signals, improvement tracking, interview prep, and conservative resume editing.

## Updated capabilities

- **Skill aliases:** `js`, `k8s`, `mongo`, `postgres`, `restful api`, `powerbi`, etc. normalize to canonical skills.
- **Weighted skills:** roles separate `required` and `preferred` skills. Required skills carry 70% of the role score when both tiers exist; preferred skills carry 30%.
- **Experience signal:** detects years (`4 years`, `5+ years`) and seniority wording (`junior`, `senior`, `lead`, etc.). A small modifier is applied to role fit; it never overrides skills.
- **Paste-a-JD mode:** upload a resume and paste a job description to extract recognized JD skills and compare them directly.
- **Before/after tracking:** the browser keeps the previous ATS score and detected skills for each filename and shows the score delta on the next analysis.
- **Diff/preview:** improved resumes show a full resume-paper preview and a summary diff before download. The user must explicitly confirm the final PDF or Word download.
- **Custom roles:** a pasted JD can be saved as a named custom role. It is added to `roles_data.py` and the current process immediately.
- **Interview prep:** missing skills generate up to three likely interview questions each.
- **Applications/tools:** common applications are mapped to skills. The user must explicitly confirm applications they have actually used.
- **Summary choices:** users can keep the existing Summary, update it for the selected role and confirmed skills/experience, or use an optional AI-assisted summary.
- **AI-assisted summary:** uses OpenAI by default. Set `OPENAI_API_KEY` on the server and optionally override `OPENAI_API_URL` or `OPENAI_MODEL`. Local Ollama remains available by setting `AI_PROVIDER=ollama`, `OLLAMA_MODEL`, and `OLLAMA_URL`.
- **Broader roles:** role matching includes financial, accounting, business analysis, operations, sales/marketing, and HR roles alongside technical roles.
- **Manual skills:** the confirmation step accepts skills typed under “Add a skill manually” for skills outside the built-in vocabulary.
- **Output naming:** `ayman.pdf` → `ayman_improved_resume.pdf`; `ayman.docx` → `ayman_improved_resume.docx`.
- **PDF safety:** scanned/image-only PDFs produce a clear OCR-not-enabled error.
- **Debug:** Flask debug mode is controlled with `FLASK_DEBUG=1`; it is off by default.
- **URL state:** the selected target role is persisted in `?role=...`.

## Run

```bash
python -m venv venv
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

pip install -r requirements.txt
python app.py
```

Open `http://127.0.0.1:5000`.

For OpenAI summary generation:

1. Create an API key at https://platform.openai.com/api-keys.
2. Set the key as an environment variable. In PowerShell:

```powershell
$env:OPENAI_API_KEY="your-api-key-here"
```

3. Start the application:

```powershell
python app.py
```

For Render, open your web service's **Environment** settings and add:

```text
AI_PROVIDER=openai
OPENAI_API_KEY=your-api-key-here
OPENAI_MODEL=gpt-4o-mini
```

Save the variables and redeploy the service. Never commit the API key to GitHub.

To use local Ollama instead, set `AI_PROVIDER=ollama` and follow the Ollama setup separately.

For local debugging:

```bash
FLASK_DEBUG=1 python app.py
```

## Project files

- `app.py` — Flask routes and filename/download handling.
- `resume_matcher.py` — extraction, alias matching, weighted role scoring, JD matching, ATS scoring, experience detection.
- `roles_data.py` — skill vocabulary, aliases, application mappings, role tiers, tips, and custom-role persistence.
- `resume_editor.py` — conservative Skills/Summary editing plus preview diff and PDF/DOCX rendering.
- `pdf_report.py` — printable analysis report.
- `templates/index.html` — upload, JD, confirmation, preview and results UI.
- `static/script.js` — interactive workflow, local before/after tracking and downloads.
- `static/style.css` — visual styling.
