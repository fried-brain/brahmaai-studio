"""Persist furniture placements on rooms.

Revision ID: 0008_room_furniture
Revises: 0007_assistant_proposals
"""
from alembic import op
import sqlalchemy as sa

revision = "0008_room_furniture"
down_revision = "0007_assistant_proposals"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column("rooms", sa.Column("furniture_json", sa.Text(), nullable=False, server_default="[]"))

def downgrade() -> None:
    op.drop_column("rooms", "furniture_json")
