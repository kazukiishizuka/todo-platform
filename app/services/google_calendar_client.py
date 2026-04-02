from __future__ import annotations

import json
from urllib import request

from app.config import Settings


class GoogleCalendarClient:
    BASE_URL = "https://www.googleapis.com/calendar/v3/calendars"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def create_event(self, access_token: str, payload: dict) -> dict:
        return self._request("POST", access_token, payload)

    def update_event(self, access_token: str, event_id: str, payload: dict) -> dict:
        return self._request("PUT", access_token, payload, event_id=event_id)

    def delete_event(self, access_token: str, event_id: str) -> dict:
        return self._request("DELETE", access_token, None, event_id=event_id)

    def _request(self, method: str, access_token: str, payload: dict | None, event_id: str | None = None) -> dict:
        calendar_id = self.settings.google_calendar_id
        url = f"{self.BASE_URL}/{calendar_id}/events"
        if event_id:
            url = f"{url}/{event_id}"
        data = json.dumps(payload).encode() if payload is not None else None
        req = request.Request(url, data=data, method=method)
        req.add_header("Authorization", f"Bearer {access_token}")
        req.add_header("Content-Type", "application/json")
        with request.urlopen(req, timeout=15) as response:
            raw = response.read().decode() or "{}"
            return json.loads(raw)
