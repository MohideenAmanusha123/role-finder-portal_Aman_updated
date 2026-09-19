import unittest

from resume_importer import parse_resume_for_builder


def _fake_find_skills(text, vocabulary):
    """Tiny stand-in for resume_matcher.find_skills: case-insensitive
    substring match against a fixed vocabulary, so this test doesn't need
    to import the real (larger, slower-changing) skill matcher.
    """
    text_lower = (text or "").lower()
    return {skill for skill in vocabulary if skill in text_lower}


def _fake_normalize(data):
    """Stand-in for resume_builder.normalize_resume_data: just returns the
    dict as-is so this module can be tested without importing resume_builder.
    """
    return data


SKILL_VOCABULARY = ["python", "sql", "docker", "aws"]


class ParseResumeForBuilderTests(unittest.TestCase):
    def _parse(self, text):
        return parse_resume_for_builder(text, _fake_find_skills, SKILL_VOCABULARY, _fake_normalize)

    def test_well_formatted_resume_has_no_notes(self):
        text = (
            "Jane Smith\n"
            "jane.smith@example.com | +1 555 111 2222\n\n"
            "Summary\n"
            "Backend engineer with 5 years of experience.\n\n"
            "Skills\n"
            "Python, SQL, Docker, AWS\n\n"
            "Experience\n"
            "Senior Backend Engineer | Acme Corp\n"
            "Jan 2021 - Present\n"
            "Built and maintained internal APIs.\n\n"
            "Education\n"
            "B.Tech Computer Science\n"
            "State University\n"
            "2016 - 2020\n"
        )
        data, notes = self._parse(text)
        self.assertEqual(data["personal"]["name"], "Jane Smith")
        self.assertEqual(data["personal"]["email"], "jane.smith@example.com")
        self.assertIn("python", data["skills"])
        self.assertEqual(notes, [])

    def test_missing_contact_info_is_flagged(self):
        text = "Some Person\n\nExperience\nDid some things.\n"
        data, notes = self._parse(text)
        self.assertTrue(any("email" in note.lower() for note in notes))
        self.assertTrue(any("phone" in note.lower() for note in notes))

    def test_missing_sections_are_flagged(self):
        text = "Jane Doe\njane@example.com\n"
        data, notes = self._parse(text)
        joined = " ".join(notes).lower()
        self.assertIn("experience", joined)
        self.assertIn("education", joined)
        self.assertIn("skills", joined)

    def test_empty_input_is_handled_without_raising(self):
        data, notes = self._parse("")
        self.assertEqual(data["personal"]["name"], "")
        self.assertTrue(len(notes) >= 1)

    def test_experience_dates_detected(self):
        text = (
            "Alex Kim\nalex@example.com\n\n"
            "Experience\n"
            "Software Engineer | Beta Inc\n"
            "Mar 2019 - Dec 2022\n"
            "Shipped features.\n"
        )
        data, notes = self._parse(text)
        self.assertEqual(len(data["experience"]), 1)
        self.assertTrue(data["experience"][0]["start_date"])
        self.assertFalse(any("dates" in note.lower() for note in notes))


if __name__ == "__main__":
    unittest.main()
