"""Persist floor rooms; derive wall segments from room boundaries.

Revision ID: 0004_rooms
Revises: 0003_plot_geometry
"""
from alembic import op
import sqlalchemy as sa

revision = "0004_rooms"
down_revision = "0003_plot_geometry"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "rooms",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("project_id", sa.String(length=36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("floor_number", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("room_type", sa.String(length=32), nullable=False, server_default="other"),
        sa.Column("geometry_json", sa.Text(), nullable=False),
    )
    op.create_index("ix_rooms_project_id", "rooms", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_rooms_project_id", table_name="rooms")
    op.drop_table("rooms")
