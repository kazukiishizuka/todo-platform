from __future__ import annotations

from app.services.google_sync import GoogleSyncService
from app.services.slack_client import SlackClient


class JobWorker:
    def __init__(self, repository, google_sync: GoogleSyncService, slack_client: SlackClient) -> None:
        self.repository = repository
        self.google_sync = google_sync
        self.slack_client = slack_client

    def run_once(self) -> list[dict]:
        results = []
        for job in self.repository.list_jobs(status="queued"):
            try:
                if job["job_type"] == "google_sync":
                    payload = self.google_sync.execute_job(self.repository, job)
                elif job["job_type"] == "slack_post":
                    payload = self.slack_client.post_message(job["payload_json"]["channelId"], job["payload_json"]["text"], job["payload_json"].get("blocks"))
                else:
                    payload = {"status": "skipped"}
                self.repository.mark_job_status(job["id"], "completed")
                results.append({"jobId": job["id"], "status": "completed", "payload": payload})
            except Exception as exc:
                self.repository.mark_job_status(job["id"], "failed", str(exc))
                if job["job_type"] == "google_sync":
                    self.google_sync.mark_failure(self.repository, job["payload_json"]["taskId"], str(exc))
                results.append({"jobId": job["id"], "status": "failed", "error": str(exc)})
        return results
