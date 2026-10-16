"""Tests for the device connection flow with Google's endpoints mocked out.

AI-GENERATED (Claude) for the device-connection demo.

Run from the repo root:  PYTHONPATH=code python -m pytest code/backend/tests
"""

import base64
import json
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock
from urllib.parse import parse_qs, urlsplit

from backend import google_health, google_oauth, token_store

SAMPLES = Path(__file__).resolve().parents[3] / "data" / "samples"


def _fake_id_token(email):
    payload = base64.urlsafe_b64encode(json.dumps({"email": email}).encode()).rstrip(b"=").decode()
    return f"header.{payload}.sig"


class FakeResponse:
    def __init__(self, status, body):
        self.status_code = status
        self._body = body
        self.content = json.dumps(body).encode()

    def json(self):
        return self._body

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests
            raise requests.HTTPError(response=self)


ALL_SCOPES = " ".join(google_oauth.SCOPES)


class DeviceConnectionFlowTest(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.patches = [
            mock.patch.object(token_store, "DATABASE_PATH", Path(self.tmp.name) / "test.db"),
            mock.patch.dict("os.environ", {"GOOGLE_CLIENT_ID": "cid", "GOOGLE_CLIENT_SECRET": "secret"}),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.tmp.cleanup()

    def _connect(self, scope=ALL_SCOPES):
        url = google_health.start_connection()
        state = parse_qs(urlsplit(url).query)["state"][0]
        token_resp = FakeResponse(200, {
            "access_token": "access-1", "refresh_token": "refresh-1", "expires_in": 3599,
            "scope": scope, "id_token": _fake_id_token("atticus@example.com"),
        })
        with mock.patch("backend.google_oauth.requests.post", return_value=token_resp) as post:
            google_health.complete_connection({"state": state, "code": "auth-code"})
        return url, post

    def test_authorization_url_has_pkce_and_offline_access(self):
        url = google_health.start_connection()
        q = parse_qs(urlsplit(url).query)
        self.assertEqual(q["code_challenge_method"], ["S256"])
        self.assertEqual(q["access_type"], ["offline"])
        self.assertEqual(q["redirect_uri"], [google_oauth.redirect_uri()])

    def test_connect_stores_tokens_and_sends_verifier(self):
        _, post = self._connect()
        sent = post.call_args.kwargs["data"]
        self.assertEqual(sent["grant_type"], "authorization_code")
        self.assertTrue(sent["code_verifier"])
        status = google_health.get_status()
        self.assertEqual(status["status"], "connected")
        self.assertEqual(status["email"], "atticus@example.com")

    def test_unknown_or_reused_state_is_rejected(self):
        with self.assertRaises(google_health.ConnectionFailed):
            google_health.complete_connection({"state": "forged", "code": "x"})

    def test_user_cancel_is_reported(self):
        with self.assertRaises(google_health.ConnectionFailed):
            google_health.complete_connection({"error": "access_denied"})

    def test_missing_health_scope_is_rejected(self):
        with self.assertRaises(google_health.ConnectionFailed):
            self._connect(scope="openid email")
        self.assertIsNone(google_health.get_status())

    def test_sync_uses_bearer_token_and_summarizes(self):
        self._connect()

        def fake_get(url, params, headers, timeout):
            self.assertEqual(headers["Authorization"], "Bearer access-1")
            data_type = url.split("/dataTypes/")[1].split("/")[0]
            return FakeResponse(200, json.loads((SAMPLES / f"{data_type}.json").read_text()))

        with mock.patch("backend.google_health.requests.get", side_effect=fake_get):
            results = google_health.sync()
        lines = google_health.summarize(results)
        self.assertTrue(any("Resting heart rate" in line for line in lines))
        self.assertEqual(google_health.get_status()["device_name"], "Charge 6")

    def test_expired_access_token_is_refreshed(self):
        self._connect()
        token_store.update_access_token("new-user", "access-1", int(time.time()) - 10)
        refresh = FakeResponse(200, {"access_token": "access-2", "expires_in": 3599})
        with mock.patch("backend.google_oauth.requests.post", return_value=refresh):
            self.assertEqual(google_health._access_token("new-user"), "access-2")

    def test_revoked_refresh_token_requires_reconnect(self):
        self._connect()
        token_store.update_access_token("new-user", "access-1", int(time.time()) - 10)
        bad = FakeResponse(400, {"error": "invalid_grant", "error_description": "Token has been expired or revoked."})
        with mock.patch("backend.google_oauth.requests.post", return_value=bad):
            with self.assertRaises(google_health.ReconnectRequired):
                google_health._access_token("new-user")
        self.assertEqual(google_health.get_status()["status"], "reconnect_required")


if __name__ == "__main__":
    unittest.main()
