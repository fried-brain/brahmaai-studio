from app.schemas.layouts import RoomInput
from app.schemas.design_optimization import OpeningSuggestion


def _edge_key(a, b):
    return tuple(sorted((tuple(a), tuple(b))))


def suggest_openings(rooms: list[RoomInput], plot_context: dict, floor_number: int) -> list[OpeningSuggestion]:
    """Return advisory openings only on known shared/exterior wall segments."""
    plot = plot_context.get("plot_vertices") or []
    exterior = set(_edge_key(plot[i], plot[(i+1) % len(plot)]) for i in range(len(plot))) if len(plot) >= 3 else set()
    edges = {}
    for room in rooms:
        points=[(p.x,p.y) for p in room.vertices_mm]
        for index,(start,end) in enumerate(zip(points,points[1:]+points[:1])):
            edges.setdefault(_edge_key(start,end),[]).append((room,index,start,end))
    suggestions=[]
    for edge, owners in edges.items():
        length=((edge[1][0]-edge[0][0])**2+(edge[1][1]-edge[0][1])**2)**0.5
        if length < 600: continue
        if len(owners)==2:
            for room,index,_,_ in owners:
                if not any(o.kind=="door" and o.edge_index==index for o in room.openings) and length>=900:
                    suggestions.append(OpeningSuggestion(room_name=room.name,kind="door",edge_index=index,offset_mm=(length-900)/2,width_mm=900,reason="Potential door on a shared wall connecting adjacent rooms.",assumptions=["Confirm privacy, furniture clearance and the intended circulation route."]))
        elif edge in exterior:
            room,index,_,_=owners[0]
            if not any(o.kind=="window" and o.edge_index==index for o in room.openings):
                suggestions.append(OpeningSuggestion(room_name=room.name,kind="window",edge_index=index,offset_mm=(length-600)/2,width_mm=600,reason="Potential window on an exterior wall.",assumptions=["Daylight, ventilation, setbacks and local rules are not simulated."]))
    return suggestions
