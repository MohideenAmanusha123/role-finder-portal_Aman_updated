import unittest

from resume_builder import (
    normalize_resume_data,
    build_resume_text,
    calculate_builder_ats_score,
    generate_ats_pdf,
    generate_ats_docx,
)
from resume_editor import build_edited_resume, render_edited_resume_pdf, render_edited_resume_docx


SAMPLE_RESUME = {
    "personal": {
        "name": "Taylor Morgan",
        "email": "taylor.morgan@example.com",
        "phone": "+1 555 222 3333",
        "location": "Chennai, India",
        "linkedin": "https://linkedin.com/in/taylormorgan",
    },
    "summary": "Backend engineer focused on reliable APIs.",
    "skills": ["python", "sql", "docker"],
    "experience": [{
        "job_title": "Backend Engineer",
        "company": "Widget Co",
        "location": "Remote",
        "start_date": "Jan 2021",
        "end_date": "Present",
        "description": "Built and maintained REST APIs.\nImproved p99 latency by 30%.",
    }],
    "education": [{
        "degree": "B.Tech Computer Science",
        "institution": "State University",
        "location": "Chennai",
        "start_date": "2016",
        "end_date": "2020",
        "grade": "",
    }],
    "projects": [{
        "name": "Internal Dashboard",
        "description": "Built an internal metrics dashboard.",
        "technologies": ["python", "react"],
    }],
    "certifications": ["AWS Certified Developer"],
    "achievements": ["Employee of the quarter"],
    "languages": ["English", "Tamil"],
}


class ResumeBuilderSmokeTests(unittest.TestCase):
    def test_normalize_resume_data_fills_missing_fields(self):
        normalized = normalize_resume_data({"personal": {"name": "Only Name"}})
        self.assertEqual(normalized["personal"]["name"], "Only Name")
        self.assertEqual(normalized["skills"], [])
        self.assertEqual(normalized["experience"], [])

    def test_build_resume_text_includes_key_fields(self):
        normalized = normalize_resume_data(SAMPLE_RESUME)
        text = build_resume_text(normalized)
        self.assertIn("Taylor Morgan", text)
        self.assertIn("Widget Co", text)
        self.assertIn("State University", text)

    def test_calculate_builder_ats_score_returns_expected_shape(self):
        normalized = normalize_resume_data(SAMPLE_RESUME)
        result = calculate_builder_ats_score(normalized, "Python and SQL experience needed.")
        self.assertIn("score", result)
        self.assertIn("recommendations", result)
        self.assertGreaterEqual(result["score"], 0)
        self.assertLessEqual(result["score"], 100)

    def test_generate_ats_pdf_produces_nonempty_stream(self):
        normalized = normalize_resume_data(SAMPLE_RESUME)
        stream = generate_ats_pdf(normalized)
        content = stream.read()
        self.assertGreater(len(content), 0)
        self.assertTrue(content.startswith(b"%PDF"))

    def test_generate_ats_docx_produces_nonempty_stream(self):
        normalized = normalize_resume_data(SAMPLE_RESUME)
        stream = generate_ats_docx(normalized)
        content = stream.read()
        self.assertGreater(len(content), 0)
        # .docx files are zip containers.
        self.assertTrue(content.startswith(b"PK"))


class ResumeEditorSmokeTests(unittest.TestCase):
    ORIGINAL_TEXT = (
        "Summary\n"
        "Backend engineer.\n\n"
        "Skills\n"
        "Python\n\n"
        "Experience\n"
        "Backend Engineer at Widget Co\n"
    )

    def test_build_edited_resume_keep_mode_preserves_summary(self):
        result = build_edited_resume(
            self.ORIGINAL_TEXT,
            matched_skills=["python", "sql"],
            confirmed_skills=["sql"],
            applications={"sql": ["PostgreSQL"]},
            summary_mode="keep",
        )
        self.assertEqual(result["diff"]["summary_after"], result["diff"]["summary_before"])
        self.assertIn("sql", ", ".join(result["diff"]["skills_added"]).lower())

    def test_build_edited_resume_update_mode_changes_summary(self):
        result = build_edited_resume(
            self.ORIGINAL_TEXT,
            matched_skills=["python", "sql"],
            confirmed_skills=["sql"],
            summary_mode="update",
            role_name="Backend Engineer",
        )
        self.assertTrue(result["diff"]["summary_after"])

    def test_build_edited_resume_rejects_invalid_summary_mode(self):
        with self.assertRaises(ValueError):
            build_edited_resume(self.ORIGINAL_TEXT, [], [], summary_mode="not-a-real-mode")

    def test_render_edited_resume_pdf_and_docx(self):
        edited = build_edited_resume(
            self.ORIGINAL_TEXT,
            matched_skills=["python"],
            confirmed_skills=[],
            summary_mode="keep",
        )
        pdf_stream = render_edited_resume_pdf(edited)
        docx_stream = render_edited_resume_docx(edited)
        self.assertTrue(pdf_stream.read().startswith(b"%PDF"))
        self.assertTrue(docx_stream.read().startswith(b"PK"))


if __name__ == "__main__":
    unittest.main()
