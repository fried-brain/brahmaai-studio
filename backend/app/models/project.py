from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    category: Mapped[str] = mapped_column(String(40), nullable=False, default="residential")
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    plot: Mapped["Plot | None"] = relationship(back_populates="project", cascade="all, delete-orphan", uselist=False)


class Plot(Base):
    __tablename__ = "plots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), unique=True, index=True, nullable=False)
    shape: Mapped[str] = mapped_column(String(24), nullable=False, default="rectangle")
    width_mm: Mapped[float | None] = mapped_column(Float, nullable=True)
    length_mm: Mapped[float | None] = mapped_column(Float, nullable=True)
    geometry_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    display_unit: Mapped[str] = mapped_column(String(12), nullable=False, default="ft")
    orientation: Mapped[str | None] = mapped_column(String(16), nullable=True)
    road_facing_side: Mapped[str | None] = mapped_column(String(16), nullable=True)

    project: Mapped[Project] = relationship(back_populates="plot")


class Room(Base):
    __tablename__ = "rooms"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False)
    floor_number: Mapped[int] = mapped_column(nullable=False, default=0)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    room_type: Mapped[str] = mapped_column(String(32), nullable=False, default="other")
    geometry_json: Mapped[str] = mapped_column(Text, nullable=False)
    wall_thickness_mm: Mapped[float] = mapped_column(Float, nullable=False, default=150)
    openings_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    furniture_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
