import unittest
from uuid import uuid4

from app.repositories.memory import InMemoryTaskRepository
from app.services.google_sync import GoogleSyncService
from app.services.parser import NaturalLanguageParser
from app.services.task_service import TaskService


class TaskServiceTests(unittest.TestCase):
    def setUp(self):
        self.repository = InMemoryTaskRepository()
        self.service = TaskService(self.repository, NaturalLanguageParser(), GoogleSyncService())
        self.user_id = uuid4()

    def test_create_task_and_queue_google_sync(self):
        result = self.service.parse_and_create(self.user_id, "chat", "room-1", "4月5日15時に面談", "Asia/Tokyo")
        self.assertEqual(result.status, "confirmed")
        self.assertEqual(result.task.title, "面談")
        self.assertEqual(result.googleSync["status"], "queued")
        self.assertEqual(len(self.repository.sync_logs), 1)

    def test_query_today_tasks(self):
        self.service.parse_and_create(self.user_id, "chat", "room-1", "今日15時に面談", "Asia/Tokyo")
        result = self.service.parse_and_create(self.user_id, "chat", "room-1", "今日のタスク教えて", "Asia/Tokyo")
        self.assertEqual(result["status"], "ok")
        self.assertEqual(len(result["items"]), 1)
        self.assertEqual(result["items"][0].taskType, "event")

    def test_create_backlog_task_without_date(self):
        result = self.service.parse_and_create(self.user_id, "chat", "room-1", "引っ越し準備", "Asia/Tokyo")
        self.assertEqual(result.status, "confirmed")
        self.assertEqual(result.task.taskType, "backlog_task")
        self.assertIsNone(result.task.dueDate)
        self.assertIsNone(result.task.startDatetime)

    def test_complete_by_title(self):
        create_result = self.service.parse_and_create(self.user_id, "chat", "room-1", "4月5日15時にレポート提出", "Asia/Tokyo")
        result = self.service.parse_and_create(self.user_id, "chat", "room-1", "レポート提出完了", "Asia/Tokyo")
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["task"].status, "completed")
        self.assertEqual(self.repository.get_task(create_result.task.id)["status"], "completed")

    def test_update_from_context(self):
        create_result = self.service.parse_and_create(self.user_id, "chat", "room-1", "4月5日15時に面談", "Asia/Tokyo")
        result = self.service.parse_and_create(self.user_id, "chat", "room-1", "それ16時にして", "Asia/Tokyo")
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["task"].startDatetime.hour, 16)
        self.assertEqual(self.repository.get_task(create_result.task.id)["start_datetime"].hour, 16)

    def test_query_dedupes_accidental_duplicates(self):
        self.service.parse_and_create(self.user_id, "chat", "room-1", "今日15時に面談", "Asia/Tokyo")
        self.service.parse_and_create(self.user_id, "chat", "room-1", "今日15時に面談", "Asia/Tokyo")
        result = self.service.parse_and_create(self.user_id, "chat", "room-1", "今日のタスク教えて", "Asia/Tokyo")
        self.assertEqual(result["status"], "ok")
        self.assertEqual(len(result["items"]), 1)

    def test_query_cleans_dirty_titles_for_display(self):
        self.repository.create_task(
            {
                "user_id": self.user_id,
                "title": "からミーティング",
                "original_text": "<@U0AR9GMMTSL> 明日11時からミーティング",
                "status": "pending",
                "timezone": "Asia/Tokyo",
                "due_date": None,
                "start_datetime": None,
                "end_datetime": None,
                "is_all_day": False,
            }
        )
        result = self.service.handle_intent(self.user_id, "chat", "room-1", "一覧", "Asia/Tokyo")
        self.assertEqual(result["items"][0].title, "ミーティング")

    def test_query_backlog_tasks(self):
        self.service.parse_and_create(self.user_id, "chat", "room-1", "引っ越し準備", "Asia/Tokyo")
        self.service.parse_and_create(self.user_id, "chat", "room-1", "明日15時に歯医者", "Asia/Tokyo")
        result = self.service.parse_and_create(self.user_id, "chat", "room-1", "バックログ見せて", "Asia/Tokyo")
        self.assertEqual(result["status"], "ok")
        self.assertEqual(len(result["items"]), 1)
        self.assertEqual(result["items"][0].taskType, "backlog_task")
        self.assertEqual(result["items"][0].title, "引っ越し準備")

    def test_repository_marks_processed_slack_events_once(self):
        self.assertTrue(self.repository.mark_slack_event_processed("Ev123"))
        self.assertFalse(self.repository.mark_slack_event_processed("Ev123"))


if __name__ == "__main__":
    unittest.main()
