from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, StrictFloat, StrictInt, StrictStr, field_validator, model_validator

from app.schemas.layouts import FurnitureInput, OpeningInput, RoomInput
from app.schemas.room_layout_candidates import UtilizationSummary


class StrictAIModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class AIClarification(StrictAIModel):
    type: Literal["clarification"]
    reply: StrictStr = Field(min_length=1, max_length=12000)
    clarifying_questions: list[StrictStr] = Field(default_factory=list, max_length=20)
    suggestions: list[StrictStr] = Field(default_factory=list, max_length=20)


class AIAnswer(StrictAIModel):
    type: Literal["answer"]
    reply: StrictStr = Field(min_length=1, max_length=12000)
    suggestions: list[StrictStr] = Field(default_factory=list, max_length=20)


class AIProposalCoordinate(StrictAIModel):
    x: StrictFloat = Field(ge=-100000, le=100000)
    y: StrictFloat = Field(ge=-100000, le=100000)


class AIProposalOpening(StrictAIModel):
    kind: Literal["door", "window"]
    edge_index: StrictInt = Field(ge=0, le=99)
    offset_mm: StrictFloat = Field(ge=0, le=100000)
    width_mm: StrictFloat = Field(gt=0, le=6000)
    height_mm: StrictFloat = Field(gt=0, le=4000)
    sill_height_mm: StrictFloat = Field(ge=0, le=3000, default=0)
    swing_direction: Literal["left", "right", "none"] = "none"


class AIProposalRoom(StrictAIModel):
    proposal_id: StrictStr = Field(min_length=1, max_length=80)
    name: StrictStr = Field(min_length=1, max_length=100)
    room_type: Literal["living", "bedroom", "kitchen", "bathroom", "dining", "study", "utility", "staircase", "corridor", "parking", "other"]
    vertices_mm: list[AIProposalCoordinate] = Field(min_length=3, max_length=100)
    wall_thickness_mm: StrictFloat = Field(default=150, ge=75, le=500)
    openings: list[AIProposalOpening] = Field(default_factory=list, max_length=100)
    furniture: list[FurnitureInput] | None = Field(default=None, max_length=100)

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Room name cannot be blank")
        return value

    @model_validator(mode="after")
    def validate_existing_room_contract(self):
        RoomInput.model_validate({
            "name": self.name,
            "room_type": self.room_type,
            "vertices_mm": [point.model_dump() for point in self.vertices_mm],
            "wall_thickness_mm": self.wall_thickness_mm,
            "openings": [opening.model_dump() for opening in self.openings],
            "furniture": [item.model_dump() for item in self.furniture] if self.furniture is not None else None,
        })
        return self


class LayoutProposalDraft(StrictAIModel):
    schema_version: Literal["1.0"]
    title: StrictStr = Field(min_length=1, max_length=160)
    assumptions: list[StrictStr] = Field(default_factory=list, max_length=40)
    warnings: list[StrictStr] = Field(default_factory=list, max_length=40)
    floor_number: StrictInt = Field(ge=-5, le=50)
    rooms: list[AIProposalRoom] = Field(min_length=1, max_length=100)
    candidate_key: StrictStr | None = Field(default=None, max_length=64)
    planner_version: StrictStr | None = Field(default=None, max_length=20)
    template: Literal["public_first", "private_first", "service_cluster", "largest_first", "adjacency_first"] | None = None
    score: StrictInt | None = Field(default=None, ge=0, le=100)
    score_breakdown: dict[str, StrictInt] = Field(default_factory=dict)
    unmet_preferences: list[StrictStr] = Field(default_factory=list, max_length=40)
    score_version: StrictStr = "1.0"
    search_status: Literal["complete", "budget_exhausted"] = "complete"
    utilization: UtilizationSummary | None = None
    circulation_components: list[list[StrictStr]] = Field(default_factory=list)

    @field_validator("title")
    @classmethod
    def title_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Proposal title cannot be blank")
        return value


class AILayoutProposal(StrictAIModel):
    type: Literal["layout_proposal"]
    reply: StrictStr = Field(min_length=1, max_length=12000)
    proposal: LayoutProposalDraft


AssistantAIResponse = Annotated[Union[AIClarification, AIAnswer, AILayoutProposal], Field(discriminator="type")]
_ASSISTANT_RESPONSE_ADAPTER = TypeAdapter(AssistantAIResponse)


def assistant_ai_json_schema() -> dict:
    return _ASSISTANT_RESPONSE_ADAPTER.json_schema()


def parse_assistant_ai_response(value: str | dict) -> AIClarification | AIAnswer | AILayoutProposal:
    if isinstance(value, str):
        import json
        value = json.loads(value)
    return _ASSISTANT_RESPONSE_ADAPTER.validate_python(value)
