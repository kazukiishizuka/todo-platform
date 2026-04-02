from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from app.schemas import ReminderMessage
from app.services.slack_client import SlackClient


class ReminderWorker:
    def __init__(self, repository, task_service, slack_client: SlackClient | None = None) -> None:
        self.repository = repository
        self.task_service = task_service
        self.slack_client = slack_client

    def run_due_rules(self, now: datetime | None = None) -> list[dict]:
        now = now or datetime.now(ZoneInfo("Asia/Tokyo"))
        deliveries = []
        for rule in self.repository.list_active_reminder_rules():
            if not self._is_due(rule, now):
                continue
            items = self.task_service.list_tasks(rule["user_id"], scope=self._scope_for_rule(rule["reminder_type"]), status="pending" if rule["reminder_type"] == "daily_unfinished_tasks" else None)
            message = self._compose_message(rule["reminder_type"], items)
            job = self.repository.enqueue_job("slack_post", {"channelId": rule["slack_channel_id"], "text": message.text, "blocks": message.blocks})
            deliveries.append({"channelId": rule["slack_channel_id"], "message": message.model_dump(), "ruleId": str(rule["id"]), "jobId": job["id"]})
        return deliveries

    @staticmethod
    def _is_due(rule: dict, now: datetime) -> bool:
        local_now = now.astimezone(ZoneInfo(rule["timezone"]))
        if local_now.strftime("%H:%M") != rule["time_of_day"]:
            return False
        if rule["frequency"] == "daily":
            return True
        if rule["frequency"] == "weekdays":
            return local_now.weekday() < 5
        if rule["frequency"] == "weekly":
            weekdays = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}
            return local_now.weekday() == weekdays.get((rule.get("day_of_week") or "mon").lower(), 0)
        return False

    @staticmethod
    def _scope_for_rule(reminder_type: str) -> str | None:
        return {"daily_today_tasks": "today", "today_events_and_tasks": "today", "weekly_summary": "this_week", "overdue_tasks": "overdue"}.get(reminder_type)

    @staticmethod
    def _compose_message(reminder_type: str, items) -> ReminderMessage:
        title = {"daily_today_tasks": "本日のタスク", "daily_unfinished_tasks": "未完了タスク", "weekly_summary": "今週の予定", "overdue_tasks": "期限切れタスク", "today_events_and_tasks": "本日の予定とTODO"}.get(reminder_type, "タスク一覧")
        if not items:
            return ReminderMessage(text=f"{title}はありません。")
        lines = [f"- {item.startDatetime.strftime('%H:%M')} {item.title}" if item.startDatetime else f"- {item.title}" for item in items]
        return ReminderMessage(text=f"{title}は{len(items)}件です。\n" + "\n".join(lines))
