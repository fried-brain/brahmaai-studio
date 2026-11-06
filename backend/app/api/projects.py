from typing import Annotated
import json

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.dependencies import current_user, database_session, require_csrf
from app.models import Plot, Project, Room, User
from app.models.assistant import AssistantConversation
from app.schemas.layouts import LayoutOutput, LayoutUpdate, RoomOutput, WallOutput, parse_room
from app.schemas.staircases import StaircasePreviewInput, StaircasePreviewOutput
from app.schemas.assistant import AssistantMessageInput, AssistantMessageOutput, AssistantProposal
from app.schemas.assistant_conversations import AssistantConversationDetail, AssistantConversationListItem, AssistantConversationSummary, AssistantMessageOutput as TranscriptMessageOutput
from app.schemas.assistant_proposals import ApplyAssistantProposalInput, AssistantProposalRecordOutput
from app.schemas.room_layout_generation import LayoutGenerationCandidateOutput, LayoutGenerationInput, LayoutGenerationOutput
from app.services.assistant import respond_to_design_message
from app.services.assistant_conversations import append_message, conversation_message_counts, create_conversation, get_owned_conversation, list_conversations, load_transcript
from app.services.assistant_context import build_bounded_history, build_project_context
from app.services.assistant_orchestrator import orchestrate_assistant_message
from app.services.assistant_proposals import ProposalActionError, apply_pending_proposal, create_pending_proposal, get_owned_proposal, reject_pending_proposal
from app.services.room_planning_interpreter import parse_room_planning_brief
from app.services.room_layout_planner import generate_layout_candidates, rectangular_plot_bounds, validate_layout_candidate
from app.models.assistant import AssistantProposalRecord
from app.services.staircases import preview_staircase
from app.services.design_analysis import analyze_rooms
from app.schemas.projects import (
    PolygonPlotInput, ProjectCreate, ProjectResponse, PlotUpdate, RectanglePlotInput,
    serialize_project, to_mm,
)
from app.services.geometry import polygon_area_mm2, polygon_perimeter_mm
from app.services.layouts import persist_floor_rooms, validate_layout_update
from app.schemas.design_optimization import DesignOptimizationPreviewInput, DesignOptimizationApplyInput
from app.services.design_optimization import build_optimization_preview, apply_optimization_layout

router = APIRouter(prefix="/projects", tags=["projects"])


def owned_project(db: Session, project_id: str, owner_id: str) -> Project:
    project = db.scalar(
        select(Project).options(selectinload(Project.plot)).where(
            Project.id == project_id, Project.owner_id == owner_id, Project.status != "archived"
        )
    )
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_csrf)])
def create_project(
    payload: ProjectCreate,
    db: Annotated[Session, Depends(database_session)],
    user: Annotated[User, Depends(current_user)],
):
    project = Project(owner_id=user.id, name=payload.name.strip(), category=payload.category)
    if not project.name:
        raise HTTPException(status_code=422, detail="Project name cannot be blank")
    if payload.plot is not None:
        plot = payload.plot
        project.plot = build_plot(plot)
    db.add(project)
    db.commit()
    db.refresh(project)
    return serialize_project(project)


@router.get("", response_model=list[ProjectResponse])
def list_projects(
    db: Annotated[Session, Depends(database_session)],
    user: Annotated[User, Depends(current_user)],
):
    projects = db.scalars(
        select(Project).options(selectinload(Project.plot)).where(
            Project.owner_id == user.id, Project.status != "archived"
        ).order_by(Project.updated_at.desc())
    ).all()
    return [serialize_project(project) for project in projects]


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(
    project_id: str,
    db: Annotated[Session, Depends(database_session)],
    user: Annotated[User, Depends(current_user)],
):
    return serialize_project(owned_project(db, project_id, user.id))


@router.patch("/{project_id}", response_model=ProjectResponse, dependencies=[Depends(require_csrf)])
def update_project(
    project_id: str,
    payload: ProjectCreate,
    db: Annotated[Session, Depends(database_session)],
    user: Annotated[User, Depends(current_user)],
):
    project = owned_project(db, project_id, user.id)
    project.name = payload.name.strip()
    project.category = payload.category
    db.commit()
    db.refresh(project)
    return serialize_project(project)


