from __future__ import annotations

from zoneinfo import ZoneInfo
from uuid import NAMESPACE_URL, UUID, uuid5

from app.schemas import ReminderMessage, TaskUpdateRequest
from app.services.slack_client import SlackClient


class SlackBotService:
    def __init__(self, repository, task_service, slack_client: SlackClient | None = None) -> None:
        self.repository = repository
        self.task_service = task_service
        self.slack_client = slack_client

    def resolve_user_id(self, workspace_id: str, slack_user_id: str) -> UUID:
        return uuid5(NAMESPACE_URL, f"{workspace_id}:{slack_user_id}")

    def handle_message(self, workspace_id: str, channel_id: str, slack_user_id: str, text: str) -> dict:
        user_id = self.resolve_user_id(workspace_id, slack_user_id)
        result = self.task_service.parse_and_create(user_id, "slack", channel_id, text, "Asia/Tokyo")
        message = self._to_slack_message(result)
        self.repository.log_slack_message(
            {
                "user_id": str(user_id),
                "slack_channel_id": channel_id,
                "message_type": "conversation_reply",
                "payload_json": message.model_dump(),
                "status": "queued",
                "error_message": None,
                "sent_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc),
            }
        )
        self.repository.enqueue_job("slack_post", {"channelId": channel_id, "text": message.text, "blocks": message.blocks})
        return {"userId": str(user_id), "message": message.model_dump()}

    def handle_interaction(self, action_id: str) -> dict:
        operation, task_id = action_id.split(":", 1)
        if operation == "complete":
            task = self.task_service.complete_task(task_id)
            return self._interaction_response(f"「{task['title']}」を完了にしました。")
        if operation == "delete":
            task = self.task_service.delete_task(task_id)
            return self._interaction_response(f"「{task['title']}」を削除しました。")
        if operation == "snooze":
            task = self.task_service.update_task(task_id, TaskUpdateRequest(status="snoozed"))
            return self._interaction_response(f"「{task['title']}」を延期しました。")
        if operation == "detail":
            task = self.task_service.repository.get_task(task_id)
            if not task:
                return self._interaction_response("対象タスクが見つかりませんでした。")
            task_response = self.task_service._to_response(task)
            return self._interaction_response(self._format_task_line(task_response))
        return self._interaction_response("未対応の操作です。")

    def _to_slack_message(self, result) -> ReminderMessage:
        if isinstance(result, dict) and result.get("items") is not None:
            unique_lines = list(dict.fromkeys(self._format_task_line(task) for task in result["items"]))
            lines = [f"{index + 1}. {line}" for index, line in enumerate(unique_lines)]
            text = "\n".join(lines) if lines else "該当するタスクはありません。"
            return ReminderMessage(text=text)
        if hasattr(result, "status") and result.status == "confirmed" and result.task:
            text = f"{result.task.title} を登録しました。Google同期: {result.googleSync['status']}"
            return ReminderMessage(text=text, blocks=self._task_action_blocks(result.task.id, result.task.title))
        if isinstance(result, dict) and result.get("status") == "ok":
            task = result.get("task")
            return ReminderMessage(text=result.get("message", "処理しました。"), blocks=self._task_action_blocks(task.id, task.title) if task else [])
        if hasattr(result, "status") and result.status == "needs_confirmation":
            return ReminderMessage(text=result.message or "確認が必要です。")
        return ReminderMessage(text=getattr(result, "message", None) or result.get("message", "解釈できませんでした。"))

    @staticmethod
    def _interaction_response(text: str) -> dict:
        return {
            "response_type": "ephemeral",
            "replace_original": False,
            "delete_original": False,
            "text": text,
        }

    @staticmethod
    def _task_action_blocks(task_id, title: str) -> list[dict]:
        return [
            {
                "type": "actions",
                "elements": [
                    {"type": "button", "text": {"type": "plain_text", "text": "完了"}, "action_id": f"complete:{task_id}"},
                    {"type": "button", "text": {"type": "plain_text", "text": "延期"}, "action_id": f"snooze:{task_id}"},
                    {"type": "button", "text": {"type": "plain_text", "text": "削除"}, "action_id": f"delete:{task_id}"},
                    {"type": "button", "text": {"type": "plain_text", "text": "詳細"}, "action_id": f"detail:{task_id}"},
                ],
            }
        ]

    @staticmethod
    def _format_task_line(task) -> str:
        if task.startDatetime:
            local_dt = task.startDatetime.astimezone(ZoneInfo(task.timezone))
            return f"{local_dt.strftime('%m/%d %H:%M')} {task.title}"
        if task.dueDate:
            return f"{task.dueDate.strftime('%m/%d')} {task.title}"
        return f"期限未設定 {task.title}"