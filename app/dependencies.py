from __future__ import annotations

from functools import lru_cache

from app.config import get_settings
from app.db import SessionLocal, engine
from app.models import Base
from app.repositories.memory import InMemoryTaskRepository
from app.repositories.sqlalchemy_repo import SqlAlchemyTaskRepository
from app.services.google_auth import GoogleAuthService
from app.services.google_calendar_client import GoogleCalendarClient
from app.services.google_sync import GoogleSyncService
from app.services.parser import NaturalLanguageParser
from app.services.slack_auth import SlackAuthService
from app.services.slack_client import SlackClient
from app.services.slack_service import SlackBotService
from app.services.task_service import TaskService
from app.workers.job_worker import JobWorker
from app.workers.reminder_worker import ReminderWorker


@lru_cache
def get_parser() -> NaturalLanguageParser:
    return NaturalLanguageParser()


@lru_cache
def get_google_calendar_client() -> GoogleCalendarClient:
    return GoogleCalendarClient(get_settings())


@lru_cache
def get_google_auth_service() -> GoogleAuthService:
    return GoogleAuthService(get_settings())


@lru_cache
def get_slack_client() -> SlackClient:
    return SlackClient(get_settings())


@lru_cache
def get_slack_auth_service() -> SlackAuthService:
    return SlackAuthService(get_settings())


@lru_cache
def get_google_sync() -> GoogleSyncService:
    return GoogleSyncService(get_google_calendar_client())


def get_repository():
    settings = get_settings()
    if settings.use_sql_repository:
        Base.metadata.create_all(bind=engine)
        db = SessionLocal()
        try:
            yield SqlAlchemyTaskRepository(db)
        finally:
            db.close()
    else:
        yield _memory_repository()


@lru_cache
def _memory_repository() -> InMemoryTaskRepository:
    return InMemoryTaskRepository()


def get_task_service(repository=next(iter([None]))):
    raise RuntimeError("Use FastAPI dependency injection for get_task_service")


def build_task_service(repository):
    return TaskService(repository, get_parser(), get_google_sync())


def build_slack_service(repository):
    return SlackBotService(repository, build_task_service(repository), get_slack_client())


def build_reminder_worker(repository):
    return ReminderWorker(repository, build_task_service(repository), get_slack_client())


def build_job_worker(repository):
    return JobWorker(repository, get_google_sync(), get_slack_client())
