from types import SimpleNamespace

from app.services.room_planning_interpreter import parse_room_planning_brief


class FakeClient:
    def __init__(self, status, reply=None):
        self._status = status
        self.reply = reply
        self.calls = []

    def status(self):
        return self._status

    def chat(self, messages, schema):
        self.calls.append((messages, schema))
        return SimpleNamespace(text=self.reply, model="local-test")


def test_unavailable_local_model_returns_typed_result_without_chat_call():
    client = FakeClient(SimpleNamespace(code="model_unavailable", message="Local model unavailable"))
    result = parse_room_planning_brief(client, [], {"plot": None}, 0)
    assert result.status == "model_unavailable"
    assert result.brief is None
    assert client.calls == []


def test_interpreter_parses_typed_brief_and_never_accepts_model_geometry():
    reply = '{"type":"planning_brief","reply":"Ready","brief":{"floor_number":0,"required_rooms":[{"room_type":"living","quantity":1}],"adjacency_preferences":[],"privacy_preferences":[],"circulation_preferences":[],"entrance_side":null,"orientation_preferences":[],"vastu_mode":"off","hard_constraints":[],"notes":""}}'
    client = FakeClient(SimpleNamespace(code="ready", message="ready"), reply)
    result = parse_room_planning_brief(client, [], {"plot": {"shape": "rectangle"}}, 0)
    assert result.status == "brief"
    assert result.brief.required_rooms[0].room_type == "living"
    assert "coordinates" in client.calls[0][0][0]["content"].lower()


def test_interpreter_returns_invalid_model_response_for_coordinate_payload():
    reply = '{"type":"planning_brief","reply":"Ready","brief":{"floor_number":0,"required_rooms":[{"room_type":"living","quantity":1}],"adjacency_preferences":[],"privacy_preferences":[],"circulation_preferences":[],"entrance_side":null,"orientation_preferences":[],"vastu_mode":"off","hard_constraints":[],"notes":"","coordinates":[1,2]}}'
    client = FakeClient(SimpleNamespace(code="ready", message="ready"), reply)
    result = parse_room_planning_brief(client, [], {"plot": {"shape": "rectangle"}}, 0)
    assert result.status == "invalid_model_response"
    assert result.brief is None
