import unittest

from resume_matcher import analyze_text, detect_experience_signal, find_skills, compute_role_match


class ResumeMatcherRegressionTests(unittest.TestCase):
    def test_find_skills_detects_aliases_and_canonical_entries(self):
        text = "Experienced Python developer with SQL and REST API work. Used React and AWS."
        skills = find_skills(text)

        self.assertIn("python", skills)
        self.assertIn("sql", skills)
        self.assertIn("rest api", skills)
        self.assertIn("react", skills)
        self.assertIn("aws", skills)

    def test_experience_signal_handles_years(self):
        signal = detect_experience_signal("5+ years of experience in Python and team leadership.")
        self.assertEqual(signal["years"], 5)
        self.assertIn(signal["level"], {"senior", "mid"})

    def test_compute_role_match_uses_weighted_required_and_preferred(self):
        resume_skills = {"python", "sql", "git", "docker", "aws"}
        result = compute_role_match(resume_skills, "Backend Developer")

        self.assertGreater(result["score"], 0)
        self.assertIn("python", result["matched_required"])
        self.assertTrue(result["base_score"] >= 0)

    def test_analyze_text_returns_role_results_for_resume_text(self):
        sample = "Python developer with SQL, AWS, Docker, Git and REST API experience."
        result = analyze_text(sample)

        self.assertIn("roles", result)
        self.assertIn("detected_skills", result)
        self.assertGreater(len(result["roles"]), 0)


if __name__ == "__main__":
    unittest.main()