@router.put("/{project_id}/plot", response_model=ProjectResponse, dependencies=[Depends(require_csrf)])
def update_plot(
    project_id: str,
    payload: PlotUpdate,
    db: Annotated[Session, Depends(database_session)],
    user: Annotated[User, Depends(current_user)],
):
    project = owned_project(db, project_id, user.id)
    plot = project.plot
    if plot is None:
        plot = Plot(project_id=project.id)
        db.add(plot)
    values = build_plot(payload)
    plot.shape = values.shape
    plot.width_mm = values.width_mm
    plot.length_mm = values.length_mm
    plot.geometry_json = values.geometry_json
    plot.display_unit = values.display_unit
    plot.orientation = values.orientation
    plot.road_facing_side = values.road_facing_side
    db.commit()
    db.refresh(project)
    return serialize_project(project)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_csrf)])
def archive_project(
    project_id: str,
    db: Annotated[Session, Depends(database_session)],
    user: Annotated[User, Depends(current_user)],
):
    project = owned_project(db, project_id, user.id)
    project.status = "archived"
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def build_plot(payload: RectanglePlotInput | PolygonPlotInput) -> Plot:
    if isinstance(payload, RectanglePlotInput):
        return Plot(
            shape="rectangle",
            width_mm=to_mm(payload.width, payload.unit),
            length_mm=to_mm(payload.length, payload.unit),
            geometry_json=None,
            display_unit=payload.unit,
            orientation=payload.orientation,
            road_facing_side=payload.road_facing_side,
        )
    factor_vertices = [
        {"x": to_mm(point.x, payload.unit), "y": to_mm(point.y, payload.unit)}
        for point in payload.vertices
    ]
    return Plot(
        shape="polygon",
        width_mm=None,
        length_mm=None,
        geometry_json=json.dumps(factor_vertices, separators=(",", ":")),
        display_unit=payload.unit,
        orientation=payload.orientation,
        road_facing_side=payload.road_facing_side,
    )


@router.post("/{project_id}/assistant/message", response_model=AssistantMessageOutput, dependencies=[Depends(require_csrf)])
def assistant_message(
    project_id: str,
    payload: AssistantMessageInput,
    request: Request,
    db: Annotated[Session, Depends(database_session)],
    user: Annotated[User, Depends(current_user)],
):
    project = owned_project(db, project_id, user.id)
    request_settings = request.app.state.settings
    rooms = db.scalars(
        select(Room).where(Room.project_id == project.id, Room.floor_number == payload.floor_number).order_by(Room.name)
    ).all()
    conversation = None
    if payload.conversation_id:
        conversation = get_owned_conversation(db, project.id, user.id, payload.conversation_id)
        if conversation.floor_number != payload.floor_number:
            raise HTTPException(status_code=409, detail={"code": "conversation_floor_mismatch", "message": "Start or select a conversation for this floor."})
    else:
        conversation = create_conversation(db, project, user, payload.floor_number, payload.normalized_message())
    previous_messages = load_transcript(db, conversation)
    history = build_bounded_history(
        previous_messages,
        request_settings.local_llm_max_history_messages,
        request_settings.local_llm_max_history_characters,
    )
    append_message(db, conversation, "user", payload.normalized_message(), "user")
    project_context = build_project_context(project, payload.floor_number, rooms)
    fallback = lambda: respond_to_design_message(payload.normalized_message(), project, payload.floor_number, rooms)
    turn = orchestrate_assistant_message(
        request_settings, request.app.state.local_llm_client, project_context, history,
        payload.normalized_message(), fallback=fallback,
    )
    proposal = None
    proposal_json = None
    proposal_id = None
    proposal_metadata = None
    if turn.proposal:
        if turn.response_type == "layout_proposal":
            proposal_details = turn.proposal
            proposal_title = str(turn.proposal.get("title", "Draft layout proposal"))
            proposal_kind = "layout_proposal"
            proposal_record, validation = create_pending_proposal(
                db, conversation, project, user, turn.proposal, rooms,
            )
            proposal_json = proposal_record.proposal_json
            proposal_id = proposal_record.id
            proposal_metadata = {
                "status": proposal_record.status,
                "validation_issues": validation.issues,
                "base_layout_hash": proposal_record.base_layout_hash,
            }
        else:
            proposal_details = turn.proposal.get("details", {})
            proposal_title = turn.proposal.get("title", "Draft proposal")
            proposal_kind = turn.proposal.get("kind", "design_brief")
        proposal = AssistantProposal(
            kind=proposal_kind, title=proposal_title, details=proposal_details, requires_user_approval=True,
        )
    append_message(
        db, conversation, "assistant", turn.reply[:12000], turn.engine, turn.model,
        turn.response_type, proposal_json, proposal_id,
    )
    db.commit()
    return AssistantMessageOutput(
        reply=turn.reply, intent=turn.intent, clarifying_questions=turn.clarifying_questions,
        suggestions=turn.suggestions, proposal=proposal, changes_applied=False,
        engine=turn.engine, conversation_id=conversation.id, response_type=turn.response_type, model=turn.model,
        proposal_id=proposal_id, proposal_metadata=proposal_metadata,
    )


