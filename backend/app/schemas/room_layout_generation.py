from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator
from app.schemas.room_layout_candidates import UtilizationSummary


class LayoutGenerationInput(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    floor_number: int = Field(default=0, ge=-5, le=50)
    conversation_id: str | None = Field(default=None, min_length=1, max_length=36)

    @field_validator("message")
    @classmethod
    def message_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Message cannot be blank")
        return value

    def normalized_message(self) -> str:
        return self.message.strip()


class LayoutGenerationCandidateOutput(BaseModel):
    proposal_id: str
    candidate_key: str
    template: str
    score: int = Field(ge=0, le=100)
    score_breakdown: dict[str, int]
    score_version: str = "1.0"
    search_status: Literal["complete", "budget_exhausted"] = "complete"
    utilization: UtilizationSummary | None = None
    circulation_components: list[list[str]] = Field(default_factory=list)
    proposal: dict
    status: Literal["draft", "needs_revision", "applied", "rejected"]
    validation_issues: list[dict[str, str]] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


class LayoutGenerationOutput(BaseModel):
    outcome: Literal[
        "layout_candidates", "clarification", "missing_plot", "unsupported_plot_geometry",
        "infeasible", "search_exhausted", "model_unavailable", "invalid_model_response",
    ]
    reply: str
    questions: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)
    conversation_id: str
    planner_version: str = "2.0"
    search_status: Literal["complete", "budget_exhausted"] = "complete"
    candidates: list[LayoutGenerationCandidateOutput] = Field(default_factory=list, max_length=3)
    reasons: list[str] = Field(default_factory=list)
