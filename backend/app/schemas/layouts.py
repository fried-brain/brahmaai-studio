import json
from typing import Literal

from pydantic import BaseModel, Field, computed_field, model_validator, field_validator

from app.services.geometry import validate_polygon


class CoordinateMM(BaseModel):
    x: float = Field(ge=-100000, le=100000)
    y: float = Field(ge=-100000, le=100000)


class OpeningInput(BaseModel):
    kind: Literal["door", "window"]
    edge_index: int = Field(ge=0, le=99)
    offset_mm: float = Field(ge=0, le=100000)
    width_mm: float = Field(gt=0, le=6000)
    height_mm: float = Field(gt=0, le=4000)
    sill_height_mm: float = Field(ge=0, le=3000, default=0)
    swing_direction: Literal["left", "right", "none"] = "none"

    @computed_field
    @property
    def head_height_mm(self) -> float:
        return self.sill_height_mm + self.height_mm

    @model_validator(mode="after")
    def sensible_vertical_dimensions(self):
        if self.kind == "door" and self.sill_height_mm != 0:
            raise ValueError("Door sill height must be zero")
        if self.kind == "window" and self.swing_direction != "none":
            raise ValueError("Window swing direction must be none")
        if self.sill_height_mm + self.height_mm > 5000:
            raise ValueError("Opening top height cannot exceed 5000 mm")
        return self



class FurnitureInput(BaseModel):
    item_id: str = Field(min_length=1, max_length=80)
    catalog_type: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=100)
    x_mm: float = Field(ge=-100000, le=100000)
    y_mm: float = Field(ge=-100000, le=100000)
    width_mm: float = Field(gt=0, le=20000)
    depth_mm: float = Field(gt=0, le=20000)
    rotation_deg: Literal[0, 90, 180, 270] = 0

    @field_validator("item_id", "catalog_type", "name")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Furniture identifiers and names cannot be blank")
        return value.strip()


class RoomInput(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    room_type: Literal["living", "bedroom", "kitchen", "bathroom", "dining", "study", "utility", "staircase", "corridor", "parking", "other"] = "other"
    vertices_mm: list[CoordinateMM] = Field(min_length=3, max_length=100)
    wall_thickness_mm: float = Field(default=150, ge=75, le=500)
    openings: list[OpeningInput] = Field(default_factory=list, max_length=100)
    furniture: list[FurnitureInput] | None = Field(default=None, max_length=100)

    @model_validator(mode="after")
    def valid_polygon(self):
        validate_polygon([(p.x, p.y) for p in self.vertices_mm])
        if self.furniture is not None:
            ids = [item.item_id for item in self.furniture]
            if len(ids) != len(set(ids)):
                raise ValueError("Furniture item IDs must be unique within a room")
        if not self.name.strip():
            raise ValueError("Room name cannot be blank")
        vertices = [(p.x, p.y) for p in self.vertices_mm]
        edge_intervals: dict[int, list[tuple[float, float]]] = {}
        for opening in self.openings:
            if opening.edge_index >= len(vertices):
                raise ValueError("Opening references a wall edge that does not exist")
            start = vertices[opening.edge_index]
            end = vertices[(opening.edge_index + 1) % len(vertices)]
            edge_length = ((end[0] - start[0]) ** 2 + (end[1] - start[1]) ** 2) ** 0.5
            finish = opening.offset_mm + opening.width_mm
            if finish > edge_length + 1e-7:
                raise ValueError("Opening must fit within its wall segment")
            intervals = edge_intervals.setdefault(opening.edge_index, [])
            if any(opening.offset_mm < previous_end and finish > previous_start for previous_start, previous_end in intervals):
                raise ValueError("Openings on the same wall cannot overlap")
            intervals.append((opening.offset_mm, finish))
        return self


class LayoutUpdate(BaseModel):
    floor_number: int = Field(ge=-5, le=50)
    rooms: list[RoomInput] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def unique_room_names(self):
        names = [room.name.strip().casefold() for room in self.rooms]
        if len(names) != len(set(names)):
            raise ValueError("Room names must be unique on a floor")
        return self


class RoomOutput(BaseModel):
    id: str
    name: str
    room_type: str
    vertices_mm: list[CoordinateMM]
    area_sq_ft: float
    perimeter_mm: float
    wall_thickness_mm: float = 150
    openings: list[OpeningInput] = Field(default_factory=list)
    furniture: list[FurnitureInput] = Field(default_factory=list)


class WallOutput(BaseModel):
    id: str
    start_mm: CoordinateMM
    end_mm: CoordinateMM
    length_mm: float
    room_ids: list[str]
    classification: Literal["internal", "external"]


class RoomAdjacencyOutput(BaseModel):
    room_ids: list[str]
    room_names: list[str]
    shared_wall_id: str
    shared_wall_length_mm: float
    connected_by_door: bool


class CirculationComponentOutput(BaseModel):
    room_ids: list[str]
    room_names: list[str]
    room_count: int


class LayoutOutput(BaseModel):
    floor_number: int
    rooms: list[RoomOutput]
    walls: list[WallOutput]
    adjacencies: list[RoomAdjacencyOutput] = Field(default_factory=list)
    circulation_components: list[CirculationComponentOutput] = Field(default_factory=list)


def parse_room(room) -> list[dict[str, float]]:
    return json.loads(room.geometry_json)
