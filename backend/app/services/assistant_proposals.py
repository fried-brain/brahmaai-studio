import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.models.assistant import AssistantConversation, AssistantProposalRecord
from app.models.project import Project
from app.models.user import User
from app.schemas.assistant_ai import LayoutProposalDraft
from app.schemas.layouts import LayoutUpdate
from app.services.layouts import validate_layout_update


@dataclass(frozen=True)
class ProposalValidationResult:
    valid: bool
    issues: list[dict[str, str]]


def fingerprint_floor_state(project: Project, floor_number: int, saved_rooms: list) -> str:
    plot = project.plot
    canonical = {
        "plot": None if plot is None else {
            "shape": plot.shape, "width_mm": plot.width_mm, "length_mm": plot.length_mm,
            "geometry_json": json.loads(plot.geometry_json) if plot.geometry_json else None,
            "orientation": plot.orientation, "road_facing_side": plot.road_facing_side,
        },
        "floor_number": floor_number,
        "rooms": sorted([
            {
                "name": room.name,
                "room_type": room.room_type,
                "geometry": json.loads(room.geometry_json),
                "wall_thickness_mm": room.wall_thickness_mm,
                "openings": json.loads(room.openings_json or "[]"),
                "furniture": json.loads(getattr(room, "furniture_json", "[]") or "[]"),
            }
            for room in saved_rooms if room.floor_number == floor_number
        ], key=lambda item: (item["name"].casefold(), item["name"])),
    }
    encoded = json.dumps(canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def validate_layout_proposal(project: Project, floor_number: int, rooms: list[dict]) -> ProposalValidationResult:
    issues: list[dict[str, str]] = []
    try:
        payload_rooms = [{key: value for key, value in room.items() if key != "proposal_id"} for room in rooms]
        layout = LayoutUpdate.model_validate({"floor_number": floor_number, "rooms": payload_rooms})
    except ValidationError as exc:
        for error in exc.errors():
            path = ".".join(str(part) for part in error.get("loc", ())) or "rooms"
            issues.append({"path": path, "message": error.get("msg", "Invalid room data")})
        return ProposalValidationResult(False, issues)
    try:
        validate_layout_update(project.plot, layout)
    except ValueError as exc:
        issues.append({"path": "rooms", "message": str(exc)})
    return ProposalValidationResult(not issues, issues)


def create_pending_proposal(
    db: Session,
    conversation: AssistantConversation,
    project: Project,
    owner: User,
    proposal: dict,
    saved_rooms: list,
) -> tuple[AssistantProposalRecord, ProposalValidationResult]:
    raw = json.loads(json.dumps(proposal))
    issues: list[dict[str, str]] = []
    try:
        parsed = LayoutProposalDraft.model_validate(raw)
        floor_number = parsed.floor_number
        normalized = parsed.model_dump(mode="json")
        result = validate_layout_proposal(project, floor_number, normalized["rooms"])
        issues.extend(result.issues)
        stored_json = json.dumps(normalized, sort_keys=True, separators=(",", ":"))
    except ValidationError as exc:
        floor_number = raw.get("floor_number", conversation.floor_number)
        for error in exc.errors():
            path = ".".join(str(part) for part in error.get("loc", ())) or "proposal"
            issues.append({"path": path, "message": error.get("msg", "Invalid proposal data")})
        result = ProposalValidationResult(False, issues)
        stored_json = json.dumps(raw, sort_keys=True, separators=(",", ":"))
    if floor_number != conversation.floor_number:
        issues.append({"path": "floor_number", "message": "Proposal floor does not match its conversation floor"})
        result = ProposalValidationResult(False, issues)
    record = AssistantProposalRecord(
        conversation_id=conversation.id,
        project_id=project.id,
        owner_id=owner.id,
        floor_number=floor_number,
        status="draft" if result.valid else "needs_revision",
        proposal_json=stored_json,
        validation_issues_json=json.dumps(issues, separators=(",", ":")),
        base_layout_hash=fingerprint_floor_state(project, conversation.floor_number, saved_rooms),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(record)
    db.flush()
    return record, result


class ProposalActionError(RuntimeError):
    def __init__(self, code: str, message: str, issues: list[dict[str, str]] | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.issues = issues or []


@dataclass(frozen=True)
class AppliedProposalResult:
    proposal: AssistantProposalRecord
    rooms: list


def get_owned_proposal(db: Session, project_id: str, owner_id: str, proposal_id: str) -> AssistantProposalRecord:
    from sqlalchemy import select

    record = db.scalar(select(AssistantProposalRecord).where(
        AssistantProposalRecord.id == proposal_id,
        AssistantProposalRecord.project_id == project_id,
        AssistantProposalRecord.owner_id == owner_id,
    ))
    if record is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Proposal not found")
    return record


def apply_pending_proposal(
    db: Session,
    project: Project,
    owner: User,
    proposal_id: str,
    edited_proposal: dict,
) -> AppliedProposalResult:
    from sqlalchemy import select
    from app.models.project import Room
    from app.schemas.layouts import LayoutUpdate
    from app.services.layouts import persist_floor_rooms

    record = get_owned_proposal(db, project.id, owner.id, proposal_id)
    if record.status not in {"draft", "needs_revision"}:
        raise ProposalActionError("proposal_not_pending", "This proposal is no longer pending")
    current_rooms = list(db.scalars(select(Room).where(
        Room.project_id == project.id, Room.floor_number == record.floor_number
    )).all())
    current_hash = fingerprint_floor_state(project, record.floor_number, current_rooms)
    if current_hash != record.base_layout_hash:
        record.status = "needs_revision"
        record.validation_issues_json = json.dumps([{
            "path": "floor", "message": "The saved plot or floor plan changed after this proposal was generated. Generate a fresh proposal."
        }], separators=(",", ":"))
        record.updated_at = datetime.now(timezone.utc)
        db.commit()
        raise ProposalActionError("proposal_stale", "The saved floor plan changed. Generate a fresh proposal before applying.")
    try:
        parsed = LayoutProposalDraft.model_validate(edited_proposal)
        if parsed.floor_number != record.floor_number:
            raise ProposalActionError("proposal_invalid", "Proposal floor does not match the target floor", [{"path": "floor_number", "message": "Proposal floor does not match the target floor"}])
        validation = validate_layout_proposal(project, parsed.floor_number, parsed.model_dump(mode="json")["rooms"])
        if not validation.valid:
            raise ProposalActionError("proposal_invalid", "The edited proposal has geometry issues", validation.issues)
        layout_payload = LayoutUpdate.model_validate({
            "floor_number": parsed.floor_number,
            "rooms": [{key: value for key, value in room.model_dump(mode="json").items() if key != "proposal_id"} for room in parsed.rooms],
        })
        validate_layout_update(project.plot, layout_payload)
        rooms = persist_floor_rooms(db, project.id, layout_payload)
        record.proposal_json = json.dumps(parsed.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
        record.status = "applied"
        record.applied_at = datetime.now(timezone.utc)
        record.updated_at = record.applied_at
        db.commit()
        for room in rooms:
            db.refresh(room)
        return AppliedProposalResult(record, rooms)
    except ProposalActionError:
        db.rollback()
        raise
    except ValidationError as exc:
        db.rollback()
        issues = [{"path": ".".join(str(part) for part in error.get("loc", ())) or "proposal", "message": error.get("msg", "Invalid proposal data")} for error in exc.errors()]
        raise ProposalActionError("proposal_invalid", "The edited proposal is invalid", issues) from None
    except Exception:
        db.rollback()
        raise


def reject_pending_proposal(db: Session, project: Project, owner: User, proposal_id: str) -> AssistantProposalRecord:
    record = get_owned_proposal(db, project.id, owner.id, proposal_id)
    if record.status not in {"draft", "needs_revision"}:
        raise ProposalActionError("proposal_not_pending", "This proposal is no longer pending")
    record.status = "rejected"
    record.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(record)
    return record
