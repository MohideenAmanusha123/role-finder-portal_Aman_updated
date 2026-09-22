import unittest

from roles_data import ROLES, build_custom_role, merge_roles


class BuildCustomRoleTests(unittest.TestCase):
    """build_custom_role() replaced the old add_custom_role(). The old
    version mutated the module-level ROLES dict and wrote to a shared JSON
    file on disk -- which meant one visitor's custom role leaked into every
    other visitor's role list, and behaved inconsistently across gunicorn
    worker processes. The new version is pure: it returns a role
    definition and touches nothing global. app.py is responsible for
    storing the result somewhere request-scoped (the Flask session).
    """

    def test_returns_expected_role_shape(self):
        clean_name, info = build_custom_role(
            "  Test   Role  ",
            "Python and SQL experience",
            ["python", "sql"],
        )
        self.assertEqual(clean_name, "Test Role")
        self.assertEqual(info["required"], ["python", "sql"])
        self.assertEqual(info["skills"], ["python", "sql"])
        self.assertTrue(info["custom"])

    def test_does_not_mutate_global_roles(self):
        before = dict(ROLES)
        build_custom_role("Another Test Role", "Python and SQL experience", ["python", "sql"])
        self.assertEqual(ROLES, before)
        self.assertNotIn("Another Test Role", ROLES)

    def test_empty_name_is_rejected(self):
        with self.assertRaises(ValueError):
            build_custom_role("   ", "Python experience", ["python"])

    def test_no_recognized_skills_is_rejected(self):
        with self.assertRaises(ValueError):
            build_custom_role("Empty Skills Role", "Some job description", [])

    def test_skill_list_is_capped(self):
        many_skills = [f"skill{i}" for i in range(50)]
        _, info = build_custom_role("Big Role", "many skills", many_skills)
        self.assertLessEqual(len(info["skills"]), 30)


class MergeRolesTests(unittest.TestCase):
    def test_merge_with_no_custom_roles_returns_base_catalog(self):
        merged = merge_roles(None)
        self.assertEqual(merged, ROLES)
        # Must be a copy, not the same object, so callers can't accidentally
        # mutate the shared base catalog through the merged result.
        self.assertIsNot(merged, ROLES)

    def test_merge_adds_custom_role_without_touching_base(self):
        _, info = build_custom_role("Merged Role", "Python experience", ["python"])
        merged = merge_roles({"Merged Role": info})
        self.assertIn("Merged Role", merged)
        self.assertNotIn("Merged Role", ROLES)


class ExpandedRoleCatalogTests(unittest.TestCase):
    """Covers the 8 roles added to broaden the out-of-the-box catalog
    beyond the original 18 (Full Stack Developer, Cloud Engineer,
    Cybersecurity Analyst, Mobile App Developer, UX/UI Designer,
    Digital Marketing Specialist, Database Administrator, Project Manager).
    """

    NEW_ROLES = [
        "Full Stack Developer", "Cloud Engineer", "Cybersecurity Analyst",
        "Mobile App Developer", "UX/UI Designer", "Digital Marketing Specialist",
        "Database Administrator", "Project Manager",
    ]

    def test_new_roles_exist_in_catalog(self):
        for role in self.NEW_ROLES:
            self.assertIn(role, ROLES)

    def test_new_roles_have_required_fields(self):
        for role in self.NEW_ROLES:
            info = ROLES[role]
            self.assertTrue(info.get("description"))
            self.assertTrue(info.get("required"))
            self.assertIn("level", info)

    def test_new_role_skills_are_all_in_the_vocabulary(self):
        from roles_data import SKILL_VOCABULARY
        vocab = set(SKILL_VOCABULARY)
        for role in self.NEW_ROLES:
            info = ROLES[role]
            for skill in info.get("required", []) + info.get("preferred", []):
                self.assertIn(skill, vocab, f"{skill!r} (from {role}) is missing from SKILL_VOCABULARY")

    def test_catalog_grew_from_original_eighteen(self):
        self.assertGreaterEqual(len(ROLES), 26)


if __name__ == "__main__":
    unittest.main()
