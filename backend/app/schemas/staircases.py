from typing import Literal

from pydantic import BaseModel, Field


class StaircasePreviewInput(BaseModel):
    floor_to_floor_mm: float = Field(gt=1500, le=6000)
    preferred_riser_mm: float = Field(gt=100, le=250)
    tread_depth_mm: float = Field(ge=180, le=450)
    clear_width_mm: float = Field(ge=600, le=3000)
    landing_depth_mm: float = Field(ge=600, le=6000)
    configuration: Literal["straight", "L", "U"] = "U"


class StaircasePreviewOutput(BaseModel):
    configuration: str
    floor_to_floor_mm: float
    riser_count: int
    actual_riser_mm: float
    total_rise_mm: float
    going_count: int
    tread_depth_mm: float
    flight_count: int
    risers_per_flight: list[int]
    flight_run_mm: float
    clear_width_mm: float
    landing_depth_mm: float
    comfort_sum_2r_plus_t_mm: float
    comfort_indicator: Literal["within_reference_band", "outside_reference_band"]
    notes: list[str]
    is_code_certified: Literal[False] = False
