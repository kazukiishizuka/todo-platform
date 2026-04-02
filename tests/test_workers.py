import unittest
from uuid import uuid4

from app.repositories.memory import InMemoryTaskRepository
from app.services.google_sync import GoogleSyncService
from app.services.parser import NaturalLanguageParser
from app.services.task_service import TaskService
from app.workers.job_worker import JobWorker
from app.workers.reminder_worker import ReminderWorker


class DummySlackClient:
    def __init__(self):
        self.messages = []

    def post_message(self, channel_id: str, text: str, blocks=None):
        self.messages.append({"channel": channel_id, "text": text, "blocks": blocks or []})
        return {"ok": True}


class WorkerTests(unittest.TestCase):
    def setUp(self):
        self.repository = InMemoryTaskRepository()
        self.task_service = TaskService(self.repository, NaturalLanguageParser(), GoogleSyncService())
        self.slack_client = DummySlackClient()
        self.user_id = uuid4()

    def test_reminder_worker_enqueues_slack_post(self):
        self.task_service.parse_and_create(self.user_id, "chat", "room-1", "今日15時に面談", "Asia/Tokyo")
        self.repository.create_reminder_rule({"user_id": str(self.user_id), "slack_channel_id": "C123", "reminder_type": "daily_today_tasks", "frequency": "daily", "time_of_day": __import__('datetime').datetime.now().strftime('%H:%M'), "timezone": "Asia/Tokyo", "enabled": True})
        worker = ReminderWorker(self.repository, self.task_service, self.slack_client)
        deliveries = worker.run_due_rules()
        self.assertEqual(len(deliveries), 1)
        self.assertEqual(self.repository.list_jobs(job_type="slack_post")[0]["job_type"], "slack_post")

    def test_job_worker_posts_slack_message(self):
        self.repository.enqueue_job("slack_post", {"channelId": "C123", "text": "hello", "blocks": []})
        worker = JobWorker(self.repository, GoogleSyncService(), self.slack_client)
        results = worker.run_once()
        self.assertEqual(results[0]["status"], "completed")
        self.assertEqual(self.slack_client.messages[0]["text"], "hello")


if __name__ == "__main__":
    unittest.main()
