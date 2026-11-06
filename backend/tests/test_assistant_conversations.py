from sqlalchemy import select
from fastapi.testclient import TestClient

from app.main import create_app
from app.models import Project, User
from app.services.assistant_conversations import (
    append_message, create_conversation, get_owned_conversation, list_conversations, load_transcript,
)


def make_user_and_project(client: TestClient, email: str):
    client.post("/api/v1/auth/register", json={"email": email, "password": "StrongPass123!"})
    login = client.post("/api/v1/auth/login", json={"email": email, "password": "StrongPass123!"})
    headers = {"X-CSRF-Token": login.json()["csrf_token"]}
    project_response = client.post("/api/v1/projects", headers=headers, json={"name": "Assistant project"})
    return headers, project_response.json()["id"]


def seed_conversation(client, headers, project_id, first_message="Design a 3 bedroom home"):
    app = client.app
    with app.state.session_factory() as db:
        owner = db.scalar(select(User).where(User.email == "conversation@example.com"))
        project = db.get(Project, project_id)
        conversation = create_conversation(db, project, owner, 0, first_message)
        append_message(db, conversation, "user", first_message, "local_rules")
        append_message(db, conversation, "assistant", "How many bathrooms?", "local_llm", "qwen2.5:7b", "clarification")
        db.commit()
        return conversation.id


def test_conversation_messages_persist_in_chronological_order_and_title_is_derived():
    client = TestClient(create_app(database_url="sqlite://", create_tables=True))
    headers, project_id = make_user_and_project(client, "conversation@example.com")
    conversation_id = seed_conversation(client, headers, project_id, "Design a 3 bedroom home with a courtyard")
    with client.app.state.session_factory() as db:
        conversation = get_owned_conversation(db, project_id, db.scalar(select(User).where(User.email == "conversation@example.com")).id, conversation_id)
        transcript = load_transcript(db, conversation)
        assert conversation.title == "Design a 3 bedroom home with a courtyard"
        assert [item.content for item in transcript] == ["Design a 3 bedroom home with a courtyard", "How many bathrooms?"]
        assert transcript[1].engine == "local_llm"
        assert transcript[1].model_name == "qwen2.5:7b"


def test_conversation_title_is_truncated_to_80_characters():
    client = TestClient(create_app(database_url="sqlite://", create_tables=True))
    headers, project_id = make_user_and_project(client, "conversation@example.com")
    long_message = "A" * 120
    conversation_id = seed_conversation(client, headers, project_id, long_message)
    with client.app.state.session_factory() as db:
        conversation = db.get(__import__("app.models.assistant", fromlist=["AssistantConversation"]).AssistantConversation, conversation_id)
        assert len(conversation.title) == 80


def test_conversation_list_and_transcript_routes_are_owner_scoped():
    owner = TestClient(create_app(database_url="sqlite://", create_tables=True))
    headers, project_id = make_user_and_project(owner, "conversation@example.com")
    conversation_id = seed_conversation(owner, headers, project_id)

    listed = owner.get(f"/api/v1/projects/{project_id}/assistant/conversations")
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    transcript = owner.get(f"/api/v1/projects/{project_id}/assistant/conversations/{conversation_id}")
    assert transcript.status_code == 200
    assert [item["role"] for item in transcript.json()["messages"]] == ["user", "assistant"]
    assert transcript.json()["messages"][1]["model_name"] == "qwen2.5:7b"

    other = TestClient(create_app(database_url="sqlite://", create_tables=True))
    other_headers, other_project_id = make_user_and_project(other, "other-conversation@example.com")
    assert other.get(f"/api/v1/projects/{project_id}/assistant/conversations/{conversation_id}").status_code == 404
    assert other.get(f"/api/v1/projects/{other_project_id}/assistant/conversations/{conversation_id}").status_code == 404


def test_conversation_list_limit_is_bounded():
    client = TestClient(create_app(database_url="sqlite://", create_tables=True))
    headers, project_id = make_user_and_project(client, "conversation@example.com")
    response = client.get(f"/api/v1/projects/{project_id}/assistant/conversations?limit=1000")
    assert response.status_code == 422
