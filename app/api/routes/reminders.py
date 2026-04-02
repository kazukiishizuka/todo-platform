from fastapi import APIRouter, Depends

from app.dependencies import get_repository
from app.schemas import ReminderRuleCreateRequest

router = APIRouter(prefix="/reminder-rules", tags=["reminders"])


@router.post("")
def create_reminder_rule(payload: ReminderRuleCreateRequest, repository=Depends(get_repository)):
    rule = repository.create_reminder_rule({"user_id": payload.userId, "slack_channel_id": payload.slackChannelId, "reminder_type": payload.reminderType, "frequency": payload.frequency, "day_of_week": payload.dayOfWeek, "time_of_day": payload.timeOfDay, "timezone": payload.timezone, "enabled": True})
    return {"status": "created", "id": str(rule["id"])}
