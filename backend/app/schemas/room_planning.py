import json
from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, StrictFloat, StrictInt, StrictStr, TypeAdapter, model_validator


RoomType = Literal[
    "living", "bedroom", "kitchen", "bathroom", "dining", "study",
    "utility", "staircase", "corridor", "parking", "other",
]
Orientation = Literal["north", "east", "south", "west", "northeast", "southeast", "southwest", "northwest"]


class StrictPlanningModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class RoomRequirement(StrictPlanningModel):
    room_type: RoomType
    quantity: StrictInt = Field(ge=1, le=20)
    name: StrictStr | None = Field(default=None, min_length=1, max_length=80)
    preferred_width_mm: StrictInt | StrictFloat | None = Field(default=None, gt=0, le=50000)
    preferred_depth_mm: StrictInt | StrictFloat | None = Field(default=None, gt=0, le=50000)
    dimension_mode: Literal["preferred", "minimum", "exact"] = "preferred"
    allow_rotation: bool = True
    target_aspect_ratio: StrictFloat | StrictInt | None = Field(default=None, gt=0, le=20)
    long_axis_orientation: Literal["north_south", "east_west"] | None = None

    @model_validator(mode="after")
    def dimensions_are_paired(self):
        if (self.preferred_width_mm is None) != (self.preferred_depth_mm is None):
            raise ValueError("Preferred width and depth must be supplied together")
        return self


class RoomAdjacencyPreference(StrictPlanningModel):
    room_a: StrictStr = Field(min_length=1, max_length=80)
    room_b: StrictStr = Field(min_length=1, max_length=80)
    priority: Literal["must_be_adjacent", "prefer_adjacent"]

    @model_validator(mode="after")
    def distinct_rooms(self):
        if self.room_a.strip().casefold() == self.room_b.strip().casefold():
            raise ValueError("Adjacency preference must name two different rooms")
        return self


class RoomPrivacyPreference(StrictPlanningModel):
    room_a: StrictStr = Field(min_length=1, max_length=80)
    room_b: StrictStr = Field(min_length=1, max_length=80)
    relation: Literal["separate", "group"]
    priority: Literal["must", "prefer"] = "prefer"

    @model_validator(mode="after")
    def distinct_rooms(self):
        if self.room_a.strip().casefold() == self.room_b.strip().casefold():
            raise ValueError("Privacy preference must name two different rooms")
        return self


class RoomPlanningBrief(StrictPlanningModel):
    floor_number: StrictInt = Field(ge=-5, le=50)
    required_rooms: list[RoomRequirement] = Field(min_length=1, max_length=50)
    adjacency_preferences: list[RoomAdjacencyPreference] = Field(default_factory=list, max_length=50)
    privacy_preferences: list[RoomPrivacyPreference] = Field(default_factory=list, max_length=50)
    circulation_preferences: list[StrictStr] = Field(default_factory=list, max_length=20)
    entrance_side: Orientation | None = None
    orientation_preferences: list[StrictStr] = Field(default_factory=list, max_length=20)
    vastu_mode: Literal["off", "traditional_reference"] = "off"
    hard_constraints: list[StrictStr] = Field(default_factory=list, max_length=30)
    notes: StrictStr = Field(default="", max_length=1000)

    @model_validator(mode="after")
    def unique_adjacency_preferences(self):
        pairs = [tuple(sorted((item.room_a.strip().casefold(), item.room_b.strip().casefold()))) for item in self.adjacency_preferences]
        if len(pairs) != len(set(pairs)):
            raise ValueError("Duplicate adjacency preference pair")
        if sum(item.quantity for item in self.required_rooms) > 100:
            raise ValueError("A floor plan cannot contain more than 100 required room instances")
        return self


class PlanningClarification(StrictPlanningModel):
    type: Literal["clarification"]
    reply: StrictStr = Field(min_length=1, max_length=12000)
    questions: list[StrictStr] = Field(min_length=1, max_length=10)
    suggestions: list[StrictStr] = Field(default_factory=list, max_length=20)


class PlanningBriefResponse(StrictPlanningModel):
    type: Literal["planning_brief"]
    reply: StrictStr = Field(min_length=1, max_length=12000)
    brief: RoomPlanningBrief


PlanningModelResponse = Annotated[Union[PlanningClarification, PlanningBriefResponse], Field(discriminator="type")]
_RESPONSE_ADAPTER = TypeAdapter(PlanningModelResponse)


class PlanningBriefResult(BaseModel):
    status: Literal["brief", "clarification", "model_unavailable", "invalid_model_response"]
    brief: RoomPlanningBrief | None = None
    reply: str
    questions: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)
    error_code: str | None = None
    model: str | None = None


def room_planning_json_schema() -> dict:
    return _RESPONSE_ADAPTER.json_schema()


def parse_room_planning_response(value: str | dict) -> PlanningBriefResponse | PlanningClarification:
    if isinstance(value, str):
        value = json.loads(value)
    return _RESPONSE_ADAPTER.validate_python(value)
