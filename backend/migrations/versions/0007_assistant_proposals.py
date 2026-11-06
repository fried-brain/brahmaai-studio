"""Persist validated, approval-gated assistant layout proposals.

Revision ID: 0007_assistant_proposals
Revises: 0006_assistant_conversations
"""
from alembic import op
import sqlalchemy as sa

revision = "0007_assistant_proposals"
down_revision = "0006_assistant_conversations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "assistant_proposals",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("conversation_id", sa.String(length=36), sa.ForeignKey("assistant_conversations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", sa.String(length=36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("owner_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("floor_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="draft"),
        sa.Column("proposal_json", sa.Text(), nullable=False),
        sa.Column("validation_issues_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("base_layout_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_assistant_proposals_owner_project", "assistant_proposals", ["owner_id", "project_id"])
    op.create_index("ix_assistant_proposals_conversation", "assistant_proposals", ["conversation_id"])
    with op.batch_alter_table("assistant_messages") as batch_op:
        batch_op.add_column(sa.Column("proposal_id", sa.String(length=36), nullable=True))
        batch_op.create_foreign_key("fk_assistant_messages_proposal_id", "assistant_proposals", ["proposal_id"], ["id"], ondelete="SET NULL")


def downgrade() -> None:
    with op.batch_alter_table("assistant_messages") as batch_op:
        batch_op.drop_constraint("fk_assistant_messages_proposal_id", type_="foreignkey")
        batch_op.drop_column("proposal_id")
    op.drop_index("ix_assistant_proposals_conversation", table_name="assistant_proposals")
    op.drop_index("ix_assistant_proposals_owner_project", table_name="assistant_proposals")
    op.drop_table("assistant_proposals")
