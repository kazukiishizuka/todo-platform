from __future__ import annotations

import json
from urllib import parse, request

from app.config import Settings


class SlackAuthService:
    AUTHORIZE_URL = "https://slack.com/oauth/v2/authorize"
    ACCESS_URL = "https://slack.com/api/oauth.v2.access"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def build_authorization_url(self, state: str) -> str:
        query = parse.urlencode(
            {
                "client_id": self.settings.slack_client_id,
                "scope": ",".join(
                    [
                        "chat:write",
                        "groups:history",
                        "groups:read",
                        "channels:history",
                        "channels:read",
                        "im:history",
                        "im:read",
                        "mpim:history",
                        "mpim:read",
                        "commands",
                        "app_mentions:read",
                    ]
                ),
                "redirect_uri": self.settings.slack_redirect_uri,
                "state": state,
            }
        )
        return f"{self.AUTHORIZE_URL}?{query}"

    def exchange_code(self, code: str) -> dict:
        payload = parse.urlencode(
            {
                "code": code,
                "client_id": self.settings.slack_client_id,
                "client_secret": self.settings.slack_client_secret,
                "redirect_uri": self.settings.slack_redirect_uri,
            }
        ).encode()
        req = request.Request(self.ACCESS_URL, data=payload, method="POST")
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
        with request.urlopen(req, timeout=15) as response:
            data = json.loads(response.read().decode())
        if not data.get("ok"):
            raise RuntimeError(data.get("error", "slack oauth failed"))
        authed_user = data.get("authed_user", {})
        return {
            "slack_workspace_id": data["team"]["id"],
            "slack_team_name": data["team"].get("name"),
            "slack_user_id": authed_user.get("id", ""),
            "bot_user_id": data.get("bot_user_id"),
            "bot_access_token": data.get("access_token"),
            "access_scope": data.get("scope"),
        }
