from typing import Literal
from pydantic import BaseModel, Field
from app.schemas.layouts import FurnitureInput, RoomInput

class FurnitureIssue(BaseModel):
    code: str
    severity: Literal["error", "warning"]
    message: str
    item_ids: list[str] = Field(default_factory=list)

class FurnitureArrangementCandidate(BaseModel):
    candidate_key: str
    solver_version: str = "1.0"
    placements: list[FurnitureInput]
    issues: list[FurnitureIssue] = Field(default_factory=list)
    score: float = 0
    assumptions: list[str] = Field(default_factory=list)
    unmet_preferences: list[str] = Field(default_factory=list)

class FurniturePlannerResult(BaseModel):
    status: Literal["complete", "search_exhausted", "unsupported_geometry", "infeasible"]
    candidates: list[FurnitureArrangementCandidate] = Field(default_factory=list)
    explored: int = 0

class OpeningSuggestion(BaseModel):
    room_name: str
    kind: Literal["door", "window"]
    edge_index: int
    offset_mm: float
    width_mm: float
    reason: str
    assumptions: list[str] = Field(default_factory=list)

class RoomUsability(BaseModel):
    room_name: str
    area_mm2: float
    furniture_area_mm2: float
    unoccupied_area_mm2: float
    issues: list[FurnitureIssue] = Field(default_factory=list)

class DesignOptimizationPreviewInput(BaseModel):
    floor_number: int = Field(ge=-5, le=50)
    operation: Literal["furniture_arrangement", "opening_suggestions", "full_review"]
    room_ids: list[str] | None = Field(default=None, max_length=100)
    requested_items_by_room: dict[str, list[FurnitureInput]] = Field(default_factory=dict)
    clearance_preferences: dict[str, float] = Field(default_factory=dict)

class DesignOptimizationApplyInput(BaseModel):
    floor_number: int = Field(ge=-5, le=50)
    source_layout_fingerprint: str = Field(min_length=64, max_length=64)
    rooms: list[RoomInput] = Field(min_length=1, max_length=100)

class DesignOptimizationPreview(BaseModel):
    source_layout_fingerprint: str
    operation: str
    candidates: dict[str, FurniturePlannerResult] = Field(default_factory=dict)
    opening_suggestions: list[OpeningSuggestion] = Field(default_factory=list)
    room_analyses: list[RoomUsability] = Field(default_factory=list)
    issues: list[FurnitureIssue] = Field(default_factory=list)
    solver_version: str = "1.0"
