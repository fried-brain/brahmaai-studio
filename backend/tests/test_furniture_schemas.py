import pytest
from pydantic import ValidationError
from app.schemas.layouts import FurnitureInput, RoomInput, RoomOutput


def furniture(**changes):
    data = dict(item_id="bed-1", catalog_type="bed_double", name="Double bed", x_mm=1500, y_mm=1500, width_mm=1400, depth_mm=2000, rotation_deg=0)
    data.update(changes)
    return data

@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
def test_furniture_accepts_quarter_turns(rotation):
    assert FurnitureInput.model_validate(furniture(rotation_deg=rotation)).rotation_deg == rotation

@pytest.mark.parametrize("changes", [{"rotation_deg": 45}, {"width_mm": 0}, {"depth_mm": -1}, {"item_id": " "}, {"name": ""}])
def test_furniture_rejects_invalid_dimensions_identity_and_rotation(changes):
    with pytest.raises(ValidationError):
        FurnitureInput.model_validate(furniture(**changes))

def test_room_rejects_duplicate_furniture_ids_and_more_than_100_items():
    room = dict(name="Bedroom", vertices_mm=[{"x":0,"y":0},{"x":4000,"y":0},{"x":4000,"y":4000},{"x":0,"y":4000}])
    with pytest.raises(ValidationError):
        RoomInput.model_validate({**room, "furniture": [furniture(), furniture(name="Duplicate")]})
    items = [furniture(item_id=f"item-{i}") for i in range(101)]
    with pytest.raises(ValidationError):
        RoomInput.model_validate({**room, "furniture": items})

def test_room_output_defaults_legacy_furniture_to_empty_array():
    out = RoomOutput.model_validate(dict(id="r", name="Room", room_type="other", vertices_mm=[{"x":0,"y":0}], area_sq_ft=1, perimeter_mm=1))
    assert out.furniture == []