@router.get("/{project_id}/assistant/conversations", response_model=list[AssistantConversationListItem])
def get_assistant_conversations(
    project_id: str,
    db: Annotated[Session, Depends(database_session)],
    user: Annotated[User, Depends(current_user)],
    limit: int = Query(default=20, ge=1, le=100),
):
    owned_project(db, project_id, user.id)
    conversations = list_conversations(db, project_id, user.id, limit)
    counts = conversation_message_counts(db, [item.id for item in conversations])
    return [
        AssistantConversationListItem(
            id=item.id, project_id=item.project_id, floor_number=item.floor_number, title=item.title,
            created_at=item.created_at, updated_at=item.updated_at, message_count=counts.get(item.id, 0),
        )
        for item in conversations
    ]


@router.get("/{project_id}/assistant/conversations/{conversation_id}", response_model=AssistantConversationDetail)
def get_assistant_conversation(
    project_id: str,
    conversation_id: str,
    db: Annotated[Session, Depends(database_session)],
    user: Annotated[User, Depends(current_user)],
):
    owned_project(db, project_id, user.id)
    conversation = get_owned_conversation(db, project_id, user.id, conversation_id)
    return AssistantConversationDetail(
        **AssistantConversationSummary.model_validate(conversation).model_dump(),
        messages=[TranscriptMessageOutput.model_validate(item) for item in load_transcript(db, conversation)],
    )


