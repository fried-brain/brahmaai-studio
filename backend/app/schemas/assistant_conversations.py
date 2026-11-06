from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AssistantMessageOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    role: str
    content: str
    engine: str
    model_name: str | None = None
    response_type: str | None = None
    proposal_json: str | None = None
    proposal_id: str | None = None
    created_at: datetime


class AssistantConversationSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    project_id: str
    floor_number: int
    title: str
    created_at: datetime
    updated_at: datetime


class AssistantConversationListItem(AssistantConversationSummary):
    message_count: int


class AssistantConversationDetail(AssistantConversationSummary):
    messages: list[AssistantMessageOutput]
