from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse

from app.dependencies import get_google_auth_service, get_repository, get_slack_auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/google/start")
def start_google_oauth(user_id: str = Query(alias="userId"), auth_service=Depends(get_google_auth_service)):
    return {"authorizationUrl": auth_service.build_authorization_url(user_id)}


@router.get("/google/callback")
def google_oauth_callback(code: str, state: str, repository=Depends(get_repository), auth_service=Depends(get_google_auth_service)):
    try:
        token_payload = auth_service.exchange_code(code)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"google oauth failed: {exc}") from exc
    repository.create_google_connection({"user_id": state, **token_payload})
    return RedirectResponse(url="/")


@router.get("/slack/start")
def start_slack_oauth(user_id: str = Query(alias="userId"), auth_service=Depends(get_slack_auth_service)):
    return {"authorizationUrl": auth_service.build_authorization_url(user_id)}


@router.get("/slack/callback")
def slack_oauth_callback(code: str, state: str, repository=Depends(get_repository), auth_service=Depends(get_slack_auth_service)):
    try:
        token_payload = auth_service.exchange_code(code)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"slack oauth failed: {exc}") from exc
    repository.create_slack_connection({"user_id": state, **token_payload})
    return RedirectResponse(url="/")
