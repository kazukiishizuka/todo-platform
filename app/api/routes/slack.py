import json
from urllib.parse import parse_qs

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import PlainTextResponse

from app.dependencies import build_slack_service, get_repository, get_slack_client
from app.schemas import SlackEventRequest

router = APIRouter(prefix="/slack", tags=["slack"])


@router.post("/events/message")
def slack_message(payload: SlackEventRequest, repository=Depends(get_repository)):
    return build_slack_service(repository).handle_message(payload.slackWorkspaceId, payload.slackChannelId, payload.slackUserId, payload.text)


@router.post("/events")
async def slack_events(
    request: Request,
    x_slack_request_timestamp: str = Header(default=""),
    x_slack_signature: str = Header(default=""),
    repository=Depends(get_repository),
    slack_client=Depends(get_slack_client),
):
    body = await request.body()
    payload = json.loads(body.decode())
    if payload.get("type") == "url_verification":
        return PlainTextResponse(payload["challenge"])
    if not slack_client.verify_signature(x_slack_request_timestamp, x_slack_signature, body):
        raise HTTPException(status_code=401, detail="invalid slack signature")
    event = payload.get("event", {})
    if event.get("type") == "message" and not event.get("bot_id"):
        return build_slack_service(repository).handle_message(payload.get("team_id", ""), event["channel"], event["user"], event.get("text", ""))
    return {"ok": True}


@router.post("/interactions")
async def slack_interactions(
    request: Request,
    x_slack_request_timestamp: str = Header(default=""),
    x_slack_signature: str = Header(default=""),
    repository=Depends(get_repository),
    slack_client=Depends(get_slack_client),
):
    body = await request.body()
    if not slack_client.verify_signature(x_slack_request_timestamp, x_slack_signature, body):
        raise HTTPException(status_code=401, detail="invalid slack signature")
    form = parse_qs(body.decode())
    payload = json.loads(form["payload"][0])
    action_id = payload["actions"][0]["action_id"]
    return build_slack_service(repository).handle_interaction(action_id)
