from __future__ import annotations

import hashlib
import hmac
import json
import time
import logging
from urllib import request

from app.config import Settings


logger = logging.getLogger(__name__)


class SlackClient:
    POST_MESSAGE_URL = "https://slack.com/api/chat.postMessage"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def verify_signature(self, timestamp: str, signature: str, body: bytes) -> bool:
        signing_secret = (self.settings.slack_signing_secret or "").strip()
        if not signing_secret:
            logger.warning("Slack signing secret is empty")
            return False
        if not timestamp or not signature:
            logger.warning("Missing Slack signature headers timestamp=%s signature_present=%s", timestamp, bool(signature))
            return False
        if abs(time.time() - int(timestamp)) > 60 * 5:
            logger.warning("Slack request timestamp too old timestamp=%s", timestamp)
            return False
        basestring = f"v0:{timestamp}:{body.decode()}".encode()
        digest = "v0=" + hmac.new(signing_secret.encode(), basestring, hashlib.sha256).hexdigest()
        ok = hmac.compare_digest(digest, signature)
        if not ok:
            logger.warning("Slack signature mismatch computed_prefix=%s provided_prefix=%s secret_length=%s", digest[:16], signature[:16], len(signing_secret))
        return ok

    def post_message(self, channel_id: str, text: str, blocks: list[dict] | None = None) -> dict:
        payload = {"channel": channel_id, "text": text}
        if blocks:
            payload["blocks"] = blocks
        data = json.dumps(payload).encode()
        req = request.Request(self.POST_MESSAGE_URL, data=data, method="POST")
        req.add_header("Authorization", f"Bearer {self.settings.slack_bot_token}")
        req.add_header("Content-Type", "application/json; charset=utf-8")
        with request.urlopen(req, timeout=15) as response:
            return json.loads(response.read().decode())
