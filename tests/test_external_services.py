import time
import unittest

from app.config import Settings
from app.services.google_auth import GoogleAuthService
from app.services.slack_auth import SlackAuthService
from app.services.slack_client import SlackClient


class ExternalServiceTests(unittest.TestCase):
    def test_google_authorization_url_contains_state(self):
        settings = Settings(google_client_id="client-id", google_redirect_uri="http://localhost/callback")
        service = GoogleAuthService(settings)
        url = service.build_authorization_url("user-123")
        self.assertIn("client_id=client-id", url)
        self.assertIn("state=user-123", url)

    def test_slack_signature_verification(self):
        settings = Settings(slack_signing_secret="secret")
        client = SlackClient(settings)
        body = b'{"type":"event_callback"}'
        timestamp = str(int(time.time()))
        import hashlib
        import hmac

        digest = "v0=" + hmac.new(b"secret", f"v0:{timestamp}:{body.decode()}".encode(), hashlib.sha256).hexdigest()
        self.assertTrue(client.verify_signature(timestamp, digest, body))

    def test_slack_authorization_url_contains_redirect(self):
        settings = Settings(
            slack_client_id="12345.67890",
            slack_redirect_uri="https://example.ngrok-free.app/auth/slack/callback",
        )
        service = SlackAuthService(settings)
        url = service.build_authorization_url("user-123")
        self.assertIn("client_id=12345.67890", url)
        self.assertIn("redirect_uri=https%3A%2F%2Fexample.ngrok-free.app%2Fauth%2Fslack%2Fcallback", url)
        self.assertIn("state=user-123", url)


if __name__ == "__main__":
    unittest.main()