@router.post("/{project_id}/assistant/layout-generation", response_model=LayoutGenerationOutput, dependencies=[Depends(require_csrf)])
def generate_assistant_layout(
    project_id: str,
    payload: LayoutGenerationInput,
    request: Request,
    db: Annotated[Session, Depends(database_session)],
    user: Annotated[User, Depends(current_user)],
):
    project = owned_project(db, project_id, user.id)
    floor_number = payload.floor_number
    message = payload.normalized_message()
    rooms = db.scalars(
        select(Room).where(Room.project_id == project.id, Room.floor_number == floor_number).order_by(Room.name)
    ).all()
    if payload.conversation_id:
        conversation = get_owned_conversation(db, project.id, user.id, payload.conversation_id)
        if conversation.floor_number != floor_number:
            raise HTTPException(status_code=409, detail={"code": "conversation_floor_mismatch", "message": "Start or select a conversation for this floor."})
    else:
        conversation = create_conversation(db, project, user, floor_number, message)

    previous_messages = load_transcript(db, conversation)
    history = build_bounded_history(
        previous_messages,
        request.app.state.settings.local_llm_max_history_messages,
        request.app.state.settings.local_llm_max_history_characters,
    )
    append_message(db, conversation, "user", message, "user")

    def finish_without_candidates(outcome: str, reply: str, questions=None, suggestions=None, reasons=None, engine="local_rules", model_name=None, planner_version="2.0", search_status="complete"):
        append_message(db, conversation, "assistant", reply[:12000], engine, model_name, "clarification")
        db.commit()
        return LayoutGenerationOutput(
            outcome=outcome, reply=reply, questions=questions or [], suggestions=suggestions or [],
            conversation_id=conversation.id, planner_version=planner_version,
            search_status=search_status, candidates=[], reasons=reasons or [],
        )

    if project.plot is None:
        return finish_without_candidates("missing_plot", "Define the plot dimensions before generating a floor plan.")
    if rectangular_plot_bounds(project.plot) is None:
        return finish_without_candidates(
            "unsupported_plot_geometry",
            "Automatic generation currently supports only an exact axis-aligned rectangular plot. Your saved plot was not approximated or changed.",
        )

    project_context = build_project_context(project, floor_number, rooms)
    interpreted = parse_room_planning_brief(
        request.app.state.local_llm_client,
        [*history, {"role": "user", "content": message}],
        project_context,
        floor_number,
    )
    if interpreted.status != "brief":
        return finish_without_candidates(
            interpreted.status, interpreted.reply, interpreted.questions, interpreted.suggestions,
            engine="local_llm", model_name=interpreted.model,
        )

    planned = generate_layout_candidates(project.plot, interpreted.brief)
    if planned.status != "layout_candidates":
        outcome = planned.status if planned.status in {"unsupported_plot_geometry", "search_exhausted"} else "infeasible"
        reply = "No candidate layout was generated. " + " ".join(planned.reasons)
        return finish_without_candidates(outcome, reply, reasons=planned.reasons, engine="local_llm",
                                         model_name=interpreted.model, planner_version=planned.planner_version,
                                         search_status=planned.search_status)

    valid_candidates = []
    for candidate in planned.candidates:
        validation = validate_layout_candidate(project, floor_number, candidate)
        if validation.valid:
            valid_candidates.append(candidate)
    if not valid_candidates:
        return finish_without_candidates(
            "infeasible", "The planner could not produce a candidate that passed the existing layout and proposal validators.",
            reasons=["Every candidate failed server-side validation."], engine="local_llm", model_name=interpreted.model,
        )

    created = []
    try:
        for candidate in valid_candidates[:3]:
            record, validation = create_pending_proposal(
                db, conversation, project, user, candidate.proposal_payload(floor_number), rooms,
            )
            if not validation.valid or record.status != "draft":
                raise ValueError("A candidate failed proposal validation during persistence")
            created.append((record, candidate))
        first_record = created[0][0]
        append_message(
            db, conversation, "assistant", interpreted.reply[:12000], "local_llm", interpreted.model,
            "layout_proposal", first_record.proposal_json, first_record.id,
        )
        db.commit()
    except Exception:
        db.rollback()
        raise

    outputs = []
    for record, candidate in created:
        proposal = json.loads(record.proposal_json)
        outputs.append(LayoutGenerationCandidateOutput(
            proposal_id=record.id, candidate_key=candidate.candidate_key, template=candidate.template,
            score=candidate.score.total, score_breakdown=candidate.score.breakdown,
            score_version=candidate.score_version, search_status=candidate.search_status,
            utilization=candidate.utilization, circulation_components=candidate.circulation_components,
            proposal=proposal, status=record.status, validation_issues=json.loads(record.validation_issues_json or "[]"),
        ))
    return LayoutGenerationOutput(
        outcome="layout_candidates", reply=interpreted.reply, conversation_id=conversation.id,
        candidates=outputs, reasons=planned.reasons, planner_version=planned.planner_version,
        search_status=planned.search_status,
    )


@router.get("/{project_id}/assistant/conversations/{conversation_id}/proposals", response_model=list[LayoutGenerationCandidateOutput])
def list_assistant_conversation_proposals(
    project_id: str,
    conversation_id: str,
    db: Annotated[Session, Depends(database_session)],
    user: Annotated[User, Depends(current_user)],
):
    owned_project(db, project_id, user.id)
    conversation = get_owned_conversation(db, project_id, user.id, conversation_id)
    records = db.scalars(select(AssistantProposalRecord).where(
        AssistantProposalRecord.conversation_id == conversation.id,
        AssistantProposalRecord.project_id == project_id,
        AssistantProposalRecord.owner_id == user.id,
    ).order_by(AssistantProposalRecord.created_at.asc(), AssistantProposalRecord.id.asc())).all()
    outputs = []
    for record in records:
        proposal = json.loads(record.proposal_json)
        if not proposal.get("candidate_key") or not proposal.get("planner_version"):
            continue
        outputs.append(LayoutGenerationCandidateOutput(
            proposal_id=record.id,
            candidate_key=proposal["candidate_key"],
            template=proposal.get("template") or "public_first",
            score=proposal.get("score") if proposal.get("score") is not None else 0,
            score_breakdown=proposal.get("score_breakdown") or {},
            score_version=proposal.get("score_version") or "1.0",
            search_status=proposal.get("search_status") or "complete",
            utilization=proposal.get("utilization"),
            circulation_components=proposal.get("circulation_components") or [],
            proposal=proposal, status=record.status,
            validation_issues=json.loads(record.validation_issues_json or "[]"),
        ))
    outputs.sort(key=lambda item: -item.score)
    return outputs


