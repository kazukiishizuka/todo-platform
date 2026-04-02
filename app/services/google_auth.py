from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from urllib import parse, request
from urllib.error import HTTPError

from app.config import Settings


class GoogleAuthService:
    AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
    TOKEN_URL = "https://oauth2.googleapis.com/token"
    USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def build_authorization_url(self, state: str) -> str:
        query = parse.urlencode(
            {
                "client_id": self.settings.google_client_id,
                "redirect_uri": self.settings.google_redirect_uri,
                "response_type": "code",
                "scope": "openid email profile https://www.googleapis.com/auth/calendar",
                "access_type": "offline",
                "prompt": "consent",
                "state": state,
            }
        )
        return f"{self.AUTH_URL}?{query}"

    def exchange_code(self, code: str) -> dict:
        payload = parse.urlencode(
            {
                "code": code,
                "client_id": self.settings.google_client_id,
                "client_secret": self.settings.google_client_secret,
                "redirect_uri": self.settings.google_redirect_uri,
                "grant_type": "authorization_code",
            }
        ).encode()
        req = request.Request(self.TOKEN_URL, data=payload, method="POST")
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
        with request.urlopen(req, timeout=15) as response:
            data = json.loads(response.read().decode())
        token_expiry = datetime.now(timezone.utc) + timedelta(seconds=int(data.get("expires_in", 3600)))
        profile = self.fetch_userinfo(data["access_token"])
        return {
            "access_token": data["access_token"],
            "refresh_token": data.get("refresh_token"),
            "scope": data.get("scope"),
            "token_expiry": token_expiry,
            "google_account_email": profile.get("email"),
        }

    def fetch_userinfo(self, access_token: str) -> dict:
        req = request.Request(self.USERINFO_URL, method="GET")
        req.add_header("Authorization", f"Bearer {access_token}")
        with request.urlopen(req, timeout=15) as response:
            return json.loads(response.read().decode())
