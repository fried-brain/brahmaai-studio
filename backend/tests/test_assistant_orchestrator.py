import json

from app.core.config import Settings
from app.models.project import Plot, Project, Room
from app.services.assistant_orchestrator import orchestrate_assistant_message
from app.services.assistant_context import build_bounded_history, build_project_context
from app.services.local_llm import LocalModelStatus, LocalModelReply


class FakeLLM:
    def __init__(self, status, text=None):
        self._status = status
        self.text = text
        self.messages = None

    def status(self):
        return self._status

    def chat(self, messages, schema):
        self.messages = messages
        return LocalModelReply(self.text, "test-model")


def ready_status():
    return LocalModelStatus(True, True, True, True, "ready", "ready")


def test_project_context_contains_only_selected_floor_and_plot_metadata():
    project = Project(name="Home", category="residential", owner_id="owner")
    project.plot = Plot(shape="rectangle", width_mm=9000, length_mm=15000, orientation="east")
    first = Room(name="Living", room_type="living", floor_number=0, geometry_json='[{"x":0,"y":0},{"x":4000,"y":0},{"x":4000,"y":4000}]', openings_json='[]')
    other = Room(name="Bedroom", room_type="bedroom", floor_number=1, geometry_json='[{"x":0,"y":0},{"x":3000,"y":0},{"x":3000,"y":3000}]', openings_json='[]')
    context = build_project_context(project, 0, [first, other])
    assert context["plot"]["orientation"] == "east"
    assert [room["name"] for room in context["rooms"]] == ["Living"]


def test_history_keeps_newest_messages_with_count_and_character_limits():
    messages = [
        {"role": "user", "content": "old"},
        {"role": "assistant", "content": "middle"},
        {"role": "user", "content": "newest"},
    ]
    assert build_bounded_history(messages, 2, 20) == messages[1:]
    assert build_bounded_history(messages, 12, 8) == [
        {"role": "assistant", "content": "le"}, {"role": "user", "content": "newest"}
    ]


def test_configured_local_model_returns_strict_ai_response():
    llm = FakeLLM(ready_status(), json.dumps({"type": "answer", "reply": "A courtyard can fit.", "suggestions": []}))
    turn = orchestrate_assistant_message(
        Settings(_env_file=None, local_llm_enabled=True, local_llm_model="test-model"), llm,
        {"plot": {"orientation": "east"}, "rooms": []}, [], "Can I add a courtyard?",
        fallback=lambda: {"reply": "fallback", "intent": "help", "suggestions": [], "clarifying_questions": [], "proposal": None},
    )
    assert turn.engine == "local_llm"
    assert turn.response_type == "answer"
    assert turn.reply == "A courtyard can fit."
    assert llm.messages[0]["role"] == "system"


def test_disabled_or_unavailable_model_uses_deterministic_fallback():
    fallback = {"reply": "Rule-based reply", "intent": "help", "suggestions": [], "clarifying_questions": [], "proposal": None}
    llm = FakeLLM(LocalModelStatus(False, False, False, False, "disabled", "disabled"))
    turn = orchestrate_assistant_message(Settings(_env_file=None), llm, {}, [], "help", fallback=lambda: fallback)
    assert turn.engine == "local_rules"
    assert turn.reply == "Rule-based reply"


def test_malformed_local_model_output_uses_fallback_and_no_proposal():
    fallback = {"reply": "Safe fallback", "intent": "help", "suggestions": [], "clarifying_questions": [], "proposal": None}
    llm = FakeLLM(ready_status(), "not json")
    turn = orchestrate_assistant_message(
        Settings(_env_file=None, local_llm_enabled=True, local_llm_model="test-model"), llm,
        {}, [], "design", fallback=lambda: fallback,
    )
    assert turn.engine == "local_rules"
    assert turn.proposal is None
    assert turn.reply == "Safe fallback"


def test_layout_proposal_for_another_floor_uses_safe_fallback():
    draft = {
        "type": "layout_proposal", "reply": "draft", "proposal": {
            "schema_version": "1.0", "title": "Other floor", "assumptions": [], "warnings": [],
            "floor_number": 1, "rooms": [{
                "proposal_id": "r1", "name": "Living", "room_type": "living",
                "vertices_mm": [{"x": 0.0, "y": 0.0}, {"x": 4000.0, "y": 0.0}, {"x": 4000.0, "y": 4000.0}],
                "wall_thickness_mm": 150.0, "openings": [],
            }],
        },
    }
    fallback = {"reply": "Safe floor fallback", "intent": "help", "suggestions": [], "clarifying_questions": [], "proposal": None}
    llm = FakeLLM(ready_status(), json.dumps(draft))
    turn = orchestrate_assistant_message(
        Settings(_env_file=None, local_llm_enabled=True, local_llm_model="test-model"), llm,
        {"floor_number": 0}, [], "design", fallback=lambda: fallback,
    )
    assert turn.engine == "local_rules"
    assert turn.proposal is None
    assert turn.reply == "Safe floor fallback"