@router.get("/{project_id}/assistant/proposals/{proposal_id}", response_model=AssistantProposalRecordOutput)
def get_assistant_proposal(
    project_id: str,
    proposal_id: str,
    db: Annotated[Session, Depends(database_session)],
    user: Annotated[User, Depends(current_user)],
):
    owned_project(db, project_id, user.id)
    return get_owned_proposal(db, project_id, user.id, proposal_id)


@router.post("/{project_id}/assistant/proposals/{proposal_id}/apply", response_model=AssistantProposalRecordOutput, dependencies=[Depends(require_csrf)])
def apply_assistant_proposal(
    project_id: str,
    proposal_id: str,
    payload: ApplyAssistantProposalInput,
    db: Annotated[Session, Depends(database_session)],
    user: Annotated[User, Depends(current_user)],
):
    project = owned_project(db, project_id, user.id)
    try:
        result = apply_pending_proposal(db, project, user, proposal_id, payload.proposal)
        return result.proposal
    except ProposalActionError as exc:
        code_status = 422 if exc.code == "proposal_invalid" else 409
        raise HTTPException(status_code=code_status, detail={"code": exc.code, "message": exc.message, "issues": exc.issues}) from None


@router.post("/{project_id}/assistant/proposals/{proposal_id}/reject", response_model=AssistantProposalRecordOutput, dependencies=[Depends(require_csrf)])
def reject_assistant_proposal(
    project_id: str,
    proposal_id: str,
    db: Annotated[Session, Depends(database_session)],
    user: Annotated[User, Depends(current_user)],
):
    project = owned_project(db, project_id, user.id)
    try:
        return reject_pending_proposal(db, project, user, proposal_id)
    except ProposalActionError as exc:
        raise HTTPException(status_code=409, detail={"code": exc.code, "message": exc.message, "issues": exc.issues}) from None


@router.post("/{project_id}/staircase/preview", response_model=StaircasePreviewOutput, dependencies=[Depends(require_csrf)])
def staircase_preview(
    project_id: str,
    payload: StaircasePreviewInput,
    db: Annotated[Session, Depends(database_session)],
    user: Annotated[User, Depends(current_user)],
):
    owned_project(db, project_id, user.id)
    return preview_staircase(**payload.model_dump())


@router.get("/{project_id}/design-analysis/{floor_number}")
def design_analysis(
    project_id: str,
    floor_number: int,
    include_vastu: bool = False,
    db: Annotated[Session, Depends(database_session)] = None,
    user: Annotated[User, Depends(current_user)] = None,
):
    project = owned_project(db, project_id, user.id)
    rooms = db.scalars(
        select(Room).where(Room.project_id == project.id, Room.floor_number == floor_number).order_by(Room.name)
    ).all()
    if not rooms:
        raise HTTPException(status_code=404, detail="Floor layout not found")
    return analyze_rooms(rooms, include_vastu=include_vastu)


@router.post("/{project_id}/design-optimization/preview")
def design_optimization_preview(
    project_id: str, payload: DesignOptimizationPreviewInput,
    db: Annotated[Session, Depends(database_session)],
    user: Annotated[User, Depends(current_user)],
):
    project = owned_project(db, project_id, user.id)
    rooms = db.scalars(select(Room).where(Room.project_id == project.id, Room.floor_number == payload.floor_number).order_by(Room.name)).all()
    if not rooms:
        raise HTTPException(status_code=404, detail="Floor layout not found")
    known_ids = {room.id for room in rooms}
    if payload.room_ids and not set(payload.room_ids).issubset(known_ids):
        raise HTTPException(status_code=422, detail="One or more room IDs do not belong to this floor")
    return build_optimization_preview(project, payload.floor_number, rooms, payload)


