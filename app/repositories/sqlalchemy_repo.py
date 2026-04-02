from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import ConversationContext, GoogleConnection, JobQueueItem, ReminderRule, SlackConnection, SlackMessageLog, Task, TaskParseLog, TaskSyncLog


class SqlAlchemyTaskRepository:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.settings = get_settings()

    def create_task(self, task: dict) -> dict:
        now = datetime.now(timezone.utc)
        model = Task(
            id=str(task.get("id", uuid4())),
            user_id=str(task["user_id"]),
            title=task["title"],
            description=task.get("description"),
            original_text=task["original_text"],
            status=task.get("status", "pending"),
            priority=task.get("priority"),
            due_date=task.get("due_date"),
            start_datetime=task.get("start_datetime"),
            end_datetime=task.get("end_datetime"),
            timezone=task["timezone"],
            is_all_day=task.get("is_all_day", False),
            recurrence_rule=task.get("recurrence_rule"),
            parser_confidence=str(task.get("parser_confidence")) if task.get("parser_confidence") is not None else None,
            parse_status=task.get("parse_status"),
            google_event_id=task.get("google_event_id"),
            google_sync_status=task.get("google_sync_status"),
            sync_retry_count=task.get("sync_retry_count", 0),
            last_sync_error=task.get("last_sync_error"),
            completed_at=task.get("completed_at"),
            deleted_at=task.get("deleted_at"),
            created_at=task.get("created_at", now),
            updated_at=task.get("updated_at", now),
        )
        self.session.add(model)
        self.session.commit()
        return self._task_to_dict(model)

    def update_task(self, task_id, updates: dict) -> dict:
        model = self.session.get(Task, str(task_id))
        if model is None:
            raise KeyError(task_id)
        for key, value in updates.items():
            if value is not None and hasattr(model, key):
                setattr(model, key, value)
        model.updated_at = datetime.now(timezone.utc)
        self.session.add(model)
        self.session.commit()
        self.session.refresh(model)
        return self._task_to_dict(model)

    def get_task(self, task_id) -> dict | None:
        model = self.session.get(Task, str(task_id))
        return self._task_to_dict(model) if model else None

    def list_tasks(self, user_id, *, status: str | None = None, scope: str | None = None, q: str | None = None) -> list[dict]:
        stmt = select(Task).where(Task.user_id == str(user_id), Task.deleted_at.is_(None))
        if status:
            stmt = stmt.where(Task.status == status)
        if q:
            stmt = stmt.where(or_(Task.title.contains(q), Task.original_text.contains(q)))
        if scope:
            stmt = stmt.where(self._scope_condition(scope))
        stmt = stmt.order_by(Task.start_datetime, Task.due_date, Task.created_at)
        return [self._task_to_dict(item) for item in self.session.scalars(stmt).all()]

    def _scope_condition(self, scope: str):
        today = datetime.now(timezone.utc).date()
        if scope == "today":
            return or_(Task.due_date == today, Task.start_datetime >= datetime.combine(today, datetime.min.time(), tzinfo=timezone.utc), Task.start_datetime < datetime.combine(today + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc))
        if scope == "tomorrow":
            target = today + timedelta(days=1)
            return or_(Task.due_date == target, and_(Task.start_datetime >= datetime.combine(target, datetime.min.time(), tzinfo=timezone.utc), Task.start_datetime < datetime.combine(target + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc)))
        if scope == "this_week":
            start = today - timedelta(days=today.weekday())
            end = start + timedelta(days=7)
            return or_(and_(Task.due_date >= start, Task.due_date < end), and_(Task.start_datetime >= datetime.combine(start, datetime.min.time(), tzinfo=timezone.utc), Task.start_datetime < datetime.combine(end, datetime.min.time(), tzinfo=timezone.utc)))
        if scope == "this_month":
            start = today.replace(day=1)
            end = (start + timedelta(days=32)).replace(day=1)
            return or_(and_(Task.due_date >= start, Task.due_date < end), and_(Task.start_datetime >= datetime.combine(start, datetime.min.time(), tzinfo=timezone.utc), Task.start_datetime < datetime.combine(end, datetime.min.time(), tzinfo=timezone.utc)))
        if scope == "overdue":
            return and_(Task.status == "pending", Task.due_date < today)
        return True

    def log_parse(self, payload: dict) -> None:
        self.session.add(TaskParseLog(id=str(uuid4()), task_id=str(payload.get("task_id")) if payload.get("task_id") else None, original_text=payload["original_text"], parsed_json=payload["parsed_json"], confidence=str(payload.get("confidence")) if payload.get("confidence") is not None else None, ambiguity_flags=payload.get("ambiguity_flags"), created_at=payload["created_at"]))
        self.session.commit()

    def log_sync(self, payload: dict) -> None:
        self.session.add(TaskSyncLog(id=str(uuid4()), task_id=str(payload["task_id"]), provider=payload["provider"], operation_type=payload["operation_type"], status=payload["status"], error_message=payload.get("error_message"), payload_json=payload.get("payload_json"), created_at=payload["created_at"]))
        self.session.commit()

    def log_slack_message(self, payload: dict) -> None:
        self.session.add(SlackMessageLog(id=str(uuid4()), user_id=str(payload["user_id"]), slack_channel_id=payload["slack_channel_id"], message_type=payload["message_type"], payload_json=payload.get("payload_json"), status=payload["status"], error_message=payload.get("error_message"), sent_at=payload["sent_at"]))
        self.session.commit()

    def find_tasks(self, user_id, keyword: str) -> list[dict]:
        stmt = select(Task).where(Task.user_id == str(user_id), Task.deleted_at.is_(None), Task.title.contains(keyword))
        return [self._task_to_dict(item) for item in self.session.scalars(stmt).all()]

    def save_context(self, user_id, channel_type: str, channel_id: str, context: dict) -> None:
        stmt = select(ConversationContext).where(ConversationContext.user_id == str(user_id), ConversationContext.channel_type == channel_type, ConversationContext.channel_id == channel_id)
        model = self.session.scalars(stmt).first()
        now = datetime.now(timezone.utc)
        if model is None:
            model = ConversationContext(id=str(uuid4()), user_id=str(user_id), channel_type=channel_type, channel_id=channel_id, last_referenced_task_ids=context.get("last_referenced_task_ids"), context_json=context.get("context_json"), updated_at=now)
        else:
            model.last_referenced_task_ids = context.get("last_referenced_task_ids")
            model.context_json = context.get("context_json")
            model.updated_at = now
        self.session.add(model)
        self.session.commit()

    def get_context(self, user_id, channel_type: str, channel_id: str) -> dict | None:
        stmt = select(ConversationContext).where(ConversationContext.user_id == str(user_id), ConversationContext.channel_type == channel_type, ConversationContext.channel_id == channel_id)
        model = self.session.scalars(stmt).first()
        if model is None:
            return None
        if datetime.now(timezone.utc) - model.updated_at > timedelta(minutes=self.settings.context_expiry_minutes):
            return None
        return {"last_referenced_task_ids": model.last_referenced_task_ids or [], "context_json": model.context_json or {}, "updated_at": model.updated_at}

    def create_reminder_rule(self, rule: dict) -> dict:
        now = datetime.now(timezone.utc)
        model = ReminderRule(id=str(rule.get("id", uuid4())), user_id=str(rule["user_id"]), slack_channel_id=rule["slack_channel_id"], reminder_type=rule["reminder_type"], frequency=rule["frequency"], day_of_week=rule.get("day_of_week"), time_of_day=rule["time_of_day"], timezone=rule["timezone"], enabled=rule.get("enabled", True), created_at=now, updated_at=now)
        self.session.add(model)
        self.session.commit()
        return {"id": model.id, **rule}

    def list_active_reminder_rules(self) -> list[dict]:
        stmt = select(ReminderRule).where(ReminderRule.enabled.is_(True))
        return [{"id": item.id, "user_id": item.user_id, "slack_channel_id": item.slack_channel_id, "reminder_type": item.reminder_type, "frequency": item.frequency, "day_of_week": item.day_of_week, "time_of_day": item.time_of_day, "timezone": item.timezone, "enabled": item.enabled} for item in self.session.scalars(stmt).all()]

    def create_google_connection(self, payload: dict) -> dict:
        now = datetime.now(timezone.utc)
        stmt = select(GoogleConnection).where(GoogleConnection.user_id == str(payload["user_id"]))
        model = self.session.scalars(stmt).first()
        if model is None:
            model = GoogleConnection(id=str(uuid4()), user_id=str(payload["user_id"]), google_account_email=payload.get("google_account_email"), access_token=payload["access_token"], refresh_token=payload.get("refresh_token"), token_expiry=payload.get("token_expiry"), scope=payload.get("scope"), created_at=now, updated_at=now)
        else:
            model.google_account_email = payload.get("google_account_email")
            model.access_token = payload["access_token"]
            model.refresh_token = payload.get("refresh_token") or model.refresh_token
            model.token_expiry = payload.get("token_expiry")
            model.scope = payload.get("scope")
            model.updated_at = now
        self.session.add(model)
        self.session.commit()
        return {"user_id": model.user_id, "access_token": model.access_token, "refresh_token": model.refresh_token, "token_expiry": model.token_expiry, "scope": model.scope, "google_account_email": model.google_account_email}

    def get_google_connection(self, user_id) -> dict | None:
        stmt = select(GoogleConnection).where(GoogleConnection.user_id == str(user_id))
        model = self.session.scalars(stmt).first()
        if model is None:
            return None
        return {"user_id": model.user_id, "access_token": model.access_token, "refresh_token": model.refresh_token, "token_expiry": model.token_expiry, "scope": model.scope, "google_account_email": model.google_account_email}

    def create_slack_connection(self, payload: dict) -> dict:
        now = datetime.now(timezone.utc)
        stmt = select(SlackConnection).where(SlackConnection.user_id == str(payload["user_id"]))
        model = self.session.scalars(stmt).first()
        if model is None:
            model = SlackConnection(
                id=str(uuid4()),
                user_id=str(payload["user_id"]),
                slack_workspace_id=payload["slack_workspace_id"],
                slack_user_id=payload["slack_user_id"],
                slack_team_name=payload.get("slack_team_name"),
                bot_user_id=payload.get("bot_user_id"),
                bot_access_token=payload.get("bot_access_token"),
                access_scope=payload.get("access_scope"),
                connected_at=now,
                updated_at=now,
            )
        else:
            model.slack_workspace_id = payload["slack_workspace_id"]
            model.slack_user_id = payload["slack_user_id"]
            model.slack_team_name = payload.get("slack_team_name")
            model.bot_user_id = payload.get("bot_user_id")
            model.bot_access_token = payload.get("bot_access_token")
            model.access_scope = payload.get("access_scope")
            model.updated_at = now
        self.session.add(model)
        self.session.commit()
        return {
            "user_id": model.user_id,
            "slack_workspace_id": model.slack_workspace_id,
            "slack_user_id": model.slack_user_id,
            "slack_team_name": model.slack_team_name,
            "bot_user_id": model.bot_user_id,
            "bot_access_token": model.bot_access_token,
            "access_scope": model.access_scope,
        }

    def get_slack_connection(self, user_id) -> dict | None:
        stmt = select(SlackConnection).where(SlackConnection.user_id == str(user_id))
        model = self.session.scalars(stmt).first()
        if model is None:
            return None
        return {
            "user_id": model.user_id,
            "slack_workspace_id": model.slack_workspace_id,
            "slack_user_id": model.slack_user_id,
            "slack_team_name": model.slack_team_name,
            "bot_user_id": model.bot_user_id,
            "bot_access_token": model.bot_access_token,
            "access_scope": model.access_scope,
        }

    def enqueue_job(self, job_type: str, payload: dict, run_after: datetime | None = None) -> dict:
        now = datetime.now(timezone.utc)
        model = JobQueueItem(id=str(uuid4()), job_type=job_type, status="queued", payload_json=payload, retry_count=0, run_after=run_after, last_error=None, created_at=now, updated_at=now)
        self.session.add(model)
        self.session.commit()
        return {"id": model.id, "job_type": model.job_type, "status": model.status, "payload_json": model.payload_json, "retry_count": model.retry_count}

    def list_jobs(self, job_type: str | None = None, status: str = "queued") -> list[dict]:
        stmt = select(JobQueueItem).where(JobQueueItem.status == status)
        if job_type:
            stmt = stmt.where(JobQueueItem.job_type == job_type)
        stmt = stmt.order_by(JobQueueItem.created_at)
        return [{"id": item.id, "job_type": item.job_type, "status": item.status, "payload_json": item.payload_json, "retry_count": item.retry_count, "run_after": item.run_after, "last_error": item.last_error} for item in self.session.scalars(stmt).all()]

    def mark_job_status(self, job_id: str, status: str, error: str | None = None) -> None:
        model = self.session.get(JobQueueItem, job_id)
        if model is None:
            return
        model.status = status
        model.last_error = error
        if status == "queued":
            model.retry_count += 1
        model.updated_at = datetime.now(timezone.utc)
        self.session.add(model)
        self.session.commit()

    @staticmethod
    def _task_to_dict(model: Task) -> dict:
        return {
            "id": model.id,
            "user_id": model.user_id,
            "title": model.title,
            "description": model.description,
            "original_text": model.original_text,
            "status": model.status,
            "priority": model.priority,
            "due_date": model.due_date,
            "start_datetime": model.start_datetime,
            "end_datetime": model.end_datetime,
            "timezone": model.timezone,
            "is_all_day": model.is_all_day,
            "recurrence_rule": model.recurrence_rule,
            "parser_confidence": float(model.parser_confidence) if model.parser_confidence is not None else None,
            "parse_status": model.parse_status,
            "google_event_id": model.google_event_id,
            "google_sync_status": model.google_sync_status,
            "sync_retry_count": model.sync_retry_count,
            "last_sync_error": model.last_sync_error,
            "completed_at": model.completed_at,
            "deleted_at": model.deleted_at,
            "created_at": model.created_at,
            "updated_at": model.updated_at,
        }
