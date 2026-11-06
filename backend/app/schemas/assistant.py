from typing import Literal

from pydantic import BaseModel, Field


class AssistantMessageInput(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    floor_number: int = Field(default=0, ge=-5, le=50)
    conversation_id: str | None = Field(default=None, min_length=1, max_length=36)

    def normalized_message(self) -> str:
        return self.message.strip()


class AssistantProposal(BaseModel):
    kind: str
    title: str
    details: dict
    requires_user_approval: bool = True


class AssistantMessageOutput(BaseModel):
    reply: str
    intent: str
    clarifying_questions: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)
    proposal: AssistantProposal | None = None
    changes_applied: bool = False
    engine: Literal["local_rules", "local_llm"] = "local_rules"
    conversation_id: str | None = None
    response_type: Literal["clarification", "answer", "layout_proposal"] = "answer"
    model: str | None = None
    proposal_id: str | None = None
    proposal_metadata: dict | None = None
