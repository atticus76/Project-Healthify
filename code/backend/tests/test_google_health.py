"""Tests for the device connection flow with Google's endpoints mocked out.

AI-GENERATED (Claude) for the device-connection demo.

Runs against healthify-test (S2-04) and is skipped if TEST_DATABASE_URL isn't set.
"""

import base64
import json
import time
import unittest
from pathlib import Path
from unittest import mock
from urllib.parse import parse_qs, urlsplit

import pytest

from backend import auth_controller, google_health, google_oauth, telemetry_store, token_store

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


USER = "alice"


@pytest.mark.usefixtures("test_db")
class DeviceConnectionFlowTest(unittest.TestCase):
    def setUp(self):
        auth_controller.register(USER, "", "Testpass1!")
        self.patches = [
            mock.patch.dict("os.environ", {"GOOGLE_CLIENT_ID": "cid", "GOOGLE_CLIENT_SECRET": "secret"}),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()

    def _connect(self, scope=ALL_SCOPES):
        url = google_health.start_connection(USER)
        state = parse_qs(urlsplit(url).query)["state"][0]
        token_resp = FakeResponse(200, {
            "access_token": "access-1", "refresh_token": "refresh-1", "expires_in": 3599,
            "scope": scope, "id_token": _fake_id_token("atticus@example.com"),
        })
        with mock.patch("backend.google_oauth.requests.post", return_value=token_resp) as post:
            google_health.complete_connection({"state": state, "code": "auth-code"})
        return url, post

    def test_authorization_url_has_pkce_and_offline_access(self):
        url = google_health.start_connection(USER)
        q = parse_qs(urlsplit(url).query)
        self.assertEqual(q["code_challenge_method"], ["S256"])
        self.assertEqual(q["access_type"], ["offline"])
        self.assertEqual(q["redirect_uri"], [google_oauth.redirect_uri()])

    def test_connect_stores_tokens_and_sends_verifier(self):
        _, post = self._connect()
        sent = post.call_args.kwargs["data"]
        self.assertEqual(sent["grant_type"], "authorization_code")
        self.assertTrue(sent["code_verifier"])
        status = google_health.get_status(USER)
        self.assertEqual(status["status"], "connected")
        self.assertEqual(status["email"], "atticus@example.com")

    def test_connection_belongs_to_the_user_who_started_it(self):
        auth_controller.register("bob", "", "Testpass1!")
        self._connect()
        self.assertEqual(google_health.get_status(USER)["status"], "connected")
        self.assertIsNone(google_health.get_status("bob"))

    def test_unknown_or_reused_state_is_rejected(self):
        with self.assertRaises(google_health.ConnectionFailed):
            google_health.complete_connection({"state": "forged", "code": "x"})

    def test_user_cancel_is_reported(self):
        with self.assertRaises(google_health.ConnectionFailed):
            google_health.complete_connection({"error": "access_denied"})

    def test_missing_health_scope_is_rejected(self):
        with self.assertRaises(google_health.ConnectionFailed):
            self._connect(scope="openid email")
        self.assertIsNone(google_health.get_status(USER))

    def test_sync_uses_bearer_token_and_summarizes(self):
        self._connect()

        def fake_get(url, params, headers, timeout):
            self.assertEqual(headers["Authorization"], "Bearer access-1")
            data_type = url.split("/dataTypes/")[1].split("/")[0]
            return FakeResponse(200, json.loads((SAMPLES / f"{data_type}.json").read_text()))

        with mock.patch("backend.google_health.requests.get", side_effect=fake_get):
            results = google_health.sync(USER)
        lines = google_health.summarize(results)
        self.assertTrue(any("Resting heart rate" in line for line in lines))
        self.assertEqual(google_health.get_status(USER)["device_name"], "Charge 6")

    def test_sync_saves_a_google_snapshot_for_reports(self):
        self._connect()

        def fake_get(url, params, headers, timeout):
            data_type = url.split("/dataTypes/")[1].split("/")[0]
            return FakeResponse(200, json.loads((SAMPLES / f"{data_type}.json").read_text()))

        with mock.patch("backend.google_health.requests.get", side_effect=fake_get):
            results = google_health.sync(USER)
        telemetry_store._reset_cache()  # read it back from the database
        self.assertEqual(telemetry_store.get_latest(USER), results)

    def test_expired_access_token_is_refreshed(self):
        self._connect()
        token_store.update_access_token(USER, "access-1", int(time.time()) - 10)
        refresh = FakeResponse(200, {"access_token": "access-2", "expires_in": 3599})
        with mock.patch("backend.google_oauth.requests.post", return_value=refresh):
            self.assertEqual(google_health._access_token(USER), "access-2")

    def test_revoked_refresh_token_requires_reconnect(self):
        self._connect()
        token_store.update_access_token(USER, "access-1", int(time.time()) - 10)
        bad = FakeResponse(400, {"error": "invalid_grant", "error_description": "Token has been expired or revoked."})
        with mock.patch("backend.google_oauth.requests.post", return_value=bad):
            with self.assertRaises(google_health.ReconnectRequired):
                google_health._access_token(USER)
        self.assertEqual(google_health.get_status(USER)["status"], "reconnect_required")


if __name__ == "__main__":
    unittest.main()
