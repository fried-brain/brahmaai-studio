from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models.assistant import AssistantConversation, AssistantMessage
from app.models.project import Project
from app.models.user import User


def create_conversation(db: Session, project: Project, owner: User, floor_number: int, title: str) -> AssistantConversation:
    conversation = AssistantConversation(
        project_id=project.id,
        owner_id=owner.id,
        floor_number=floor_number,
        title=title.strip()[:80] or "New design conversation",
    )
    db.add(conversation)
    db.flush()
    return conversation


def append_message(
    db: Session,
    conversation: AssistantConversation,
    role: str,
    content: str,
    engine: str,
    model_name: str | None = None,
    response_type: str | None = None,
    proposal_json: str | None = None,
    proposal_id: str | None = None,
) -> AssistantMessage:
    if role not in {"user", "assistant"}:
        raise ValueError("Message role must be user or assistant")
    if len(content) > 12000:
        raise ValueError("Assistant message exceeds 12000 characters")
    if role == "user" and len(content) > 2000:
        raise ValueError("User message exceeds 2000 characters")
    message = AssistantMessage(
        conversation_id=conversation.id,
        role=role,
        content=content,
        engine=engine,
        model_name=model_name,
        response_type=response_type,
        proposal_json=proposal_json,
        proposal_id=proposal_id,
    )
    db.add(message)
    conversation.updated_at = datetime.now(timezone.utc)
    db.flush()
    return message


def get_owned_conversation(db: Session, project_id: str, owner_id: str, conversation_id: str) -> AssistantConversation:
    conversation = db.scalar(select(AssistantConversation).where(
        AssistantConversation.id == conversation_id,
        AssistantConversation.project_id == project_id,
        AssistantConversation.owner_id == owner_id,
    ))
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


def list_conversations(db: Session, project_id: str, owner_id: str, limit: int = 20) -> list[AssistantConversation]:
    if limit < 1 or limit > 100:
        raise ValueError("Conversation list limit must be between 1 and 100")
    return list(db.scalars(
        select(AssistantConversation).where(
            AssistantConversation.project_id == project_id,
            AssistantConversation.owner_id == owner_id,
        ).order_by(AssistantConversation.updated_at.desc(), AssistantConversation.created_at.desc()).limit(limit)
    ).all())


def load_transcript(db: Session, conversation: AssistantConversation) -> list[AssistantMessage]:
    return list(db.scalars(select(AssistantMessage).where(
        AssistantMessage.conversation_id == conversation.id
    ).order_by(AssistantMessage.created_at.asc(), AssistantMessage.id.asc())).all())


def conversation_message_counts(db: Session, conversation_ids: list[str]) -> dict[str, int]:
    if not conversation_ids:
        return {}
    rows = db.execute(select(AssistantMessage.conversation_id, func.count(AssistantMessage.id)).where(
        AssistantMessage.conversation_id.in_(conversation_ids)
    ).group_by(AssistantMessage.conversation_id)).all()
    return {conversation_id: count for conversation_id, count in rows}
