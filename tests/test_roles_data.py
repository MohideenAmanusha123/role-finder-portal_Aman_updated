import json
import os
import unittest

from roles_data import ROLES, add_custom_role


class AddCustomRolePersistenceTests(unittest.TestCase):
    def test_add_custom_role_persists_to_json(self):
        custom_roles_path = os.path.join(os.getcwd(), "tmp_custom_roles.json")
        if os.path.exists(custom_roles_path):
            os.remove(custom_roles_path)

        try:
            result = add_custom_role(
                "Test Role",
                "Python and SQL experience",
                ["python", "sql"],
                custom_roles_path=custom_roles_path,
            )

            self.assertEqual(result["role"], "Test Role")
            self.assertIn("Test Role", ROLES)
            self.assertTrue(os.path.exists(custom_roles_path))

            with open(custom_roles_path, "r", encoding="utf-8") as handle:
                saved = json.load(handle)

            self.assertIn("Test Role", saved)
            self.assertEqual(saved["Test Role"]["required"], ["python", "sql"])
        finally:
            if os.path.exists(custom_roles_path):
                os.remove(custom_roles_path)


if __name__ == "__main__":
    unittest.main()
