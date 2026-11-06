from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ProposalValidationIssue(BaseModel):
    path: str
    message: str


class ProposalValidationResult(BaseModel):
    valid: bool
    issues: list[ProposalValidationIssue] = Field(default_factory=list)


class AssistantProposalRecordOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    conversation_id: str
    project_id: str
    floor_number: int
    status: Literal["draft", "needs_revision", "applied", "rejected"]
    proposal_json: str
    validation_issues_json: str
    base_layout_hash: str
    created_at: datetime
    updated_at: datetime
    applied_at: datetime | None = None


class ApplyAssistantProposalInput(BaseModel):
    proposal: dict
