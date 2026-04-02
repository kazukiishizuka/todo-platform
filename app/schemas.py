from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal
from uuid import UUID

try:
    from pydantic import BaseModel, Field
except ModuleNotFoundError:
    class BaseModel:
        def __init__(self, **kwargs):
            annotations = {}
            for cls in reversed(self.__class__.__mro__):
                annotations.update(getattr(cls, "__annotations__", {}))
            for key in annotations:
                default = getattr(self.__class__, key, None)
                source_value = kwargs[key] if key in kwargs else default
                if isinstance(source_value, list):
                    value = list(source_value)
                elif isinstance(source_value, dict):
                    value = dict(source_value)
                else:
                    value = source_value
                setattr(self, key, value)

        def model_dump(self, mode: str | None = None) -> dict[str, Any]:
            return dict(self.__dict__)

    def Field(default=None, default_factory=None):
        if default_factory is not None:
            return default_factory()
        return default


TaskStatus = Literal["pending", "completed", "canceled", "deleted", "snoozed"]
ParseStatus = Literal["confirmed", "needs_confirmation", "on_hold"]
TaskType = Literal["event", "deadline_task", "backlog_task"]


class ParseResult(BaseModel):
    original_text: str
    title: str
    description: str | None = None
    due_date: date | None = None
    start_datetime: datetime | None = None
    end_datetime: datetime | None = None
    timezone: str
    is_all_day: bool = False
    recurrence_rule: str | None = None
    confidence: float = 0.0
    ambiguity_flags: list[str] = Field(default_factory=list)
    parse_status: ParseStatus
    intent: str = "create"


class TaskCreateRequest(BaseModel):
    userId: UUID
    channelType: str
    channelId: str
    text: str
    timezone: str


class TaskResponse(BaseModel):
    id: UUID
    title: str
    description: str | None = None
    status: TaskStatus
    taskType: TaskType = "backlog_task"
    dueDate: date | None = None
    startDatetime: datetime | None = None
    endDatetime: datetime | None = None
    timezone: str
    isAllDay: bool
    recurrenceRule: str | None = None
    googleSyncStatus: str | None = None


class ParseAndCreateResponse(BaseModel):
    status: str
    task: TaskResponse | None = None
    googleSync: dict | None = None
    candidates: list[dict] = Field(default_factory=list)
    message: str | None = None


class TaskUpdateRequest(BaseModel):
    title: str | None = None
    description: str | None = None
    dueDate: date | None = None
    startDatetime: datetime | None = None
    endDatetime: datetime | None = None
    timezone: str | None = None
    status: TaskStatus | None = None
    recurrenceRule: str | None = None


class TaskQueryResponse(BaseModel):
    items: list[TaskResponse]


class SlackEventRequest(BaseModel):
    slackWorkspaceId: str
    slackChannelId: str
    slackUserId: str
    text: str


class ReminderRuleCreateRequest(BaseModel):
    userId: UUID
    slackChannelId: str
    reminderType: str
    frequency: str
    dayOfWeek: str | None = None
    timeOfDay: str
    timezone: str


class ReminderMessage(BaseModel):
    text: str
    blocks: list[dict] = Field(default_factory=list)
