from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.services.google_calendar_client import GoogleCalendarClient


class GoogleSyncService:
    def __init__(self, client: GoogleCalendarClient | None = None) -> None:
        self.client = client

    def build_sync_payload(self, task: dict, operation: str) -> dict:
        payload = {
            "summary": task["title"],
            "description": task.get("description") or task.get("original_text"),
            "extendedProperties": {"private": {"taskId": str(task["id"])}},
        }
        if task.get("is_all_day") and task.get("due_date"):
            payload["start"] = {"date": task["due_date"].isoformat()}
            payload["end"] = {"date": task["due_date"].isoformat()}
        elif task.get("start_datetime"):
            payload["start"] = {"dateTime": task["start_datetime"].isoformat(), "timeZone": task["timezone"]}
            payload["end"] = {"dateTime": task.get("end_datetime").isoformat() if task.get("end_datetime") else task["start_datetime"].isoformat(), "timeZone": task["timezone"]}
        if task.get("recurrence_rule"):
            payload["recurrence"] = [task["recurrence_rule"]]
        return {"taskId": str(task["id"]), "operation": operation, "event": payload, "googleEventId": task.get("google_event_id")}

    def queue_sync(self, repository, task: dict, operation: str) -> dict:
        payload = self.build_sync_payload(task, operation)
        repository.log_sync({"task_id": task["id"], "provider": "google_calendar", "operation_type": operation, "status": "queued", "error_message": None, "payload_json": payload, "created_at": datetime.now(timezone.utc)})
        repository.update_task(task["id"], {"google_sync_status": "queued", "last_sync_error": None})
        job = repository.enqueue_job("google_sync", payload)
        return {"status": "queued", "jobId": job["id"]}

    def execute_job(self, repository, job: dict) -> dict:
        payload = job["payload_json"]
        task = repository.update_task(payload["taskId"], {})
        connection = repository.get_google_connection(task["user_id"])
        if not connection:
            raise RuntimeError("google connection not found")
        access_token = connection["access_token"]
        if payload["operation"] == "create":
            event = self.client.create_event(access_token, payload["event"])
            repository.update_task(payload["taskId"], {"google_event_id": event.get("id"), "google_sync_status": "synced"})
            return event
        if payload["operation"] == "update":
            event_id = payload.get("googleEventId") or task.get("google_event_id")
            if not event_id:
                event = self.client.create_event(access_token, payload["event"])
                repository.update_task(payload["taskId"], {"google_event_id": event.get("id"), "google_sync_status": "synced"})
                return event
            event = self.client.update_event(access_token, event_id, payload["event"])
            repository.update_task(payload["taskId"], {"google_sync_status": "synced"})
            return event
        if payload["operation"] == "delete":
            event_id = payload.get("googleEventId") or task.get("google_event_id")
            if event_id:
                self.client.delete_event(access_token, event_id)
            repository.update_task(payload["taskId"], {"google_sync_status": "deleted"})
            return {"status": "deleted"}
        raise RuntimeError(f"unsupported job operation: {payload['operation']}")

    def mark_failure(self, repository, task_id, error_message: str) -> None:
        task = repository.update_task(task_id, {})
        repository.update_task(task_id, {"google_sync_status": "failed", "sync_retry_count": task.get("sync_retry_count", 0) + 1, "last_sync_error": error_message})
        repository.log_sync({"task_id": task_id, "provider": "google_calendar", "operation_type": "retry", "status": "failed", "error_message": error_message, "payload_json": {"taskId": str(task_id)}, "created_at": datetime.now(timezone.utc)})