@router.post("/{project_id}/design-optimization/apply", response_model=LayoutOutput, dependencies=[Depends(require_csrf)])
def design_optimization_apply(
    project_id: str, payload: DesignOptimizationApplyInput,
    db: Annotated[Session, Depends(database_session)],
    user: Annotated[User, Depends(current_user)],
):
    project = owned_project(db, project_id, user.id)
    try:
        layout_payload = apply_optimization_layout(db, project, payload.floor_number, payload.source_layout_fingerprint, payload.rooms)
        plot_vertices = validate_layout_update(project.plot, layout_payload)
        stored = persist_floor_rooms(db, project.id, layout_payload)
        db.commit()
        for room in stored: db.refresh(room)
        return serialize_layout(payload.floor_number, stored, plot_vertices)
    except ValueError as exc:
        db.rollback()
        if str(exc) == "optimization_preview_stale":
            raise HTTPException(status_code=409, detail={"code":"optimization_preview_stale","message":"The saved layout changed after preview. Generate a new preview."}) from None
        raise HTTPException(status_code=422, detail=str(exc)) from None
    except Exception:
        db.rollback()
        raise


@router.put("/{project_id}/layout", response_model=LayoutOutput, dependencies=[Depends(require_csrf)])
def replace_floor_layout(
    project_id: str,
    payload: LayoutUpdate,
    db: Annotated[Session, Depends(database_session)],
    user: Annotated[User, Depends(current_user)],
):
    project = owned_project(db, project_id, user.id)
    if project.plot is None:
        raise HTTPException(status_code=409, detail="Define the plot before creating a floor layout")
    try:
        plot_vertices = validate_layout_update(project.plot, payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None

    try:
        stored_rooms = persist_floor_rooms(db, project.id, payload)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from None
    db.commit()
    for room in stored_rooms:
        db.refresh(room)
    stored_rooms.sort(key=lambda item: item.name.casefold())
    return serialize_layout(payload.floor_number, stored_rooms, plot_vertices)


@router.delete("/{project_id}/layout/{floor_number}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_csrf)])
def clear_floor_layout(
    project_id: str,
    floor_number: int,
    db: Annotated[Session, Depends(database_session)],
    user: Annotated[User, Depends(current_user)],
):
    project = owned_project(db, project_id, user.id)
    db.query(Room).filter(Room.project_id == project.id, Room.floor_number == floor_number).delete()
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{project_id}/layout/{floor_number}", response_model=LayoutOutput)
def get_floor_layout(
    project_id: str,
    floor_number: int,
    db: Annotated[Session, Depends(database_session)],
    user: Annotated[User, Depends(current_user)],
):
    project = owned_project(db, project_id, user.id)
    rooms = db.scalars(
        select(Room).where(Room.project_id == project.id, Room.floor_number == floor_number).order_by(Room.name)
    ).all()
    if not rooms:
        raise HTTPException(status_code=404, detail="Floor layout not found")
    plot = project.plot
    if plot.geometry_json:
        plot_vertices_data = json.loads(plot.geometry_json)
        plot_vertices = [(point["x"], point["y"]) for point in plot_vertices_data]
    else:
        plot_vertices = [(0.0, 0.0), (plot.width_mm, 0.0), (plot.width_mm, plot.length_mm), (0.0, plot.length_mm)]
    return serialize_layout(floor_number, rooms, plot_vertices)


def _point_on_segment(point: tuple[float, float], start: tuple[float, float], end: tuple[float, float], tolerance: float = 1e-5) -> bool:
    cross = (point[0] - start[0]) * (end[1] - start[1]) - (point[1] - start[1]) * (end[0] - start[0])
    if abs(cross) > tolerance:
        return False
    dot = (point[0] - start[0]) * (end[0] - start[0]) + (point[1] - start[1]) * (end[1] - start[1])
    length_sq = (end[0] - start[0]) ** 2 + (end[1] - start[1]) ** 2
    return -tolerance <= dot <= length_sq + tolerance


def _wall_is_external(start: tuple[float, float], end: tuple[float, float], plot_vertices: list[tuple[float, float]]) -> bool:
    for index, boundary_start in enumerate(plot_vertices):
        boundary_end = plot_vertices[(index + 1) % len(plot_vertices)]
        if _point_on_segment(start, boundary_start, boundary_end) and _point_on_segment(end, boundary_start, boundary_end):
            return True
    return False


def serialize_layout(floor_number: int, rooms: list[Room], plot_vertices: list[tuple[float, float]]) -> dict:
    wall_map: dict[tuple[tuple[float, float], tuple[float, float]], dict] = {}
    room_outputs = []
    room_by_id = {room.id: room for room in rooms}
    for room in rooms:
        vertices_data = parse_room(room)
        vertices = [(point["x"], point["y"]) for point in vertices_data]
        room_outputs.append({
            "id": room.id,
            "name": room.name,
            "room_type": room.room_type,
            "vertices_mm": vertices_data,
            "area_sq_ft": round(polygon_area_mm2(vertices) / (304.8 ** 2), 3),
            "perimeter_mm": round(polygon_perimeter_mm(vertices), 3),
            "wall_thickness_mm": room.wall_thickness_mm,
            "openings": json.loads(room.openings_json or "[]"),
            "furniture": json.loads(getattr(room, "furniture_json", "[]") or "[]"),
        })
        openings = json.loads(room.openings_json or "[]")
        for index, start_point in enumerate(vertices):
            end_point = vertices[(index + 1) % len(vertices)]
            key = tuple(sorted((start_point, end_point)))
            if key not in wall_map:
                wall_map[key] = {
                    "id": f"wall-{len(wall_map) + 1}",
                    "start_mm": {"x": key[0][0], "y": key[0][1]},
                    "end_mm": {"x": key[1][0], "y": key[1][1]},
                    "length_mm": round(((end_point[0] - start_point[0]) ** 2 + (end_point[1] - start_point[1]) ** 2) ** 0.5, 3),
                    "room_ids": [room.id],
                    "classification": "external" if _wall_is_external(start_point, end_point, plot_vertices) else "internal",
                    "door_present": any(item.get("kind") == "door" and item.get("edge_index") == index for item in openings),
                }
            else:
                wall_map[key]["room_ids"].append(room.id)
                wall_map[key]["door_present"] = wall_map[key]["door_present"] or any(
                    item.get("kind") == "door" and item.get("edge_index") == index for item in openings
                )
    walls = [{key: value for key, value in wall.items() if key != "door_present"} for wall in wall_map.values()]
    adjacencies = []
    for wall in wall_map.values():
        if len(wall["room_ids"]) != 2:
            continue
        first, second = [room_by_id[room_id] for room_id in wall["room_ids"]]
        adjacencies.append({
            "room_ids": wall["room_ids"],
            "room_names": [first.name, second.name],
            "shared_wall_id": wall["id"],
            "shared_wall_length_mm": wall["length_mm"],
            "connected_by_door": wall["door_present"],
        })
    door_graph: dict[str, set[str]] = {room.id: set() for room in rooms}
    for adjacency in adjacencies:
        if adjacency["connected_by_door"]:
            first_id, second_id = adjacency["room_ids"]
            door_graph[first_id].add(second_id)
            door_graph[second_id].add(first_id)
    circulation_components = []
    visited: set[str] = set()
    for room in rooms:
        if room.id in visited:
            continue
        stack = [room.id]
        component_ids = []
        visited.add(room.id)
        while stack:
            current = stack.pop()
            component_ids.append(current)
            for neighbour in door_graph[current] - visited:
                visited.add(neighbour)
                stack.append(neighbour)
        component_names = [room_by_id[room_id].name for room_id in component_ids]
        circulation_components.append({"room_ids": component_ids, "room_names": component_names, "room_count": len(component_ids)})
    return {"floor_number": floor_number, "rooms": room_outputs, "walls": walls, "adjacencies": adjacencies, "circulation_components": circulation_components}
