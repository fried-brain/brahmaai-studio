import re


def _room_counts(message: str) -> dict[str, int]:
    patterns = {
        "bedrooms": r"(\d+)\s*(?:bed ?rooms?|bhk)",
        "bathrooms": r"(\d+)\s*(?:bath ?rooms?|bathrooms?)",
        "parking_spaces": r"(\d+)\s*(?:car\s*)?parking(?:\s*spaces?)?",
    }
    counts: dict[str, int] = {}
    lowered = message.casefold()
    for key, pattern in patterns.items():
        match = re.search(pattern, lowered)
        if match:
            counts[key] = int(match.group(1))
    return counts


def respond_to_design_message(message: str, project, floor_number: int, rooms: list) -> dict:
    text = message.strip()
    lowered = text.casefold()
    if not text:
        return {
            "reply": "Tell me what you want to design or review, and I’ll help turn it into an editable proposal.",
            "intent": "clarify",
            "clarifying_questions": ["What would you like to design or improve?"],
            "suggestions": [],
            "proposal": None,
            "changes_applied": False,
        }

    if any(term in lowered for term in ("review", "check my", "analyse", "analyze", "audit", "improve my")):
        if not rooms:
            return {
                "reply": f"There are no saved rooms on floor {floor_number} yet. Draw or save rooms first, then I can review their geometry and openings.",
                "intent": "review_layout",
                "clarifying_questions": [],
                "suggestions": ["Add room boundaries before requesting a layout review."],
                "proposal": None,
                "changes_applied": False,
            }
        no_window = [room.name for room in rooms if not any(item.get("kind") == "window" for item in _openings(room))]
        no_door = [room.name for room in rooms if not any(item.get("kind") == "door" for item in _openings(room))]
        suggestions = []
        if no_window:
            suggestions.append("No window opening is recorded for: " + ", ".join(no_window) + ". Verify daylight and ventilation needs for these rooms.")
        if no_door:
            suggestions.append("No door opening is recorded for: " + ", ".join(no_door) + ". Confirm access and circulation connections.")
        if not suggestions:
            suggestions.append("Every saved room has at least one recorded door and window. Review opening positions, clearances and actual site conditions manually.")
        return {
            "reply": f"I reviewed {len(rooms)} saved room boundaries on floor {floor_number}. Here are geometry-record checks based on the current saved data; they are not code or safety certification.",
            "intent": "review_layout",
            "clarifying_questions": [],
            "suggestions": suggestions,
            "proposal": None,
            "changes_applied": False,
        }

    if any(term in lowered for term in ("design", "plan", "create", "make", "need", "want")):
        counts = _room_counts(lowered)
        questions = []
        if "bedrooms" not in counts:
            questions.append("How many bedrooms do you need?")
        if "bathrooms" not in counts:
            questions.append("How many bathrooms should the home have?")
        if not any(term in lowered for term in ("ground floor", "g+", "storey", "floor", "single storey", "duplex")):
            questions.append("How many floors should the building have?")
        if not any(term in lowered for term in ("parking", "car porch", "garage")):
            questions.append("Do you need car parking, and if so, for how many cars?")
        plot = project.plot
        plot_details = None
        if plot is not None:
            plot_details = {
                "shape": plot.shape,
                "width_mm": plot.width_mm,
                "length_mm": plot.length_mm,
                "orientation": plot.orientation,
            }
        else:
            questions.insert(0, "What are the plot dimensions and measurement unit? Please define the plot in this project first.")
        if plot is not None and not plot.orientation:
            questions.append("Which direction does the plot face?")
        return {
            "reply": "I’ve extracted the requirements I could identify. Before proposing a room schedule, I need a few details. Nothing has been changed in your floor plan.",
            "intent": "design_brief",
            "clarifying_questions": questions,
            "suggestions": ["You can specify room dimensions, preferred kitchen/living placement, Vastu preferences, and accessibility needs in your next message."],
            "proposal": {
                "kind": "design_brief",
                "title": "Draft architectural brief",
                "details": {
                    "requested_counts": counts,
                    "plot": plot_details,
                    "floor_number": floor_number,
                    "existing_room_count": len(rooms),
                },
                "requires_user_approval": True,
            },
            "changes_applied": False,
        }

    return {
        "reply": "I can help prepare a design brief or review the saved floor plan. Try ‘Plan a 3-bedroom, 2-bathroom home’ or ‘Review my layout’. I’ll ask for missing details and won’t alter your drawing without approval.",
        "intent": "help",
        "clarifying_questions": [],
        "suggestions": ["Design requests create a draft brief; review requests inspect saved room and opening records."],
        "proposal": None,
        "changes_applied": False,
    }


def _openings(room) -> list[dict]:
    import json
    value = getattr(room, "openings_json", "[]") or "[]"
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return []
