from __future__ import annotations

import logging

from app.services.google_sync import GoogleSyncService
from app.services.slack_client import SlackClient


logger = logging.getLogger(__name__)


class JobWorker:
    def __init__(self, repository, google_sync: GoogleSyncService, slack_client: SlackClient) -> None:
        self.repository = repository
        self.google_sync = google_sync
        self.slack_client = slack_client

    def run_once(self) -> list[dict]:
        results = []
        for job in self.repository.list_jobs(status="queued"):
            logger.info("Processing job id=%s type=%s", job["id"], job["job_type"])
            try:
                if job["job_type"] == "google_sync":
                    payload = self.google_sync.execute_job(self.repository, job)
                elif job["job_type"] == "slack_post":
                    payload = self.slack_client.post_message(job["payload_json"]["channelId"], job["payload_json"]["text"], job["payload_json"].get("blocks"))
                else:
                    payload = {"status": "skipped"}
                self.repository.mark_job_status(job["id"], "completed")
                logger.info("Completed job id=%s type=%s", job["id"], job["job_type"])
                results.append({"jobId": job["id"], "status": "completed", "payload": payload})
            except Exception as exc:
                self.repository.mark_job_status(job["id"], "failed", str(exc))
                logger.warning("Failed job id=%s type=%s error=%s", job["id"], job["job_type"], exc)
                if job["job_type"] == "google_sync":
                    self.google_sync.mark_failure(self.repository, job["payload_json"]["taskId"], str(exc))
                results.append({"jobId": job["id"], "status": "failed", "error": str(exc)})
        return results
