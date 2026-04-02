from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Iterable
from uuid import UUID, uuid4

from app.config import get_settings


class InMemoryTaskRepository:
    def __init__(self) -> None:
        self.tasks: dict[str, dict] = {}
        self.parse_logs: list[dict] = []
        self.sync_logs: list[dict] = []
        self.contexts: dict[tuple[str, str, str], dict] = {}
        self.reminder_rules: dict[str, dict] = {}
        self.slack_logs: list[dict] = []
        self.google_connections: dict[str, dict] = {}
        self.slack_connections: dict[str, dict] = {}
        self.jobs: dict[str, dict] = {}
        self.processed_slack_events: set[str] = set()

    def create_task(self, task: dict) -> dict:
        task_id = str(task.get("id", uuid4()))
        now = datetime.now(timezone.utc)
        task = {**task}
        task["id"] = task_id
        task["user_id"] = str(task["user_id"])
        task.setdefault("created_at", now)
        task.setdefault("updated_at", now)
        task.setdefault("status", "pending")
        task.setdefault("sync_retry_count", 0)
        self.tasks[task_id] = task
        return task

    def update_task(self, task_id, updates: dict) -> dict:
        task = self.tasks[str(task_id)]
        task.update({k: v for k, v in updates.items() if v is not None})
        task["updated_at"] = datetime.now(timezone.utc)
        return task

    def get_task(self, task_id) -> dict | None:
        return self.tasks.get(str(task_id))

    def list_tasks(self, user_id, *, status: str | None = None, scope: str | None = None, q: str | None = None) -> list[dict]:
        items = [task for task in self.tasks.values() if task["user_id"] == str(user_id) and task.get("deleted_at") is None]
        if status:
            items = [task for task in items if task.get("status") == status]
        if q:
            items = [task for task in items if q in task.get("title", "") or q in task.get("original_text", "")]
        if scope:
            items = self._filter_scope(items, scope)
        return sorted(items, key=lambda item: item.get("start_datetime") or datetime.combine(item.get("due_date") or datetime.max.date(), datetime.min.time(), tzinfo=timezone.utc))

    def _filter_scope(self, items: Iterable[dict], scope: str) -> list[dict]:
        now = datetime.now(timezone.utc)
        today = now.date()
        if scope == "today":
            return [task for task in items if task.get("due_date") == today or (task.get("start_datetime") and task["start_datetime"].date() == today)]
        if scope == "tomorrow":
            target = today + timedelta(days=1)
            return [task for task in items if task.get("due_date") == target or (task.get("start_datetime") and task["start_datetime"].date() == target)]
        if scope == "this_week":
            start = today - timedelta(days=today.weekday())
            end = start + timedelta(days=6)
            return [task for task in items if self._task_date(task) and start <= self._task_date(task) <= end]
        if scope == "this_month":
            return [task for task in items if self._task_date(task) and self._task_date(task).month == today.month and self._task_date(task).year == today.year]
        if scope == "overdue":
            return [task for task in items if task.get("status") == "pending" and self._task_date(task) and self._task_date(task) < today]
        return list(items)

    @staticmethod
    def _task_date(task: dict):
        if task.get("start_datetime"):
            return task["start_datetime"].date()
        return task.get("due_date")

    def log_parse(self, payload: dict) -> None:
        self.parse_logs.append(payload)

    def log_sync(self, payload: dict) -> None:
        self.sync_logs.append(payload)

    def log_slack_message(self, payload: dict) -> None:
        self.slack_logs.append(payload)

    def find_tasks(self, user_id, keyword: str) -> list[dict]:
        keyword = keyword.strip()
        return [task for task in self.tasks.values() if task["user_id"] == str(user_id) and task.get("deleted_at") is None and keyword in task.get("title", "")]

    def save_context(self, user_id, channel_type: str, channel_id: str, context: dict) -> None:
        key = (str(user_id), channel_type, channel_id)
        context["updated_at"] = datetime.now(timezone.utc)
        self.contexts[key] = context

    def get_context(self, user_id, channel_type: str, channel_id: str) -> dict | None:
        key = (str(user_id), channel_type, channel_id)
        context = self.contexts.get(key)
        if not context:
            return None
        expiry = timedelta(minutes=get_settings().context_expiry_minutes)
        if datetime.now(timezone.utc) - context["updated_at"] > expiry:
            self.contexts.pop(key, None)
            return None
        return context

    def create_reminder_rule(self, rule: dict) -> dict:
        rule_id = str(rule.get("id", uuid4()))
        now = datetime.now(timezone.utc)
        rule = {**rule, "id": rule_id}
        rule.setdefault("enabled", True)
        rule.setdefault("created_at", now)
        rule.setdefault("updated_at", now)
        self.reminder_rules[rule_id] = rule
        return rule

    def list_active_reminder_rules(self) -> list[dict]:
        return [rule for rule in self.reminder_rules.values() if rule.get("enabled")]

    def create_google_connection(self, payload: dict) -> dict:
        self.google_connections[str(payload["user_id"])] = payload
        return payload

    def get_google_connection(self, user_id) -> dict | None:
        return self.google_connections.get(str(user_id))

    def create_slack_connection(self, payload: dict) -> dict:
        self.slack_connections[str(payload["user_id"])] = payload
        return payload

    def get_slack_connection(self, user_id) -> dict | None:
        return self.slack_connections.get(str(user_id))

    def enqueue_job(self, job_type: str, payload: dict, run_after: datetime | None = None) -> dict:
        job_id = str(uuid4())
        job = {"id": job_id, "job_type": job_type, "status": "queued", "payload_json": payload, "retry_count": 0, "run_after": run_after, "last_error": None, "created_at": datetime.now(timezone.utc), "updated_at": datetime.now(timezone.utc)}
        self.jobs[job_id] = job
        return job

    def list_jobs(self, job_type: str | None = None, status: str = "queued") -> list[dict]:
        jobs = [job for job in self.jobs.values() if job["status"] == status]
        if job_type:
            jobs = [job for job in jobs if job["job_type"] == job_type]
        return sorted(jobs, key=lambda item: item["created_at"])

    def mark_job_status(self, job_id: str, status: str, error: str | None = None) -> None:
        job = self.jobs[job_id]
        job["status"] = status
        job["last_error"] = error
        if status == "queued":
            job["retry_count"] += 1
        job["updated_at"] = datetime.now(timezone.utc)

    def mark_slack_event_processed(self, event_id: str) -> bool:
        if event_id in self.processed_slack_events:
            return False
        self.processed_slack_events.add(event_id)
        return True
