from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class CandidateScore(BaseModel):
    total: int = Field(ge=0, le=100)
    breakdown: dict[str, int]


class UtilizationSummary(BaseModel):
    plot_area_mm2: float = Field(ge=0)
    assigned_area_mm2: float = Field(ge=0)
    unallocated_area_mm2: float = Field(ge=0)
    utilization_percent: float = Field(ge=0, le=100)

    model_config = ConfigDict(extra="forbid")


class LayoutCandidate(BaseModel):
    candidate_key: str
    planner_version: str = "1.0"
    score_version: str = "1.0"
    search_status: Literal["complete", "budget_exhausted"] = "complete"
    utilization: UtilizationSummary | None = None
    circulation_components: list[list[str]] = Field(default_factory=list)
    template: Literal["public_first", "private_first", "service_cluster", "largest_first", "adjacency_first"]
    title: str
    rooms: list[dict]
    score: CandidateScore
    assumptions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    unmet_preferences: list[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")

    def proposal_payload(self, floor_number: int) -> dict:
        return {
            "schema_version": "1.0", "title": self.title,
            "assumptions": self.assumptions, "warnings": self.warnings,
            "floor_number": floor_number, "rooms": self.rooms,
            "candidate_key": self.candidate_key, "planner_version": self.planner_version,
            "score_version": self.score_version, "search_status": self.search_status,
            "utilization": self.utilization.model_dump(mode="json") if self.utilization else None,
            "circulation_components": self.circulation_components,
            "template": self.template, "score": self.score.total,
            "score_breakdown": self.score.breakdown,
            "unmet_preferences": self.unmet_preferences,
        }


class CandidateValidation(BaseModel):
    valid: bool
    issues: list[dict[str, str]] = Field(default_factory=list)


class PlannerResult(BaseModel):
    status: Literal["layout_candidates", "infeasible", "unsupported_plot_geometry", "search_exhausted"]
    candidates: list[LayoutCandidate] = Field(default_factory=list, max_length=3)
    reasons: list[str] = Field(default_factory=list)
    planner_version: str = "2.0"
    search_status: Literal["complete", "budget_exhausted"] = "complete"
