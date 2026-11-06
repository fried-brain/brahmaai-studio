from app.schemas.layouts import RoomInput, FurnitureInput
from app.services.furniture_catalog import catalog_for_room
from app.services.furniture_geometry import furniture_bounds, validate_furniture
from app.services.furniture_planner import generate_furniture_arrangements
from app.services.opening_optimizer import suggest_openings
from app.services.room_usability import analyze_room_usability


def room(furniture=None, vertices=None):
    return RoomInput(name='Bedroom',room_type='bedroom',vertices_mm=vertices or [{'x':0,'y':0},{'x':5000,'y':0},{'x':5000,'y':4000},{'x':0,'y':4000}],furniture=furniture or [])


def item(x=1500,y=1500):
    return FurnitureInput(item_id='bed',catalog_type='bed_double',name='Bed',x_mm=x,y_mm=y,width_mm=1400,depth_mm=2000)


def test_catalog_is_stable_and_room_filtered():
    assert catalog_for_room('bedroom') == catalog_for_room('bedroom')
    assert {v['catalog_type'] for v in catalog_for_room('bedroom')} >= {'bed_double','wardrobe'}
    assert all('bed' not in v['catalog_type'] for v in catalog_for_room('living'))


def test_geometry_rotates_footprint_and_detects_overlaps_and_wall_margin():
    a=item(); b=item(1500,1500).model_copy(update={'item_id':'second'})
    assert furniture_bounds(a)==(800,500,2200,2500)
    assert any(i.code=='furniture_overlap' for i in validate_furniture(room([a,b]),[a,b]))
    assert any(i.code=='furniture_outside_room' for i in validate_furniture(room([item(300,300)]),[item(300,300)]))


def test_planner_is_deterministic_and_rejects_unsupported_geometry():
    r=room([item()])
    first=generate_furniture_arrangements(r,[item()]); second=generate_furniture_arrangements(r,[item()])
    assert first.model_dump()==second.model_dump()
    assert first.status=='complete'
    irregular=room(vertices=[{'x':0,'y':0},{'x':5000,'y':0},{'x':4000,'y':4000},{'x':0,'y':4000}])
    assert generate_furniture_arrangements(irregular,[item()]).status=='unsupported_geometry'


def test_opening_suggestions_and_usability_are_advisory_and_non_mutating():
    r=room([item()]); before=r.model_dump()
    assert suggest_openings([r],{'plot_vertices':[(0,0),(5000,0),(5000,4000),(0,4000)]},0)
    result=analyze_room_usability([r])
    assert result[0].area_mm2==20_000_000
    assert result[0].unoccupied_area_mm2==17_200_000
    assert r.model_dump()==before


def test_planner_returns_up_to_three_distinct_stable_arrangements():
    r=room([item()])
    result=generate_furniture_arrangements(r,[item()])
    assert len(result.candidates) == 3
    assert len({candidate.candidate_key for candidate in result.candidates}) == 3
    assert generate_furniture_arrangements(r,[item()]).model_dump() == result.model_dump()
