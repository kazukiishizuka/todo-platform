from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache


@dataclass
class Settings:
    app_name: str = "todo-platform"
    database_url: str = "sqlite+pysqlite:///:memory:"
    default_timezone: str = "Asia/Tokyo"
    default_event_duration_minutes: int = 60
    sync_time_less_tasks_to_google: bool = False
    context_expiry_minutes: int = 60
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/auth/google/callback"
    google_calendar_id: str = "primary"
    slack_client_id: str = ""
    slack_client_secret: str = ""
    slack_redirect_uri: str = "https://example.ngrok-free.app/auth/slack/callback"
    slack_bot_token: str = ""
    slack_signing_secret: str = ""
    slack_bot_user_id: str = ""
    base_url: str = "http://localhost:8000"
    internal_token: str = ""

    @property
    def use_sql_repository(self) -> bool:
        return self.database_url.startswith("postgresql") or self.database_url.startswith("sqlite")


@lru_cache
def get_settings() -> Settings:
    return Settings(
        app_name=os.getenv("TODO_APP_NAME", "todo-platform"),
        database_url=os.getenv("TODO_DATABASE_URL", "sqlite+pysqlite:///:memory:"),
        default_timezone=os.getenv("TODO_DEFAULT_TIMEZONE", "Asia/Tokyo"),
        default_event_duration_minutes=int(os.getenv("TODO_DEFAULT_EVENT_DURATION_MINUTES", "60")),
        sync_time_less_tasks_to_google=os.getenv("TODO_SYNC_TIME_LESS_TASKS_TO_GOOGLE", "false").lower() == "true",
        context_expiry_minutes=int(os.getenv("TODO_CONTEXT_EXPIRY_MINUTES", "60")),
        google_client_id=os.getenv("TODO_GOOGLE_CLIENT_ID", ""),
        google_client_secret=os.getenv("TODO_GOOGLE_CLIENT_SECRET", ""),
        google_redirect_uri=os.getenv("TODO_GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/google/callback"),
        google_calendar_id=os.getenv("TODO_GOOGLE_CALENDAR_ID", "primary"),
        slack_client_id=os.getenv("TODO_SLACK_CLIENT_ID", ""),
        slack_client_secret=os.getenv("TODO_SLACK_CLIENT_SECRET", ""),
        slack_redirect_uri=os.getenv("TODO_SLACK_REDIRECT_URI", "https://example.ngrok-free.app/auth/slack/callback"),
        slack_bot_token=os.getenv("TODO_SLACK_BOT_TOKEN", ""),
        slack_signing_secret=os.getenv("TODO_SLACK_SIGNING_SECRET", ""),
        slack_bot_user_id=os.getenv("TODO_SLACK_BOT_USER_ID", ""),
        base_url=os.getenv("TODO_BASE_URL", "http://localhost:8000"),
        internal_token=os.getenv("TODO_INTERNAL_TOKEN", ""),
    )
