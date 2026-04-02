from fastapi import APIRouter, Depends, Header, HTTPException

from app.config import get_settings
from app.dependencies import build_job_worker, build_reminder_worker, get_repository

router = APIRouter(prefix="/internal", tags=["internal"])


def verify_internal_token(x_internal_token: str = Header(default="")):
    expected = get_settings().internal_token
    if not expected or x_internal_token != expected:
        raise HTTPException(status_code=401, detail="invalid internal token")


@router.post("/google-sync/run")
def run_google_sync(repository=Depends(get_repository), _=Depends(verify_internal_token)):
    results = [result for result in build_job_worker(repository).run_once() if result.get("payload") or result.get("error")]
    return {"status": "ok", "results": results}


@router.post("/reminders/run")
def run_reminders(repository=Depends(get_repository), _=Depends(verify_internal_token)):
    return {"status": "ok", "deliveries": build_reminder_worker(repository).run_due_rules()}


@router.post("/jobs/run")
def run_jobs(repository=Depends(get_repository), _=Depends(verify_internal_token)):
    return {"status": "ok", "results": build_job_worker(repository).run_once()}
