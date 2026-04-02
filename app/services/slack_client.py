from __future__ import annotations

import hashlib
import hmac
import json
import time
from urllib import request

from app.config import Settings


class SlackClient:
    POST_MESSAGE_URL = "https://slack.com/api/chat.postMessage"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def verify_signature(self, timestamp: str, signature: str, body: bytes) -> bool:
        if not self.settings.slack_signing_secret:
            return False
        if abs(time.time() - int(timestamp)) > 60 * 5:
            return False
        basestring = f"v0:{timestamp}:{body.decode()}".encode()
        digest = "v0=" + hmac.new(self.settings.slack_signing_secret.encode(), basestring, hashlib.sha256).hexdigest()
        return hmac.compare_digest(digest, signature)

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
