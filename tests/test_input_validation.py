"""Smoke tests for empty and over-limit prediction inputs."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from werkzeug.security import generate_password_hash

from app import create_app
from config import Config
from models import User, db


class InputValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.TemporaryDirectory()
        db_file = Path(cls.temp_dir.name, "test.db").as_posix()
        database_uri = f"sqlite:///{db_file}"

        # Point the app's normal factory at a disposable test database.
        with patch.object(Config, "SQLALCHEMY_DATABASE_URI", database_uri):
            cls.app = create_app()

        cls.app.config.update(TESTING=True, SECRET_KEY="test-secret")
        cls.client = cls.app.test_client()

        with cls.app.app_context():
            user = User(
                username="test-user",
                email="test@example.com",
                password_hash=generate_password_hash("test-password"),
            )
            db.session.add(user)
            db.session.commit()

        response = cls.client.post(
            "/auth/login",
            data={"username": "test-user", "password": "test-password"},
        )
        if response.status_code != 302:
            raise AssertionError("Test user could not log in to the app.")

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            db.session.remove()
            db.drop_all()
            db.engine.dispose()
        cls.temp_dir.cleanup()

    def test_dashboard_rejects_empty_input(self):
        response = self.client.post("/dashboard", data={"input_text": "   "})

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Please enter some text", response.data)

    def test_dashboard_rejects_text_over_2000_characters(self):
        response = self.client.post(
            "/dashboard", data={"input_text": "a" * 2001}
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Input too long", response.data)

    def test_compare_warns_on_empty_input(self):
        response = self.client.post("/compare", data={"input_text": " "})

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Please enter some text to compare", response.data)

    def test_compare_rejects_text_over_2000_characters(self):
        response = self.client.post(
            "/compare", data={"input_text": "a" * 2001}
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Input too long", response.data)


if __name__ == "__main__":
    unittest.main()
