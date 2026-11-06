from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.services.geometry import validate_polygon

Unit = Literal["mm", "cm", "m", "in", "ft"]
Orientation = Literal["north", "east", "south", "west", "northeast", "southeast", "southwest", "northwest"]


class PointInput(BaseModel):
    x: float = Field(ge=-100000, le=100000)
    y: float = Field(ge=-100000, le=100000)


class RectanglePlotInput(BaseModel):
    shape: Literal["rectangle"] = "rectangle"
    width: float = Field(gt=0, le=100000)
    length: float = Field(gt=0, le=100000)
    unit: Unit = "ft"
    orientation: Orientation | None = None
    road_facing_side: Orientation | None = None


class PolygonPlotInput(BaseModel):
    shape: Literal["polygon"]
    vertices: list[PointInput] = Field(min_length=3, max_length=500)
    unit: Unit = "ft"
    orientation: Orientation | None = None
    road_facing_side: Orientation | None = None

    @model_validator(mode="after")
    def validate_geometry(self):
        factor = unit_factor_mm(self.unit)
        points = [(round(p.x * factor, 3), round(p.y * factor, 3)) for p in self.vertices]
        validate_polygon(points)
        return self


PlotInput = Annotated[RectanglePlotInput | PolygonPlotInput, Field(discriminator="shape")]
PlotUpdate = PlotInput


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    category: Literal["residential", "commercial", "industrial", "other"] = "residential"
    plot: PlotInput | None = None


class PlotResponse(BaseModel):
    shape: str
    width_mm: float | None
    length_mm: float | None
    display_unit: str
    orientation: str | None
    road_facing_side: str | None
    area_sq_ft: float | None
    perimeter_mm: float | None = None
    vertices_mm: list[dict[str, float]] | None = None


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    category: str
    status: str
    created_at: datetime
    updated_at: datetime
    plot: PlotResponse | None


def unit_factor_mm(unit: Unit) -> float:
    return {"mm": 1.0, "cm": 10.0, "m": 1000.0, "in": 25.4, "ft": 304.8}[unit]


def to_mm(value: float, unit: Unit) -> float:
    return round(value * unit_factor_mm(unit), 3)


def area_sq_ft(width_mm: float, length_mm: float) -> float:
    return round((width_mm * length_mm) / (304.8**2), 3)


def serialize_project(project) -> dict:
    from app.services.geometry import polygon_area_mm2, polygon_perimeter_mm
    import json

    plot = None
    if project.plot is not None:
        p = project.plot
        vertices = json.loads(p.geometry_json) if p.geometry_json else None
        if vertices:
            points = [(item["x"], item["y"]) for item in vertices]
            area = round(polygon_area_mm2(points) / (304.8**2), 3)
            perimeter = round(polygon_perimeter_mm(points), 3)
        elif p.width_mm and p.length_mm:
            area = area_sq_ft(p.width_mm, p.length_mm)
            perimeter = round(2 * (p.width_mm + p.length_mm), 3)
        else:
            area = perimeter = None
        plot = {
            "shape": p.shape,
            "width_mm": p.width_mm,
            "length_mm": p.length_mm,
            "display_unit": p.display_unit,
            "orientation": p.orientation,
            "road_facing_side": p.road_facing_side,
            "area_sq_ft": area,
            "perimeter_mm": perimeter,
            "vertices_mm": vertices,
        }
    return {
        "id": project.id,
        "name": project.name,
        "category": project.category,
        "status": project.status,
        "created_at": project.created_at,
        "updated_at": project.updated_at,
        "plot": plot,
    }
