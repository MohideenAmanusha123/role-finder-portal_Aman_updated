import unittest

import app as app_module
from extensions import limiter
from models import db


class AuthAndAccountRolesTests(unittest.TestCase):
    """Uses an in-memory SQLite database per test run (see setUp), so this
    never touches lailnext.db or any real deployment's data.
    """

    def setUp(self):
        app_module.app.config["TESTING"] = True
        app_module.app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
        with app_module.app.app_context():
            db.drop_all()
            db.create_all()
        # The rate limiter's storage is process-global (shared across every
        # test file in the same run), not per-test-class -- without this,
        # a deliberate rate-limit-flood test elsewhere (test_app_routes.py)
        # can exhaust the /custom-role or /auth/* quota before these tests
        # even run, causing unrelated 429s here.
        limiter.reset()

    def tearDown(self):
        with app_module.app.app_context():
            db.session.remove()
            db.drop_all()

    def _signup(self, client, email="user@example.com", password="correcthorsebattery"):
        return client.post("/auth/signup", json={"email": email, "password": password})

    # --- signup ---------------------------------------------------------

    def test_signup_creates_account_and_logs_in(self):
        client = app_module.app.test_client()
        resp = self._signup(client)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json()["email"], "user@example.com")

        me = client.get("/auth/me").get_json()
        self.assertEqual(me["email"], "user@example.com")

    def test_signup_rejects_invalid_email(self):
        client = app_module.app.test_client()
        resp = self._signup(client, email="not-an-email")
        self.assertEqual(resp.status_code, 400)

    def test_signup_rejects_short_password(self):
        client = app_module.app.test_client()
        resp = self._signup(client, password="short")
        self.assertEqual(resp.status_code, 400)

    def test_signup_rejects_duplicate_email(self):
        client = app_module.app.test_client()
        self._signup(client)
        resp = self._signup(client)
        self.assertEqual(resp.status_code, 400)

    # --- login / logout --------------------------------------------------

    def test_login_with_correct_credentials(self):
        client = app_module.app.test_client()
        self._signup(client)
        client.post("/auth/logout")

        resp = client.post("/auth/login", json={"email": "user@example.com", "password": "correcthorsebattery"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(client.get("/auth/me").get_json()["email"], "user@example.com")

    def test_login_with_wrong_password_is_rejected(self):
        client = app_module.app.test_client()
        self._signup(client)
        client.post("/auth/logout")

        resp = client.post("/auth/login", json={"email": "user@example.com", "password": "wrong password"})
        self.assertEqual(resp.status_code, 401)

    def test_login_with_unknown_email_is_rejected(self):
        client = app_module.app.test_client()
        resp = client.post("/auth/login", json={"email": "nobody@example.com", "password": "whatever123"})
        self.assertEqual(resp.status_code, 401)

    def test_logout_clears_session(self):
        client = app_module.app.test_client()
        self._signup(client)
        client.post("/auth/logout")
        self.assertIsNone(client.get("/auth/me").get_json()["email"])

    # --- per-account custom role persistence ------------------------------

    def test_custom_role_persists_across_logout_and_login(self):
        client = app_module.app.test_client()
        self._signup(client)

        resp = client.post("/custom-role", json={
            "role_name": "Persistent Role",
            "job_description": "Python, SQL, Docker required.",
        })
        self.assertEqual(resp.status_code, 200)

        # Visible while logged in.
        self.assertIn(b"Persistent Role", client.get("/").data)

        # Gone from view once logged out (falls back to session roles).
        client.post("/auth/logout")
        self.assertNotIn(b"Persistent Role", client.get("/").data)

        # Back after logging in again -- proves DB persistence, not session.
        client.post("/auth/login", json={"email": "user@example.com", "password": "correcthorsebattery"})
        self.assertIn(b"Persistent Role", client.get("/").data)

    def test_account_custom_roles_are_isolated_between_accounts(self):
        client_a = app_module.app.test_client()
        client_b = app_module.app.test_client()

        self._signup(client_a, email="a@example.com")
        self._signup(client_b, email="b@example.com")

        client_a.post("/custom-role", json={
            "role_name": "Account A Only Role",
            "job_description": "Python required.",
        })

        self.assertIn(b"Account A Only Role", client_a.get("/").data)
        self.assertNotIn(b"Account A Only Role", client_b.get("/").data)

    def test_updating_existing_custom_role_does_not_duplicate(self):
        client = app_module.app.test_client()
        self._signup(client)

        client.post("/custom-role", json={"role_name": "Dup Role", "job_description": "Python required."})
        client.post("/custom-role", json={"role_name": "Dup Role", "job_description": "Python, SQL required."})

        from models import CustomRole, User
        with app_module.app.app_context():
            user = User.query.filter_by(email="user@example.com").first()
            matches = CustomRole.query.filter_by(user_id=user.id, name="Dup Role").all()
            self.assertEqual(len(matches), 1)
            self.assertIn("sql", matches[0].skills)


if __name__ == "__main__":
    unittest.main()
