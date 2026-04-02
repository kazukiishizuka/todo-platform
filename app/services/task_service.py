from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID
from zoneinfo import ZoneInfo

from app.schemas import ParseAndCreateResponse, ParseResult, TaskResponse, TaskUpdateRequest
from app.services.google_sync import GoogleSyncService
from app.services.parser import NaturalLanguageParser


class TaskService:
    def __init__(self, repository, parser: NaturalLanguageParser, google_sync: GoogleSyncService) -> None:
        self.repository = repository
        self.parser = parser
        self.google_sync = google_sync

    def parse_and_create(self, user_id: UUID, channel_type: str, channel_id: str, text: str, timezone_name: str):
        parsed = self.parser.parse(text, timezone_name)
        self.repository.log_parse(
            {
                "task_id": None,
                "original_text": text,
                "parsed_json": parsed.model_dump(mode="json"),
                "confidence": parsed.confidence,
                "ambiguity_flags": parsed.ambiguity_flags,
                "created_at": datetime.now(timezone.utc),
            }
        )
        if parsed.intent != "create":
            return self.handle_intent(user_id, channel_type, channel_id, text, timezone_name, parsed)
        if parsed.parse_status == "needs_confirmation":
            return ParseAndCreateResponse(
                status="needs_confirmation",
                candidates=self._build_confirmation_candidates(parsed),
                message="曖昧な日時があるため確認が必要です。",
            )
        if parsed.parse_status == "on_hold":
            return ParseAndCreateResponse(status="on_hold", message="日時が特定できませんでした。補足を入力してください。")

        task = self.repository.create_task(self._task_dict(user_id, parsed))
        self.repository.log_parse(
            {
                "task_id": task["id"],
                "original_text": text,
                "parsed_json": parsed.model_dump(mode="json"),
                "confidence": parsed.confidence,
                "ambiguity_flags": parsed.ambiguity_flags,
                "created_at": datetime.now(timezone.utc),
            }
        )
        self.repository.save_context(
            user_id,
            channel_type,
            channel_id,
            {"last_referenced_task_ids": [str(task["id"])], "context_json": {"last_action": "create"}},
        )
        google_sync = self.google_sync.queue_sync(self.repository, task, "create") if self._should_sync(task) else {"status": "skipped"}
        return ParseAndCreateResponse(status="confirmed", task=self._to_response(task), googleSync=google_sync)

    def handle_intent(self, user_id: UUID, channel_type: str, channel_id: str, text: str, timezone_name: str, parsed=None):
        parsed = parsed or self.parser.parse(text, timezone_name)
        if parsed.intent == "query":
            scope, status, query = self._query_params_from_text(text)
            tasks = self._dedupe_tasks_for_display(self.repository.list_tasks(user_id, status=status, scope=scope, q=query))
            self.repository.save_context(
                user_id,
                channel_type,
                channel_id,
                {"last_referenced_task_ids": [str(task["id"]) for task in tasks[:10]], "context_json": {"last_action": "query", "scope": scope, "query": query}},
            )
            return {"status": "ok", "items": [self._to_response(task) for task in tasks]}
        target = self.resolve_target_task(user_id, channel_type, channel_id, text)
        if not target:
            return {"status": "needs_confirmation", "message": "対象タスクを特定できませんでした。"}
        if parsed.intent == "complete":
            updated = self.complete_task(target["id"])
            return {"status": "ok", "task": self._to_response(updated), "message": f"{updated['title']} を完了にしました。"}
        if parsed.intent == "delete":
            updated = self.delete_task(target["id"])
            return {"status": "ok", "task": self._to_response(updated), "message": f"{updated['title']} を削除しました。"}
        if parsed.intent == "update":
            updates = self._extract_updates(text, target, timezone_name)
            updated = self.update_task(target["id"], TaskUpdateRequest(**updates))
            return {"status": "ok", "task": self._to_response(updated), "message": f"{updated['title']} を更新しました。"}
        return {"status": "on_hold", "message": "この操作はまだ解釈できませんでした。"}

    def resolve_target_task(self, user_id: UUID, channel_type: str, channel_id: str, text: str):
        context = self.repository.get_context(user_id, channel_type, channel_id)
        if any(token in text for token in ["それ", "さっき", "今日のやつ"]):
            if context and context.get("last_referenced_task_ids"):
                task_id = context["last_referenced_task_ids"][0]
                return self.repository.get_task(task_id)
        sanitized = text
        for token in ["完了", "終わった", "消して", "削除", "キャンセル", "取り消し", "変更", "して", "変えて", "を"]:
            sanitized = sanitized.replace(token, "")
        candidates = self.repository.find_tasks(user_id, sanitized.strip())
        if len(candidates) == 1:
            return candidates[0]
        if len(candidates) > 1:
            return None
        if context and context.get("last_referenced_task_ids"):
            task_id = context["last_referenced_task_ids"][0]
            return self.repository.get_task(task_id)
        return None

    def list_tasks(self, user_id: UUID, status: str | None = None, scope: str | None = None, q: str | None = None):
        tasks = self.repository.list_tasks(user_id, status=status, scope=scope, q=q)
        return [self._to_response(task) for task in tasks]

    def update_task(self, task_id: UUID, request: TaskUpdateRequest):
        updates = {
            "title": request.title,
            "description": request.description,
            "due_date": request.dueDate,
            "start_datetime": request.startDatetime,
            "end_datetime": request.endDatetime,
            "timezone": request.timezone,
            "status": request.status,
            "recurrence_rule": request.recurrenceRule,
        }
        task = self.repository.update_task(task_id, updates)
        if self._should_sync(task):
            self.google_sync.queue_sync(self.repository, task, "update")
        return task

    def complete_task(self, task_id: UUID):
        return self.repository.update_task(task_id, {"status": "completed", "completed_at": datetime.now(timezone.utc)})

    def delete_task(self, task_id: UUID):
        task = self.repository.update_task(task_id, {"status": "deleted", "deleted_at": datetime.now(timezone.utc)})
        if task.get("google_event_id") or task.get("start_datetime"):
            self.google_sync.queue_sync(self.repository, task, "delete")
        return task

    def _task_dict(self, user_id: UUID, parsed: ParseResult) -> dict:
        return {
            "user_id": user_id,
            "title": parsed.title,
            "description": parsed.description,
            "original_text": parsed.original_text,
            "status": "pending",
            "due_date": parsed.due_date,
            "start_datetime": parsed.start_datetime,
            "end_datetime": parsed.end_datetime,
            "timezone": parsed.timezone,
            "is_all_day": parsed.is_all_day,
            "recurrence_rule": parsed.recurrence_rule,
            "parser_confidence": parsed.confidence,
            "parse_status": parsed.parse_status,
            "google_sync_status": "pending",
            "last_sync_error": None,
        }

    @staticmethod
    def _build_confirmation_candidates(parsed: ParseResult) -> list[dict]:
        if "weekday_needs_week_scope" in parsed.ambiguity_flags:
            return [
                {"label": "今週金曜 15:00", "value": "candidate_1"},
                {"label": "来週金曜 15:00", "value": "candidate_2"},
            ]
        return [{"label": parsed.original_text, "value": "candidate_1"}]

    @staticmethod
    def _display_title(task: dict) -> str:
        import re

        title = task["title"]
        title = re.sub(r"<@[^>]+>", " ", title)
        title = re.sub(r"^\s*(から|まで)\s*", "", title)
        title = re.sub(r"\s+(から|まで)\s+", " ", title)
        title = re.sub(r"\s+", " ", title).strip(" 。")
        return title or task["title"]

    @classmethod
    def _to_response(cls, task: dict) -> TaskResponse:
        return TaskResponse(
            id=task["id"],
            title=cls._display_title(task),
            description=task.get("description"),
            status=task["status"],
            taskType=cls._task_type(task),
            dueDate=task.get("due_date"),
            startDatetime=task.get("start_datetime"),
            endDatetime=task.get("end_datetime"),
            timezone=task["timezone"],
            isAllDay=task.get("is_all_day", False),
            recurrenceRule=task.get("recurrence_rule"),
            googleSyncStatus=task.get("google_sync_status"),
        )

    @staticmethod
    def _query_params_from_text(text: str):
        scope = None
        status = None
        query = None
        if "今日" in text:
            scope = "today"
        elif "明日" in text:
            scope = "tomorrow"
        elif "今週" in text:
            scope = "this_week"
        elif "今月" in text:
            scope = "this_month"
        elif "バックログ" in text or "中長期" in text or "期限未設定" in text:
            scope = "backlog"
        if "未完了" in text:
            status = "pending"
        elif "完了済み" in text:
            status = "completed"
        elif "期限切れ" in text:
            scope = "overdue"
        for marker in ["関連", "タスク", "予定", "見せて", "教えて", "だけ", "表示", "一覧", "今日", "明日", "今週", "今月", "バックログ", "中長期", "期限未設定", "未完了", "完了済み", "期限切れ", "ある？", "の"]:
            text = text.replace(marker, "")
        query = text.strip() or None
        return scope, status, query

    @staticmethod
    def _dedupe_tasks_for_display(tasks: list[dict]) -> list[dict]:
        unique_tasks: list[dict] = []
        seen_signatures: set[tuple] = set()
        for task in tasks:
            signature = (
                TaskService._display_title(task),
                task.get("status"),
                task.get("due_date"),
                task.get("start_datetime"),
                task.get("end_datetime"),
            )
            if signature in seen_signatures:
                continue
            seen_signatures.add(signature)
            unique_tasks.append(task)
        return unique_tasks

    def _extract_updates(self, text: str, target: dict, timezone_name: str) -> dict:
        parsed = self.parser.parse(text, timezone_name)
        updates = {}
        start_datetime = parsed.start_datetime
        if not start_datetime:
            hour, minute = self.parser._extract_time(text, [])
            if hour is not None:
                base = target.get("start_datetime")
                if base:
                    local_base = base.astimezone(ZoneInfo(timezone_name))
                    start_datetime = datetime(local_base.year, local_base.month, local_base.day, hour, minute, tzinfo=ZoneInfo(timezone_name))
        if start_datetime:
            duration = (target.get("end_datetime") - target.get("start_datetime")).total_seconds() / 60 if target.get("start_datetime") and target.get("end_datetime") else 60
            updates["startDatetime"] = start_datetime
            updates["endDatetime"] = start_datetime + timedelta(minutes=duration)
        if parsed.due_date:
            updates["dueDate"] = parsed.due_date
        title = parsed.title.strip()
        if title and title not in ["それ", "さっきのやつ"] and title != target["title"]:
            updates["title"] = title
        updates["timezone"] = timezone_name
        return updates

    @staticmethod
    def _should_sync(task: dict) -> bool:
        return bool(task.get("start_datetime") or task.get("google_event_id"))

    @staticmethod
    def _task_type(task: dict) -> str:
        if task.get("start_datetime"):
            return "event"
        if task.get("due_date"):
            return "deadline_task"
        return "backlog_task"
