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

    def test_find_skills_tolerates_simple_plurals_on_single_word_skills(self):
        skills = find_skills("Experience with Dockers containers and Kubernetes clusters.")
        self.assertIn("docker", skills)

    def test_find_skills_plural_tolerance_now_covered_via_alias(self):
        # The pattern-level plural tolerance still only applies to
        # single-token skills (see _pattern_for) -- multi-word phrases like
        # "rest api" are matched exactly at that layer. But "rest apis" is
        # now in SKILL_ALIASES specifically to close this gap through the
        # alias layer instead, so "REST APIs" (plural) should match.
        skills = find_skills("Built several REST APIs for internal tools.")
        self.assertIn("rest api", skills)

    def test_find_skills_go_language_does_not_false_positive_on_common_word(self):
        # Regression guard: "go" the language must not match "goes", the
        # extremely common English verb form -- see the denylist in
        # resume_matcher._pattern_for.
        skills = find_skills("This project goes well beyond initial expectations.")
        self.assertNotIn("go", skills)
        skills = find_skills("Backend services written primarily in Go.")
        self.assertIn("go", skills)

    def test_experience_signal_handles_years(self):
        signal = detect_experience_signal("5+ years of experience in Python and team leadership.")
        self.assertEqual(signal["years"], 5)
        self.assertIn(signal["level"], {"senior", "mid"})

    def test_experience_signal_prefers_employment_dates_over_phrase(self):
        # The resume never says "X years" -- only employment dates. Years
        # should be calculated from those dates, not left undetected.
        text = "Backend Engineer | Acme Corp\nJan 2019 - Dec 2022\nBuilt internal tools."
        signal = detect_experience_signal(text)
        self.assertEqual(signal["source"], "employment dates")
        self.assertAlmostEqual(signal["years"], 3.9, delta=0.2)
        self.assertEqual(signal["date_ranges_found"], 1)

    def test_experience_signal_merges_overlapping_date_ranges(self):
        # Two roles held at the same time should merge into one span, not
        # sum to double the actual calendar time covered.
        text = (
            "Consultant | Acme\nJan 2019 - Dec 2022\n\n"
            "Advisor | Beta Inc\nJun 2020 - Jun 2021\n"
        )
        signal = detect_experience_signal(text)
        self.assertEqual(signal["date_ranges_found"], 2)
        # If these were summed instead of merged, this would be ~5.0 years;
        # merged, it should equal the single Jan 2019-Dec 2022 span (~3.9).
        self.assertLess(signal["years"], 4.5)

    def test_experience_signal_sums_non_overlapping_date_ranges(self):
        text = (
            "Backend Engineer | Acme\nJan 2018 - Dec 2019\n\n"
            "QA Tester | Beta Inc\nJan 2020 - Dec 2021\n"
        )
        signal = detect_experience_signal(text)
        self.assertEqual(signal["date_ranges_found"], 2)
        self.assertAlmostEqual(signal["years"], 3.8, delta=0.2)

    def test_experience_signal_falls_back_to_phrase_when_no_dates(self):
        signal = detect_experience_signal("Experienced professional with 6 years in the field.")
        self.assertEqual(signal["source"], "years of experience")
        self.assertEqual(signal["years"], 6)

    def test_experience_signal_handles_no_dates_and_no_phrase(self):
        signal = detect_experience_signal("Just some text with no dates or years mentioned.")
        self.assertIsNone(signal["years"])
        self.assertEqual(signal["level"], "unknown")

    def test_experience_signal_skips_malformed_reversed_range(self):
        signal = detect_experience_signal("Dec 2022 - Jan 2019")
        self.assertIsNone(signal["years"])

    def test_compute_role_match_uses_weighted_required_and_preferred(self):
        resume_skills = {"python", "sql", "git", "docker", "aws"}
        result = compute_role_match(resume_skills, "Backend Developer")

        self.assertGreater(result["score"], 0)
        self.assertIn("python", result["matched_required"])
        self.assertTrue(result["base_score"] >= 0)

    def test_skill_weights_reflect_the_roles_actual_configured_weights(self):
        # Backend Developer is configured for 80/20 (precision-heavy role);
        # the API response must report that, not a hardcoded 70/30 --
        # otherwise the scoring math and what the UI tells the user about
        # it silently disagree.
        resume_skills = {"python", "java", "sql", "nosql", "rest api", "git", "unit testing"}
        result = compute_role_match(resume_skills, "Backend Developer")
        self.assertEqual(result["skill_weights"], {"required": 80, "preferred": 20})

    def test_skill_weights_default_to_70_30_when_role_has_no_override(self):
        resume_skills = {"sql", "excel", "data analysis", "statistics", "data visualization"}
        result = compute_role_match(resume_skills, "Data Analyst")
        self.assertEqual(result["skill_weights"], {"required": 70, "preferred": 30})

    def test_skill_weights_differ_for_a_breadth_oriented_role(self):
        resume_skills = {"human resources", "recruiting", "communication"}
        result = compute_role_match(resume_skills, "HR Executive")
        self.assertEqual(result["skill_weights"], {"required": 60, "preferred": 40})

    def test_analyze_text_returns_role_results_for_resume_text(self):
        sample = "Python developer with SQL, AWS, Docker, Git and REST API experience."
        result = analyze_text(sample)

        self.assertIn("roles", result)
        self.assertIn("detected_skills", result)
        self.assertGreater(len(result["roles"]), 0)

    # --- Context validation (negation) --------------------------------------

    def test_negated_skill_mention_is_not_credited(self):
        skills = find_skills("I have no experience with Kubernetes, but I know Docker well.")
        self.assertNotIn("kubernetes", skills)
        self.assertIn("docker", skills)

    def test_negated_skill_still_credited_if_mentioned_positively_elsewhere(self):
        # One negated mention shouldn't hide a genuine positive mention of
        # the same skill elsewhere in the resume.
        text = "Not proficient in Python at my last job, but built several Python microservices since then."
        skills = find_skills(text)
        self.assertIn("python", skills)

    def test_various_negation_phrasings_are_recognized(self):
        cases = [
            "No experience with Terraform.",
            "Not familiar with Kubernetes.",
            "Unfamiliar with GraphQL.",
            "Limited experience with Ansible.",
            "No prior experience with Jenkins.",
            "Lacking experience in Scrum.",
        ]
        skill_for_case = ["terraform", "kubernetes", "graphql", "ansible", "jenkins", "scrum"]
        for text, skill in zip(cases, skill_for_case):
            with self.subTest(text=text):
                self.assertNotIn(skill, find_skills(text))

    def test_negation_does_not_over_trigger_on_unrelated_earlier_text(self):
        # A negation phrase early in an unrelated sentence should not
        # suppress a skill mentioned in a completely separate, later
        # sentence -- the window is short and scoped to what immediately
        # precedes the match.
        text = "Not a fan of long meetings. Proficient in React and TypeScript."
        skills = find_skills(text)
        self.assertIn("react", skills)
        self.assertIn("typescript", skills)

    # --- Expanded alias coverage ---------------------------------------------

    def test_expanded_aliases_catch_common_phrasings(self):
        text = (
            "Built REST APIs with Node.js and Express.js, deployed on AWS Cloud "
            "using Infrastructure as Code with Terraform. Familiar with TDD and CI CD pipelines."
        )
        skills = find_skills(text)
        self.assertIn("node.js", skills)
        self.assertIn("express", skills)
        self.assertIn("aws", skills)
        self.assertIn("terraform", skills)
        self.assertIn("unit testing", skills)
        self.assertIn("ci/cd", skills)

    def test_all_skill_aliases_resolve_to_real_vocabulary_entries(self):
        from roles_data import SKILL_ALIASES, SKILL_VOCABULARY
        vocab = set(SKILL_VOCABULARY)
        bad = {alias: canon for alias, canon in SKILL_ALIASES.items() if canon not in vocab}
        self.assertEqual(bad, {}, f"Aliases pointing to a non-existent canonical skill: {bad}")


if __name__ == "__main__":
    unittest.main()
