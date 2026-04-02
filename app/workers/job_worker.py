from __future__ import annotations

import logging
from datetime import datetime, timezone

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
                    payload_json = job["payload_json"]
                    if self.repository.has_recent_slack_delivery(payload_json["channelId"], payload_json["text"], payload_json.get("blocks")):
                        payload = {"ok": True, "skipped_duplicate": True}
                    else:
                        payload = self.slack_client.post_message(payload_json["channelId"], payload_json["text"], payload_json.get("blocks"))
                        self.repository.log_slack_message(
                            {
                                "user_id": "",
                                "slack_channel_id": payload_json["channelId"],
                                "message_type": "delivery",
                                "payload_json": payload_json,
                                "status": "sent",
                                "error_message": None,
                                "sent_at": datetime.now(timezone.utc),
                            }
                        )
                else:
                    payload = {"status": "skipped"}
                self.repository.mark_job_status(job["id"], "completed")
                logger.info("Completed job id=%s type=%s", job["id"], job["job_type"])
                results.append({"jobId": job["id"], "status": "completed", "payload": payload})
            except Exception as exc:
                self.repository.mark_job_status(job["id"], "failed", str(exc))
                if job["job_type"] == "slack_post":
                    payload_json = job["payload_json"]
                    self.repository.log_slack_message(
                        {
                            "user_id": "",
                            "slack_channel_id": payload_json["channelId"],
                            "message_type": "delivery",
                            "payload_json": payload_json,
                            "status": "failed",
                            "error_message": str(exc),
                            "sent_at": datetime.now(timezone.utc),
                        }
                    )
                logger.warning("Failed job id=%s type=%s error=%s", job["id"], job["job_type"], exc)
                if job["job_type"] == "google_sync":
                    self.google_sync.mark_failure(self.repository, job["payload_json"]["taskId"], str(exc))
                results.append({"jobId": job["id"], "status": "failed", "error": str(exc)})
        return results