"""Persist owner-scoped assistant conversations and messages.

Revision ID: 0006_assistant_conversations
Revises: 0005_architectural_openings
"""
from alembic import op
import sqlalchemy as sa

revision = "0006_assistant_conversations"
down_revision = "0005_architectural_openings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "assistant_conversations",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("project_id", sa.String(length=36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("owner_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("floor_number", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("title", sa.String(length=80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_assistant_conversations_project_updated", "assistant_conversations", ["project_id", "updated_at"])
    op.create_index("ix_assistant_conversations_owner_project", "assistant_conversations", ["owner_id", "project_id"])
    op.create_table(
        "assistant_messages",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("conversation_id", sa.String(length=36), sa.ForeignKey("assistant_conversations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("content", sa.String(length=12000), nullable=False),
        sa.Column("engine", sa.String(length=24), nullable=False),
        sa.Column("model_name", sa.String(length=160), nullable=True),
        sa.Column("response_type", sa.String(length=32), nullable=True),
        sa.Column("proposal_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_assistant_messages_conversation_created", "assistant_messages", ["conversation_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_assistant_messages_conversation_created", table_name="assistant_messages")
    op.drop_table("assistant_messages")
    op.drop_index("ix_assistant_conversations_owner_project", table_name="assistant_conversations")
    op.drop_index("ix_assistant_conversations_project_updated", table_name="assistant_conversations")
    op.drop_table("assistant_conversations")
