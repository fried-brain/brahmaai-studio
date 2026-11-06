"""Persist polygon plot geometry.

Revision ID: 0003_plot_geometry
Revises: 0002_projects
"""
from alembic import op
import sqlalchemy as sa

revision = "0003_plot_geometry"
down_revision = "0002_projects"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("plots", sa.Column("geometry_json", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("plots", "geometry_json")
