"""Add projects and plot configuration.

Revision ID: 0002_projects
Revises: 0001_initial_auth
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_projects"
down_revision = "0001_initial_auth"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("owner_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("category", sa.String(length=40), nullable=False, server_default="residential"),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_projects_owner_id", "projects", ["owner_id"])
    op.create_table(
        "plots",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("project_id", sa.String(length=36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("shape", sa.String(length=24), nullable=False, server_default="rectangle"),
        sa.Column("width_mm", sa.Float(), nullable=True),
        sa.Column("length_mm", sa.Float(), nullable=True),
        sa.Column("display_unit", sa.String(length=12), nullable=False, server_default="ft"),
        sa.Column("orientation", sa.String(length=16), nullable=True),
        sa.Column("road_facing_side", sa.String(length=16), nullable=True),
        sa.UniqueConstraint("project_id", name="uq_plots_project_id"),
    )
    op.create_index("ix_plots_project_id", "plots", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_plots_project_id", table_name="plots")
    op.drop_table("plots")
    op.drop_index("ix_projects_owner_id", table_name="projects")
    op.drop_table("projects")
