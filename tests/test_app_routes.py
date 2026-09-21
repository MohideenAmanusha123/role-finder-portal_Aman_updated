import io
import unittest

import app as app_module
from extensions import limiter


def _sample_resume_text():
    return (
        "Jordan Lee\n"
        "jordan.lee@example.com | +1 555 000 1111\n\n"
        "Summary\n"
        "Backend engineer with experience shipping production APIs.\n\n"
        "Skills\n"
        "Python, SQL, Docker\n\n"
        "Experience\n"
        "Backend Engineer | Widget Co\n"
        "Jan 2021 - Present\n"
        "Built and maintained REST APIs.\n\n"
        "Education\n"
        "B.Tech Computer Science\n"
        "State University\n"
        "2016 - 2020\n"
    )


class RoleFinderRouteTests(unittest.TestCase):
    """Uses Flask's test client, which gives each `app.test_client()` call
    its own cookie jar -- exactly the "two different visitors" scenario the
    session-scoped custom-role fix needs to hold up under.
    """

    def setUp(self):
        app_module.app.config["TESTING"] = True
        # The rate limiter's storage is process-global, not per test class,
        # so without resetting it here, a deliberate rate-limit-flood test
        # in this file (test_custom_role_route_is_rate_limited) can exhaust
        # quota that a completely unrelated test file then hits as a
        # spurious 429. Reset before every test so each one starts clean.
        limiter.reset()

    def test_index_loads(self):
        client = app_module.app.test_client()
        client.get("/continue-as-guest")  # index() gates on auth-or-guest since /login became the landing page
        resp = client.get("/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"lailnext", resp.data)

    def test_index_redirects_anonymous_non_guest_visitors_to_login(self):
        client = app_module.app.test_client()
        resp = client.get("/", follow_redirects=False)
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/login", resp.headers["Location"])

    def test_analyze_text_basic_flow(self):
        client = app_module.app.test_client()
        resp = client.post("/analyze-text", json={
            "resume_text": _sample_resume_text(),
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("ats", data)
        self.assertIn("roles", data)
        self.assertIn("python", data.get("detected_skills", []))

    def test_analyze_text_requires_resume_text(self):
        client = app_module.app.test_client()
        resp = client.post("/analyze-text", json={"resume_text": ""})
        self.assertEqual(resp.status_code, 400)

    # --- Custom role session isolation -----------------------------------

    def test_custom_role_is_scoped_to_the_creating_session(self):
        client_a = app_module.app.test_client()
        client_b = app_module.app.test_client()

        resp = client_a.post("/custom-role", json={
            "role_name": "Isolation Test Role",
            "job_description": "Python, SQL, Docker required.",
        })
        self.assertEqual(resp.status_code, 200)

        # Creator sees it in their own role list.
        client_a.get("/continue-as-guest")
        homepage_a = client_a.get("/")
        self.assertIn(b"Isolation Test Role", homepage_a.data)

        # A different session must NOT see it.
        client_b.get("/continue-as-guest")
        homepage_b = client_b.get("/")
        self.assertNotIn(b"Isolation Test Role", homepage_b.data)

        # And the global catalog must be untouched.
        from roles_data import ROLES
        self.assertNotIn("Isolation Test Role", ROLES)

    def test_custom_role_can_be_used_as_a_target_role(self):
        client = app_module.app.test_client()
        client.post("/custom-role", json={
            "role_name": "Route Test Role",
            "job_description": "Python, SQL, Docker required.",
        })
        resp = client.post("/analyze-text", json={
            "resume_text": _sample_resume_text(),
            "target_role": "Route Test Role",
        })
        data = resp.get_json()
        self.assertEqual(data.get("target_plan", {}).get("role"), "Route Test Role")

    def test_custom_role_requires_name_and_description(self):
        client = app_module.app.test_client()
        resp = client.post("/custom-role", json={"role_name": "", "job_description": ""})
        self.assertEqual(resp.status_code, 400)

    # --- File safety -------------------------------------------------------

    def test_import_resume_rejects_spoofed_extension(self):
        client = app_module.app.test_client()
        fake_pdf = (io.BytesIO(b"not actually a pdf"), "resume.pdf")
        resp = client.post(
            "/import-resume",
            data={"resume": fake_pdf},
            content_type="multipart/form-data",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(resp.get_json()["success"])

    def test_import_resume_accepts_plain_text(self):
        client = app_module.app.test_client()
        text_file = (io.BytesIO(_sample_resume_text().encode()), "resume.txt")
        resp = client.post(
            "/import-resume",
            data={"resume": text_file},
            content_type="multipart/form-data",
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["resume"]["personal"]["email"], "jordan.lee@example.com")
        self.assertIn("parse_notes", data)

    def test_import_resume_rejects_unsupported_extension(self):
        client = app_module.app.test_client()
        bad_file = (io.BytesIO(b"whatever"), "resume.exe")
        resp = client.post(
            "/import-resume",
            data={"resume": bad_file},
            content_type="multipart/form-data",
        )
        self.assertEqual(resp.status_code, 400)

    # --- Rate limiting -------------------------------------------------------

    def test_custom_role_route_is_rate_limited(self):
        client = app_module.app.test_client()
        statuses = []
        for i in range(12):
            resp = client.post("/custom-role", json={
                "role_name": f"Rate Limit Role {i}",
                "job_description": "Python required.",
            })
            statuses.append(resp.status_code)
        self.assertIn(429, statuses)

    # --- ATS resume builder (smoke tests) -----------------------------------

    def test_ats_resume_builder_round_trip(self):
        client = app_module.app.test_client()
        payload = {
            "resume": {
                "personal": {"name": "Sam Rivera", "email": "sam@example.com"},
                "summary": "Engineer.",
                "skills": ["python", "sql"],
                "experience": [],
                "education": [],
                "projects": [],
                "certifications": [],
                "achievements": [],
                "languages": [],
            },
            "job_description": "Python and SQL experience needed.",
        }
        resp = client.post("/ats-resume-builder", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data["success"])
        self.assertIn("ats", data)

    def test_download_ats_resume_pdf(self):
        client = app_module.app.test_client()
        payload = {
            "resume": {
                "personal": {"name": "Sam Rivera", "email": "sam@example.com"},
                "summary": "Engineer.",
                "skills": ["python"],
                "experience": [],
                "education": [],
                "projects": [],
                "certifications": [],
                "achievements": [],
                "languages": [],
            },
            "format": "pdf",
        }
        resp = client.post("/download-ats-resume", json=payload)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.mimetype, "application/pdf")
        self.assertGreater(len(resp.data), 0)


if __name__ == "__main__":
    unittest.main()
