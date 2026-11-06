"""Add parametric wall thickness and door/window openings to rooms.

Revision ID: 0005_architectural_openings
Revises: 0004_rooms
"""
from alembic import op
import sqlalchemy as sa

revision = "0005_architectural_openings"
down_revision = "0004_rooms"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("rooms", sa.Column("wall_thickness_mm", sa.Float(), nullable=False, server_default="150"))
    op.add_column("rooms", sa.Column("openings_json", sa.Text(), nullable=False, server_default="[]"))


def downgrade() -> None:
    op.drop_column("rooms", "openings_json")
    op.drop_column("rooms", "wall_thickness_mm")
