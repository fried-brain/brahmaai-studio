"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { DragEvent as ReactDragEvent, PointerEvent as ReactPointerEvent } from "react";
import { deriveWalls, moveRoomVertex, polygonAreaSqFt, polygonPerimeterMm, rectangleVertices, resizeRoomFromCorner, snapToGrid, translateRoom } from "./geometry.mjs";
import type { PointMM, RoomGeometry } from "./geometry.mjs";
import StaircasePlanner from "./StaircasePlanner";
import DesignAnalysisPanel from "./DesignAnalysisPanel";
import DesignAssistant from "./DesignAssistant";
import ProposalPreview from "./ProposalPreview";
import { furnitureToSvgRect, pointInRoom, rotateFurniture, moveFurniture, resizeFurniture, duplicateFurniture } from "../lib/furniture-geometry.mjs";
import FurnitureStudio, { type FurniturePreset } from "./FurnitureStudio";
import OptimizationReviewPanel, { type ArrangementCandidate } from "./OptimizationReviewPanel";
import type { LayoutCandidateView, LayoutProposal, ProposalPreviewState } from "./ProposalPreview";
import { ROOM_TYPE_COLORS, ROOM_TYPE_OPTIONS } from "./assistant-state.mjs";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

type Plot = {
  shape: string;
  width_mm: number | null;
  length_mm: number | null;
  vertices_mm: PointMM[] | null;
  area_sq_ft: number | null;
  orientation: string | null;
};
type Project = { id: string; name: string; plot: Plot | null };
type FurnitureItem = { item_id: string; catalog_type: string; name: string; x_mm: number; y_mm: number; width_mm: number; depth_mm: number; rotation_deg: 0 | 90 | 180 | 270 };
type Opening = { kind: "door" | "window"; edge_index: number; offset_mm: number; width_mm: number; height_mm: number; sill_height_mm: number; swing_direction: "left" | "right" | "none" };
type Room = RoomGeometry & {
  name: string;
  room_type: string;
  area_sq_ft?: number;
  perimeter_mm?: number;
  wall_thickness_mm: number;
  openings: Opening[];
  furniture: FurnitureItem[];
};
type Layout = { floor_number: number; rooms: Room[]; walls: { id: string; classification: "internal" | "external" }[]; adjacencies: { room_names: string[]; shared_wall_length_mm: number; connected_by_door: boolean }[]; circulation_components: { room_names: string[]; room_count: number }[] };
type DragState = {
  mode: "draw" | "move" | "resize" | "furniture";
  start: PointMM;
  last: PointMM;
  roomId?: string;
  vertexIndex?: number;
  itemId?: string;
  originalRooms: Room[];
};


async function responseError(response: Response) {
  try {
    const body = await response.json();
    return typeof body.detail === "string" ? body.detail : "The floor plan could not be saved.";
  } catch {
    return "The server could not complete the floor-plan request.";
  }
}

function plotPoints(project: Project): PointMM[] {
  const plot = project.plot;
  if (!plot) return [];
  if (plot.vertices_mm?.length) return plot.vertices_mm;
  if (plot.width_mm && plot.length_mm) return [
    { x: 0, y: 0 }, { x: plot.width_mm, y: 0 },
    { x: plot.width_mm, y: plot.length_mm }, { x: 0, y: plot.length_mm },
  ];
  return [];
}

function cloneRooms(rooms: Room[]): Room[] {
  return rooms.map(room => ({ ...room, furniture: (room.furniture ?? []).map(item => ({ ...item })), openings: (room.openings ?? []).map(opening => ({ ...opening })), vertices_mm: room.vertices_mm.map(point => ({ ...point })) }));
}

export default function PlanEditor({ project, csrfToken, onClose }: { project: Project; csrfToken: string; onClose: () => void }) {
  const [floor, setFloor] = useState(0);
  const [rooms, setRooms] = useState<Room[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selectedFurnitureId, setSelectedFurnitureId] = useState<string | null>(null);
  const [tool, setTool] = useState<"select" | "draw">("select");
  const [roomType, setRoomType] = useState("living");
  const [roomName, setRoomName] = useState("Room 1");
  const [openingEdge, setOpeningEdge] = useState(0);
  const [openingOffset, setOpeningOffset] = useState("500");
  const [openingWidth, setOpeningWidth] = useState("900");
  const [openingHeight, setOpeningHeight] = useState("2100");
  const [openingSill, setOpeningSill] = useState("0");
  const [doorSwing, setDoorSwing] = useState<"left" | "right" | "none">("left");
  const [adjacencies, setAdjacencies] = useState<Layout["adjacencies"]>([]);
  const [circulationComponents, setCirculationComponents] = useState<Layout["circulation_components"]>([]);
  const [wallClasses, setWallClasses] = useState({ internal: 0, external: 0 });
  const [preview, setPreview] = useState<PointMM | null>(null);
  const [past, setPast] = useState<Room[][]>([]);
  const [future, setFuture] = useState<Room[][]>([]);
  const [status, setStatus] = useState("Loading floor plan…");
  const [ready, setReady] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [wallsVisible, setWallsVisible] = useState(true);
  const [proposalPreview, setProposalPreview] = useState<ProposalPreviewState | null>(null);
  const [proposalBusy, setProposalBusy] = useState(false);
  const [optimizationPreview, setOptimizationPreview] = useState<{ fingerprint: string; placements: FurnitureItem[]; status: string; candidates: ArrangementCandidate[]; selectedKey: string | null } | null>(null);
  const [optimizationBusy, setOptimizationBusy] = useState(false);
  const [designReview, setDesignReview] = useState<{ opening_suggestions: Array<{ kind: string; edge_index: number; reason: string }>; room_analyses: Array<{ area_mm2: number; furniture_area_mm2: number; unoccupied_area_mm2: number; issues: Array<{ code: string; severity: string; message: string }> }> } | null>(null);
  const svgRef = useRef<SVGSVGElement | null>(null);
  const dragRef = useRef<DragState | null>(null);
  const lastSavedRef = useRef("[]");
  const plot = useMemo(() => plotPoints(project), [project]);
  const bounds = useMemo(() => {
    const points = plot.length ? plot : [{ x: 0, y: 0 }, { x: 10000, y: 8000 }];
    const minX = Math.min(...points.map(point => point.x));
    const minY = Math.min(...points.map(point => point.y));
    const maxX = Math.max(...points.map(point => point.x));
    const maxY = Math.max(...points.map(point => point.y));
    return { minX, minY, maxX, maxY, width: Math.max(1000, maxX - minX), height: Math.max(1000, maxY - minY) };
  }, [plot]);
  const selected = rooms.find(room => room.id === selectedId) ?? null;
  const walls = useMemo(() => deriveWalls(rooms), [rooms]);
  const svgId = useMemo(() => `plan-grid-${project.id.replaceAll("-", "")}`, [project.id]);

  const loadFloor = useCallback(async (floorNumber: number) => {
    setReady(false);
    setRooms([]);
    lastSavedRef.current = "[]";
    setStatus("Loading floor plan…");
    try {
      const response = await fetch(`${API_BASE}/projects/${project.id}/layout/${floorNumber}`, { credentials: "include", cache: "no-store" });
      if (response.status === 404) {
        setRooms([]);
        lastSavedRef.current = "[]";
        setStatus("No rooms on this floor yet. Choose Draw room and drag on the plot.");
      } else if (!response.ok) {
        throw new Error(await responseError(response));
      } else {
        const layout: Layout = await response.json();
        setRooms(layout.rooms);
        setAdjacencies(layout.adjacencies ?? []);
        setCirculationComponents(layout.circulation_components ?? []);
        setWallClasses({ internal: layout.walls.filter(wall => wall.classification === "internal").length, external: layout.walls.filter(wall => wall.classification === "external").length });
        lastSavedRef.current = JSON.stringify(layout.rooms.map(room => ({ name: room.name, room_type: room.room_type, vertices_mm: room.vertices_mm, wall_thickness_mm: room.wall_thickness_mm, openings: room.openings ?? [], furniture: room.furniture ?? [] })));
        setStatus(`${layout.rooms.length} room${layout.rooms.length === 1 ? "" : "s"} loaded.`);
      }
      setSelectedId(null);
      setSelectedFurnitureId(null);
      setPast([]);
      setFuture([]);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Unable to load this floor.");
    } finally {
      setReady(true);
    }
  }, [project.id]);

  useEffect(() => { setProposalPreview(null); void loadFloor(floor); }, [floor, loadFloor]);

  useEffect(() => {
    if (!ready || dragging) return;
    const payloadRooms = rooms.map(room => ({ name: room.name, room_type: room.room_type, vertices_mm: room.vertices_mm, wall_thickness_mm: room.wall_thickness_mm ?? 150, openings: room.openings ?? [], furniture: room.furniture ?? [] }));
    const signature = JSON.stringify(payloadRooms);
    if (signature === lastSavedRef.current) return;
    setStatus("Unsaved changes · saving shortly…");
    const timer = window.setTimeout(async () => {
      setStatus("Saving floor plan…");
      try {
        if (payloadRooms.length === 0) {
          const response = await fetch(`${API_BASE}/projects/${project.id}/layout/${floor}`, {
            method: "DELETE", credentials: "include", headers: { "X-CSRF-Token": csrfToken },
          });
          if (!response.ok && response.status !== 404) throw new Error(await responseError(response));
          lastSavedRef.current = "[]";
          setStatus("Floor cleared. Changes saved.");
          return;
        }
        const response = await fetch(`${API_BASE}/projects/${project.id}/layout`, {
          method: "PUT", credentials: "include",
          headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
          body: JSON.stringify({ floor_number: floor, rooms: payloadRooms }),
        });
        if (!response.ok) throw new Error(await responseError(response));
        const saved: Layout = await response.json();
        setAdjacencies(saved.adjacencies ?? []);
        setCirculationComponents(saved.circulation_components ?? []);
        setWallClasses({ internal: saved.walls.filter(wall => wall.classification === "internal").length, external: saved.walls.filter(wall => wall.classification === "external").length });
        lastSavedRef.current = signature;
        const savedByName = new Map<string, Room>(saved.rooms.map(room => [room.name, room] as const));
        setRooms(current => current.map(room => {
          const persisted = savedByName.get(room.name);
          return persisted ? { ...room, id: persisted.id, area_sq_ft: persisted.area_sq_ft, perimeter_mm: persisted.perimeter_mm } : room;
        }));
        setStatus("All changes saved.");
      } catch (error) {
        setStatus(error instanceof Error ? error.message : "Save failed. Check the layout and try again.");
      }
    }, 650);
    return () => window.clearTimeout(timer);
  }, [rooms, floor, project.id, csrfToken, ready, dragging]);

  const furniturePresets: FurniturePreset[] = [
    { catalog_type: "bed_single", name: "Single bed", width_mm: 1000, depth_mm: 2000, types: ["bedroom"] },
    { catalog_type: "bed_double", name: "Double bed", width_mm: 1400, depth_mm: 2000, types: ["bedroom"] },
    { catalog_type: "bed_queen", name: "Queen bed", width_mm: 1525, depth_mm: 2030, types: ["bedroom"] },
    { catalog_type: "bed_king", name: "King bed", width_mm: 1830, depth_mm: 2030, types: ["bedroom"] },
    { catalog_type: "bedside_table", name: "Bedside table", width_mm: 450, depth_mm: 450, types: ["bedroom"] },
    { catalog_type: "wardrobe", name: "Wardrobe", width_mm: 1800, depth_mm: 600, types: ["bedroom"] },
    { catalog_type: "dresser", name: "Dresser", width_mm: 1000, depth_mm: 450, types: ["bedroom"] },
    { catalog_type: "sofa_2", name: "Two-seat sofa", width_mm: 1600, depth_mm: 850, types: ["living"] },
    { catalog_type: "sofa_3", name: "Three-seat sofa", width_mm: 2100, depth_mm: 900, types: ["living"] },
    { catalog_type: "armchair", name: "Armchair", width_mm: 850, depth_mm: 850, types: ["living"] },
    { catalog_type: "coffee_table", name: "Coffee table", width_mm: 1100, depth_mm: 600, types: ["living"] },
    { catalog_type: "tv_console", name: "TV console", width_mm: 1600, depth_mm: 400, types: ["living"] },
    { catalog_type: "dining_table_4", name: "Four-seat dining table", width_mm: 1200, depth_mm: 800, types: ["dining"] },
    { catalog_type: "dining_chair", name: "Dining chair", width_mm: 450, depth_mm: 500, types: ["dining"] },
    { catalog_type: "kitchen_counter", name: "Kitchen counter", width_mm: 1800, depth_mm: 600, types: ["kitchen"] },
    { catalog_type: "refrigerator", name: "Refrigerator", width_mm: 700, depth_mm: 700, types: ["kitchen"] },
    { catalog_type: "sink_unit", name: "Sink unit", width_mm: 900, depth_mm: 600, types: ["kitchen"] },
    { catalog_type: "hob", name: "Hob", width_mm: 600, depth_mm: 600, types: ["kitchen"] },
    { catalog_type: "wc", name: "WC", width_mm: 400, depth_mm: 700, types: ["bathroom"] },
    { catalog_type: "washbasin", name: "Washbasin", width_mm: 600, depth_mm: 500, types: ["bathroom"] },
    { catalog_type: "shower", name: "Shower", width_mm: 900, depth_mm: 900, types: ["bathroom"] },
    { catalog_type: "bathtub", name: "Bathtub", width_mm: 1700, depth_mm: 750, types: ["bathroom"] },
    { catalog_type: "desk", name: "Desk", width_mm: 1200, depth_mm: 600, types: ["study", "utility"] },
    { catalog_type: "office_chair", name: "Office chair", width_mm: 600, depth_mm: 600, types: ["study", "utility"] },
    { catalog_type: "bookshelf", name: "Bookshelf", width_mm: 900, depth_mm: 300, types: ["study"] },
    { catalog_type: "washer", name: "Washer", width_mm: 650, depth_mm: 650, types: ["utility"] },
    { catalog_type: "storage_cabinet", name: "Storage cabinet", width_mm: 900, depth_mm: 450, types: ["utility"] },
  ];

  function dropFurniture(event: ReactDragEvent<SVGSVGElement>) {
    event.preventDefault();
    if (!selected || !svgRef.current) return;
    const catalogType = event.dataTransfer.getData("application/brahmaai-furniture");
    const preset = furniturePresets.find(item => item.catalog_type === catalogType && item.types.includes(selected.room_type));
    if (!preset) return;
    const svg = svgRef.current;
    const matrix = svg.getScreenCTM();
    if (!matrix) return;
    const point = svg.createSVGPoint(); point.x = event.clientX; point.y = event.clientY;
    const transformed = point.matrixTransform(matrix.inverse());
    const target = { x: transformed.x, y: transformed.y };
    if (!pointInRoom(target, selected.vertices_mm)) { setStatus("Drop the furniture inside the selected room."); return; }
    const item: FurnitureItem = { item_id: crypto.randomUUID(), catalog_type: preset.catalog_type, name: preset.name, x_mm: target.x, y_mm: target.y, width_mm: preset.width_mm, depth_mm: preset.depth_mm, rotation_deg: 0 };
    setPast(current => [...current, cloneRooms(rooms)]); setFuture([]);
    setRooms(current => current.map(room => room.id === selected.id ? { ...room, furniture: [...(room.furniture ?? []), item] } : room));
    setStatus(`${preset.name} placed. Review clearances before construction.`);
  }

  async function previewFurnitureArrangement() {
    if (!selected) return;
    setOptimizationBusy(true); setOptimizationPreview(null); setStatus("Checking furniture arrangement…");
    try {
      const response = await fetch(`${API_BASE}/projects/${project.id}/design-optimization/preview`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ floor_number: floor, operation: "furniture_arrangement", room_ids: [selected.id] }) });
      if (!response.ok) throw new Error(await responseError(response));
      const result = await response.json();
      const roomResult = result.candidates?.[selected.name];
      const candidates: ArrangementCandidate[] = roomResult?.candidates ?? [];
      const candidate = candidates[0];
      setOptimizationPreview({ fingerprint: result.source_layout_fingerprint, placements: candidate?.placements ?? [], status: roomResult?.status ?? "infeasible", candidates, selectedKey: candidate?.candidate_key ?? null });
      setStatus(candidate ? "Arrangement preview ready. Review it before applying." : `No arrangement generated: ${roomResult?.status ?? "unknown"}.`);
    } catch (error) { setStatus(error instanceof Error ? error.message : "Unable to preview furniture arrangement."); }
    finally { setOptimizationBusy(false); }
  }

  async function reviewSelectedRoom() {
    if (!selected) return;
    setOptimizationBusy(true); setDesignReview(null); setStatus("Reviewing room usability and opening options…");
    try {
      const response = await fetch(`${API_BASE}/projects/${project.id}/design-optimization/preview`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ floor_number: floor, operation: "full_review", room_ids: [selected.id] }) });
      if (!response.ok) throw new Error(await responseError(response));
      const result = await response.json();
      setDesignReview({ opening_suggestions: result.opening_suggestions ?? [], room_analyses: result.room_analyses ?? [] });
      setStatus("Room review ready. All findings are advisory planning heuristics.");
    } catch (error) { setStatus(error instanceof Error ? error.message : "Unable to review this room."); }
    finally { setOptimizationBusy(false); }
  }

  async function applyFurnitureArrangement() {
    if (!selected || !optimizationPreview || optimizationPreview.status !== "complete") return;
    const chosen = optimizationPreview.candidates.find(candidate => candidate.candidate_key === optimizationPreview.selectedKey);
    if (!chosen) return;
    const editedRooms = rooms.map(room => ({ name: room.name, room_type: room.room_type, vertices_mm: room.vertices_mm, wall_thickness_mm: room.wall_thickness_mm ?? 150, openings: room.openings ?? [], furniture: room.id === selected.id ? chosen.placements : room.furniture ?? [] }));
    setOptimizationBusy(true); setStatus("Revalidating furniture arrangement…");
    try {
      const response = await fetch(`${API_BASE}/projects/${project.id}/design-optimization/apply`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken }, body: JSON.stringify({ floor_number: floor, source_layout_fingerprint: optimizationPreview.fingerprint, rooms: editedRooms }) });
      if (!response.ok) throw new Error(await responseError(response));
      const saved: Layout = await response.json();
      setPast(current => [...current, cloneRooms(rooms)]); setFuture([]); setRooms(saved.rooms); setOptimizationPreview(null);
      lastSavedRef.current = JSON.stringify(saved.rooms.map(room => ({ name: room.name, room_type: room.room_type, vertices_mm: room.vertices_mm, wall_thickness_mm: room.wall_thickness_mm ?? 150, openings: room.openings ?? [], furniture: room.furniture ?? [] })));
      setStatus("Reviewed furniture arrangement applied and saved.");
    } catch (error) { setStatus(error instanceof Error ? error.message : "Arrangement could not be applied."); }
    finally { setOptimizationBusy(false); }
  }

  const receiveProposalPreview = useCallback((value: { proposalId: string; proposal: LayoutProposal; status: "draft" | "needs_revision" | "applied" | "rejected"; validationIssues: Array<{ path: string; message: string }>; candidates?: LayoutCandidateView[]; candidateKey?: string }) => {
    setProposalPreview({ ...value, savedRoomsSnapshot: JSON.stringify(rooms) });
  }, [rooms]);

  const clearProposalPreview = useCallback(() => setProposalPreview(null), []);

  async function applyProposal(proposalId: string, proposalJson: string) {
    setProposalBusy(true);
    setStatus("Revalidating proposal before applying…");
    try {
      const response = await fetch(`${API_BASE}/projects/${project.id}/assistant/proposals/${proposalId}/apply`, {
        method: "POST", credentials: "include",
        headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
        body: JSON.stringify({ proposal: JSON.parse(proposalJson) }),
      });
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        const detail = body.detail;
        if (detail?.code === "proposal_invalid" && Array.isArray(detail.issues)) {
          setProposalPreview(current => current ? { ...current, status: "needs_revision", validationIssues: detail.issues } : current);
          setStatus("Proposal needs revision. Saved rooms were not changed.");
          return;
        }
        if (detail?.code === "proposal_stale") {
          setProposalPreview(current => current ? { ...current, status: "needs_revision", validationIssues: [{ path: "floor", message: detail.message ?? "The saved floor changed. Generate a fresh proposal." }] } : current);
          setStatus("This proposal is stale. Saved rooms were not changed.");
          return;
        }
        throw new Error(typeof detail?.message === "string" ? detail.message : typeof detail === "string" ? detail : "Proposal could not be applied.");
      }
      setProposalPreview(null);
      await loadFloor(floor);
      setStatus("Approved proposal applied and saved.");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Proposal could not be applied.");
    } finally { setProposalBusy(false); }
  }

  async function rejectProposal(proposalId: string) {
    setProposalBusy(true);
    try {
      const response = await fetch(`${API_BASE}/projects/${project.id}/assistant/proposals/${proposalId}/reject`, {
        method: "POST", credentials: "include", headers: { "X-CSRF-Token": csrfToken },
      });
      if (!response.ok) throw new Error(await responseError(response));
      setProposalPreview(current => {
        if (!current) return null;
        const candidates = current.candidates?.map(candidate => candidate.proposalId === proposalId ? { ...candidate, status: "rejected" as const } : candidate);
        const next = candidates?.find(candidate => candidate.status === "draft" || candidate.status === "needs_revision");
        if (next) return { ...current, candidates, proposalId: next.proposalId, candidateKey: next.candidateKey, proposal: next.proposal, status: next.status, validationIssues: next.validationIssues };
        return { ...current, candidates, status: "rejected" };
      });
      setStatus("Selected proposal rejected. Saved floor plan remains unchanged.");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Proposal could not be rejected.");
    } finally { setProposalBusy(false); }
  }

  function worldPoint(clientX: number, clientY: number): PointMM {
    const rect = svgRef.current?.getBoundingClientRect();
    if (!rect) return { x: bounds.minX, y: bounds.minY };
    return {
      x: snapToGrid(bounds.minX + ((clientX - rect.left) / rect.width) * bounds.width),
      y: snapToGrid(bounds.minY + ((clientY - rect.top) / rect.height) * bounds.height),
    };
  }

  function beginDraw(event: ReactPointerEvent<SVGSVGElement>) {
    if (tool !== "draw" || !ready) return;
    const point = worldPoint(event.clientX, event.clientY);
    dragRef.current = { mode: "draw", start: point, last: point, originalRooms: cloneRooms(rooms) };
    setDragging(true);
    setPreview(point);
    event.currentTarget.setPointerCapture(event.pointerId);
  }

  function beginMove(event: ReactPointerEvent<SVGPolygonElement>, room: Room) {
    event.stopPropagation();
    if (tool !== "select") return;
    const point = worldPoint(event.clientX, event.clientY);
    setSelectedId(room.id);
    dragRef.current = { mode: "move", start: point, last: point, roomId: room.id, originalRooms: cloneRooms(rooms) };
    setDragging(true);
    svgRef.current?.setPointerCapture(event.pointerId);
  }

  function beginResize(event: ReactPointerEvent<SVGCircleElement>, room: Room, vertexIndex: number) {
    event.stopPropagation();
    if (tool !== "select") return;
    const point = worldPoint(event.clientX, event.clientY);
    setSelectedId(room.id);
    dragRef.current = { mode: "resize", start: point, last: point, roomId: room.id, vertexIndex, originalRooms: cloneRooms(rooms) };
    setDragging(true);
    svgRef.current?.setPointerCapture(event.pointerId);
  }

  function beginFurnitureMove(event: ReactPointerEvent<SVGGElement>, room: Room, item: FurnitureItem) {
    event.stopPropagation();
    if (tool !== "select") return;
    const point = worldPoint(event.clientX, event.clientY);
    setSelectedId(room.id); setSelectedFurnitureId(item.item_id);
    dragRef.current = { mode: "furniture", start: point, last: point, roomId: room.id, itemId: item.item_id, originalRooms: cloneRooms(rooms) };
    setDragging(true); svgRef.current?.setPointerCapture(event.pointerId);
  }

  function movePointer(event: ReactPointerEvent<SVGSVGElement>) {
    const drag = dragRef.current;
    if (!drag) return;
    const point = worldPoint(event.clientX, event.clientY);
    drag.last = point;
    if (drag.mode === "draw") {
      setPreview(point);
      return;
    }
    const dx = point.x - drag.start.x;
    const dy = point.y - drag.start.y;
    setRooms(drag.originalRooms.map(room => {
      if (room.id !== drag.roomId) return room;
      if (drag.mode === "furniture") return { ...room, furniture: (room.furniture ?? []).map(item => item.item_id === drag.itemId ? moveFurniture(item, item.x_mm + dx, item.y_mm + dy) : item) };
      if (drag.mode === "move") {
        const minX = Math.min(...room.vertices_mm.map(p => p.x));
        const maxX = Math.max(...room.vertices_mm.map(p => p.x));
        const minY = Math.min(...room.vertices_mm.map(p => p.y));
        const maxY = Math.max(...room.vertices_mm.map(p => p.y));
        const safeDx = Math.max(bounds.minX - minX, Math.min(bounds.maxX - maxX, dx));
        const safeDy = Math.max(bounds.minY - minY, Math.min(bounds.maxY - maxY, dy));
        return translateRoom(room, safeDx, safeDy) as Room;
      }
      const vertexIndex = drag.vertexIndex ?? 2;
      const target = { x: room.vertices_mm[vertexIndex].x + dx, y: room.vertices_mm[vertexIndex].y + dy };
      if (vertexIndex === 2 && room.vertices_mm.length === 4) {
        const xs = new Set(room.vertices_mm.map(point => point.x));
        const ys = new Set(room.vertices_mm.map(point => point.y));
        if (xs.size === 2 && ys.size === 2) return resizeRoomFromCorner(room, target.x, target.y) as Room;
      }
      return moveRoomVertex(room, vertexIndex, target.x, target.y) as Room;
    }));
  }

  function endPointer() {
    const drag = dragRef.current;
    if (!drag) return;
    if (drag.mode === "draw") {
      const vertices = rectangleVertices(drag.start, drag.last);
      const width = vertices[1].x - vertices[0].x;
      const height = vertices[2].y - vertices[1].y;
      if (width >= 300 && height >= 300) {
        const nextRoom: Room = {
          id: `draft-${Date.now()}`, name: roomName.trim() || `Room ${rooms.length + 1}`,
          room_type: roomType, vertices_mm: vertices, wall_thickness_mm: 150, openings: [], furniture: [],
        };
        setPast(current => [...current, cloneRooms(rooms)]);
        setFuture([]);
        setRooms(current => [...current, nextRoom]);
        setSelectedId(nextRoom.id);
        setRoomName(`Room ${rooms.length + 2}`);
        setTool("select");
      } else {
        setStatus("Room too small. Draw at least 300 × 300 mm.");
      }
      setPreview(null);
    } else {
      setPast(current => [...current, drag.originalRooms]);
      setFuture([]);
    }
    dragRef.current = null;
    setDragging(false);
  }

  function changeRoom(patch: Partial<Room>) {
    if (!selected) return;
    setPast(current => [...current, cloneRooms(rooms)]);
    setFuture([]);
    setRooms(current => current.map(room => room.id === selected.id ? { ...room, ...patch } : room));
  }

  function addOpening(kind: "door" | "window") {
    if (!selected) return;
    const edgeCount = selected.vertices_mm.length;
    const edge = Math.min(Math.max(0, openingEdge), edgeCount - 1);
    const nextOpening: Opening = {
      kind, edge_index: edge, offset_mm: Number(openingOffset), width_mm: Number(openingWidth),
      height_mm: Number(openingHeight), sill_height_mm: kind === "door" ? 0 : Number(openingSill),
      swing_direction: kind === "door" ? doorSwing : "none",
    };
    changeRoom({ openings: [...(selected.openings ?? []), nextOpening] });
  }

  function removeOpening(index: number) {
    if (!selected) return;
    changeRoom({ openings: (selected.openings ?? []).filter((_, itemIndex) => itemIndex !== index) });
  }

  function openingSegment(room: Room, opening: Opening) {
    const start = room.vertices_mm[opening.edge_index];
    const end = room.vertices_mm[(opening.edge_index + 1) % room.vertices_mm.length];
    if (!start || !end) return null;
    const length = Math.hypot(end.x - start.x, end.y - start.y);
    if (!length) return null;
    const ux = (end.x - start.x) / length;
    const uy = (end.y - start.y) / length;
    return { x1: start.x + ux * opening.offset_mm, y1: start.y + uy * opening.offset_mm,
      x2: start.x + ux * (opening.offset_mm + opening.width_mm), y2: start.y + uy * (opening.offset_mm + opening.width_mm) };
  }

  function deleteSelected() {
    if (!selected) return;
    setPast(current => [...current, cloneRooms(rooms)]);
    setFuture([]);
    setRooms(current => current.filter(room => room.id !== selected.id));
    setSelectedId(null);
  }

  function undo() {
    if (!past.length) return;
    const previous = past[past.length - 1];
    setFuture(current => [cloneRooms(rooms), ...current]);
    setPast(current => current.slice(0, -1));
    setRooms(cloneRooms(previous));
  }

  function redo() {
    if (!future.length) return;
    const next = future[0];
    setPast(current => [...current, cloneRooms(rooms)]);
    setFuture(current => current.slice(1));
    setRooms(cloneRooms(next));
  }

  function exportSvg() {
    if (!svgRef.current) return;
    const source = new XMLSerializer().serializeToString(svgRef.current);
    const blob = new Blob([source], { type: "image/svg+xml;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${project.name.toLowerCase().replace(/[^a-z0-9]+/g, "-")}-floor-${floor}.svg`;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  const previewPolygon = preview && dragRef.current?.mode === "draw" ? rectangleVertices(dragRef.current.start, preview) : [];
  const plotArea = project.plot?.area_sq_ft;
  const hasUnsavedChanges = JSON.stringify(rooms.map(room => ({ name: room.name, room_type: room.room_type, vertices_mm: room.vertices_mm, wall_thickness_mm: room.wall_thickness_mm ?? 150, openings: room.openings ?? [], furniture: room.furniture ?? [] }))) !== lastSavedRef.current;
  const selectedIsRectangle = !!selected && selected.vertices_mm.length === 4
    && new Set(selected.vertices_mm.map(point => point.x)).size === 2
    && new Set(selected.vertices_mm.map(point => point.y)).size === 2;
  const selectedHandles = selected ? (selectedIsRectangle
    ? [selected.vertices_mm.findIndex(point => point.x === Math.max(...selected.vertices_mm.map(item => item.x)) && point.y === Math.max(...selected.vertices_mm.map(item => item.y)))]
    : selected.vertices_mm.map((_, index) => index)) : [];

  if (!project.plot || !plot.length) return <section className="plan-editor"><div className="plan-editor-heading"><div><span className="card-kicker">2D FLOOR STUDIO</span><h2>Plot required</h2><p className="muted">Add plot dimensions before drawing rooms.</p></div><button className="text-button" onClick={onClose}>Close studio</button></div></section>;

  return (
    <section className="plan-editor" aria-label="Interactive 2D floor-plan editor">
      <div className="plan-editor-heading">
        <div><span className="card-kicker">BRAHMAAI · 2D STUDIO</span><h2>{project.name}</h2><p className="muted">Draw, select, move and resize room rectangles. Dimensions are stored in millimetres. Add door and window openings to room boundary walls.</p></div>
        <button className="text-button" onClick={onClose}>Close studio ×</button>
      </div>
      <div className="plan-toolbar" role="toolbar" aria-label="Floor-plan tools">
        <div className="tool-group">
          <button className={tool === "select" ? "studio-tool active" : "studio-tool"} aria-pressed={tool === "select"} onClick={() => setTool("select")}>↖ Select</button>
          <button className={tool === "draw" ? "studio-tool active" : "studio-tool"} aria-pressed={tool === "draw"} onClick={() => setTool("draw")}>＋ Draw room</button>
        </div>
        <div className="tool-group">
          <button className="studio-tool" onClick={undo} disabled={!past.length} aria-label="Undo">↶ Undo</button>
          <button className="studio-tool" onClick={redo} disabled={!future.length} aria-label="Redo">↷ Redo</button>
          <button className="studio-tool" onClick={() => setWallsVisible(value => !value)}>{wallsVisible ? "Hide walls" : "Show walls"}</button>
          <button className="studio-tool" onClick={exportSvg}>Export SVG ↓</button>
        </div>
        <label className="floor-select">Floor <select value={floor} disabled={!ready || dragging || hasUnsavedChanges} title={hasUnsavedChanges ? "Wait for autosave before switching floors" : "Choose a floor"} onChange={event => { setProposalPreview(null); setFloor(Number(event.target.value)); }}><option value={-1}>Basement</option><option value={0}>Ground floor</option><option value={1}>First floor</option><option value={2}>Second floor</option><option value={3}>Third floor</option></select></label>
      </div>
      <div className="plan-workspace">
        <div className="plan-canvas-wrap">
          <div className="plan-canvas-top"><span>{floor === -1 ? "BASEMENT" : floor === 0 ? "GROUND FLOOR" : `FLOOR ${floor}`} · PLAN VIEW</span><span>SNAP 100 MM · GRID 1000 MM</span></div>
          <div className="plan-canvas" style={{ aspectRatio: `${bounds.width} / ${bounds.height}` }}>
            <svg ref={svgRef} viewBox={`${bounds.minX} ${bounds.minY} ${bounds.width} ${bounds.height}`} preserveAspectRatio="none" role="application" aria-label={`Floor ${floor} drawing canvas. ${rooms.length} rooms.`} onPointerDown={beginDraw} onPointerMove={movePointer} onPointerUp={endPointer} onPointerCancel={endPointer} onDragOver={event => event.preventDefault()} onDrop={dropFurniture}>
              <defs><pattern id={svgId} width="1000" height="1000" patternUnits="userSpaceOnUse"><path d={`M 1000 0 L 0 0 0 1000`} fill="none" stroke="#718073" strokeOpacity=".22" strokeWidth="12"/></pattern></defs>
              <rect x={bounds.minX} y={bounds.minY} width={bounds.width} height={bounds.height} fill={`url(#${svgId})`} />
              <polygon points={plot.map(point => `${point.x},${point.y}`).join(" ")} fill="#1c2821" stroke="#c3d3a0" strokeWidth={Math.max(24, bounds.width / 450)} />
              {rooms.map(room => <g key={room.id}>
                <polygon points={room.vertices_mm.map(point => `${point.x},${point.y}`).join(" ")} fill={ROOM_TYPE_COLORS[room.room_type] ?? ROOM_TYPE_COLORS.other} fillOpacity={selectedId === room.id ? ".42" : ".25"} stroke={selectedId === room.id ? "#f0f4e8" : "#aab9a8"} strokeWidth={selectedId === room.id ? Math.max(32, bounds.width / 300) : Math.max(20, bounds.width / 500)} tabIndex={0} role="button" aria-label={`Select ${room.name}`} onPointerDown={event => beginMove(event, room)} onKeyDown={event => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); setSelectedId(room.id); } else if (event.key === "Delete" || event.key === "Backspace") { setPast(current => [...current, cloneRooms(rooms)]); setFuture([]); setSelectedId(null); setRooms(current => current.filter(item => item.id !== room.id)); } }} />
                <text x={room.vertices_mm.reduce((sum, point) => sum + point.x, 0) / room.vertices_mm.length} y={room.vertices_mm.reduce((sum, point) => sum + point.y, 0) / room.vertices_mm.length} textAnchor="middle" dominantBaseline="middle" fill="#f2f5ed" fontSize={Math.max(230, bounds.width / 35)} pointerEvents="none">{room.name}</text>
              </g>)}
              {rooms.flatMap(room => (room.furniture ?? []).map(item => { const rect = furnitureToSvgRect(item); const active = room.id === selectedId && item.item_id === selectedFurnitureId; return <g key={`${room.id}-${item.item_id}`} role="button" tabIndex={0} aria-label={`Move ${item.name}`} onPointerDown={event => beginFurnitureMove(event, room, item)} onKeyDown={event => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); setSelectedId(room.id); setSelectedFurnitureId(item.item_id); } }} style={{ cursor: "move" }}><rect x={rect.x} y={rect.y} width={rect.width} height={rect.height} rx={45} fill="#d6b47a" fillOpacity=".78" stroke={active ? "#ffffff" : "#f8e7c6"} strokeWidth={active ? Math.max(45,bounds.width/500) : Math.max(18,bounds.width/900)}/><text x={item.x_mm} y={item.y_mm} textAnchor="middle" dominantBaseline="middle" fill="#172019" fontSize={Math.max(130,bounds.width/65)} pointerEvents="none">{item.name}</text></g>; }))}
              {proposalPreview?.proposal.floor_number === floor && proposalPreview.proposal.rooms.map(room => <g key={`proposal-${room.proposal_id}`} pointerEvents="none">
                <polygon points={room.vertices_mm.map(point => `${point.x},${point.y}`).join(" ")} fill="#e3bd7e" fillOpacity=".13" stroke="#e3bd7e" strokeWidth={Math.max(35, bounds.width / 350)} strokeDasharray={`${bounds.width / 80} ${bounds.width / 60}`} />
                <text x={room.vertices_mm.reduce((sum, point) => sum + point.x, 0) / room.vertices_mm.length} y={room.vertices_mm.reduce((sum, point) => sum + point.y, 0) / room.vertices_mm.length} textAnchor="middle" dominantBaseline="middle" fill="#f4d9a9" fontSize={Math.max(220, bounds.width / 38)}>{`DRAFT · ${room.name}`}</text>
              </g>)}
              {wallsVisible && walls.map(wall => <line key={wall.id} x1={wall.start_mm.x} y1={wall.start_mm.y} x2={wall.end_mm.x} y2={wall.end_mm.y} stroke={wall.room_ids.length > 1 ? "#f0e5c8" : "#8fa08f"} strokeWidth={Math.max(20, Math.max(...rooms.filter(room => wall.room_ids.includes(room.id)).map(room => room.wall_thickness_mm ?? 150)))} pointerEvents="none"/>)}
              {rooms.flatMap(room => (room.openings ?? []).map((opening, index) => { const segment = openingSegment(room, opening); return segment ? <g key={`${room.id}-opening-${index}`} pointerEvents="none">
                <line {...segment} stroke="#0e1410" strokeWidth={(room.wall_thickness_mm ?? 150) + 35} />
                <line {...segment} stroke={opening.kind === "door" ? "#d6b47a" : "#80c5d0"} strokeWidth={Math.max(35, bounds.width / 700)} strokeLinecap="round" />
              </g> : null; }))}
              {previewPolygon.length > 0 && <polygon points={previewPolygon.map(point => `${point.x},${point.y}`).join(" ")} fill="#c3d3a0" fillOpacity=".25" stroke="#e8f1d6" strokeWidth={Math.max(24, bounds.width / 400)} strokeDasharray={`${bounds.width / 100} ${bounds.width / 100}`} pointerEvents="none"/>}
              {selected && selectedHandles.map(vertexIndex => <circle key={`handle-${vertexIndex}`} cx={selected.vertices_mm[vertexIndex].x} cy={selected.vertices_mm[vertexIndex].y} r={Math.max(100, bounds.width / 90)} fill="#c3d3a0" stroke="#172019" strokeWidth={Math.max(30, bounds.width / 350)} style={{ cursor: "move" }} role="button" tabIndex={0} onPointerDown={event => beginResize(event, selected, vertexIndex)} onKeyDown={event => {
                const step = event.shiftKey ? 500 : 100;
                const dx = event.key === "ArrowRight" ? step : event.key === "ArrowLeft" ? -step : 0;
                const dy = event.key === "ArrowDown" ? step : event.key === "ArrowUp" ? -step : 0;
                if (!dx && !dy) return;
                event.preventDefault();
                setPast(current => [...current, cloneRooms(rooms)]);
                setFuture([]);
                setRooms(current => current.map(item => {
                  if (item.id !== selected.id) return item;
                  const point = item.vertices_mm[vertexIndex];
                  const x = point.x + dx; const y = point.y + dy;
                  const isRect = item.vertices_mm.length === 4 && new Set(item.vertices_mm.map(p => p.x)).size === 2 && new Set(item.vertices_mm.map(p => p.y)).size === 2;
                  return isRect && vertexIndex === selectedHandles[0] ? resizeRoomFromCorner(item, x, y) as Room : moveRoomVertex(item, vertexIndex, x, y) as Room;
                }));
              }} aria-label={`Move room corner ${vertexIndex + 1}. Use arrow keys to move by 100 millimetres, Shift for 500 millimetres.`}/>)}
            </svg>
          </div>
          <div className="plan-canvas-foot"><span>{(plotArea ?? 0).toLocaleString()} SQ FT PLOT</span><span>{rooms.length} ROOMS · {walls.length} WALL SEGMENTS</span></div>
        </div>
        <aside className="plan-inspector">
          <div className="card-kicker">ROOM INSPECTOR</div>
          {selected ? <>
            <label>Room name<input value={selected.name} maxLength={100} onChange={event => changeRoom({ name: event.target.value })}/></label>
            <label>Room type<select value={selected.room_type} onChange={event => changeRoom({ room_type: event.target.value })}>{ROOM_TYPE_OPTIONS.map(type => <option key={type} value={type}>{type[0].toUpperCase() + type.slice(1)}</option>)}</select></label>
            <label>Wall thickness · mm<input type="number" min="75" max="500" step="5" value={selected.wall_thickness_mm ?? 150} onChange={event => changeRoom({ wall_thickness_mm: Math.min(500, Math.max(75, Number(event.target.value) || 75)) })}/></label>
            <div className="inspector-metrics"><div><strong>{polygonAreaSqFt(selected.vertices_mm).toFixed(1)}</strong><span>AREA · SQ FT</span></div><div><strong>{polygonPerimeterMm(selected.vertices_mm).toFixed(0)}</strong><span>PERIMETER · MM</span></div></div>
            <div className="opening-editor"><div className="room-list-heading">DOORS & WINDOWS <span>{(selected.openings ?? []).length}</span></div>
              <label>Wall edge<select value={openingEdge} onChange={event => setOpeningEdge(Number(event.target.value))}>{selected.vertices_mm.map((_, index) => { const a = selected.vertices_mm[index]; const b = selected.vertices_mm[(index + 1) % selected.vertices_mm.length]; const length = Math.round(Math.hypot(b.x-a.x,b.y-a.y)); return <option key={index} value={index}>Edge {index + 1} · {length} mm</option>; })}</select></label>
              <div className="field-pair"><label>Offset · mm<input type="number" min="0" value={openingOffset} onChange={event => setOpeningOffset(event.target.value)}/></label><label>Width · mm<input type="number" min="100" value={openingWidth} onChange={event => setOpeningWidth(event.target.value)}/></label></div>
              <div className="field-pair"><label>Height · mm<input type="number" min="100" value={openingHeight} onChange={event => setOpeningHeight(event.target.value)}/></label><label>Window sill · mm<input type="number" min="0" value={openingSill} onChange={event => setOpeningSill(event.target.value)}/></label></div>
              <label>Door swing direction<select value={doorSwing} onChange={event => setDoorSwing(event.target.value as "left" | "right" | "none")}><option value="left">Left</option><option value="right">Right</option><option value="none">Unspecified</option></select></label>
              <div className="tool-group"><button className="studio-tool" onClick={() => addOpening("door")}>＋ Add door</button><button className="studio-tool" onClick={() => addOpening("window")}>＋ Add window</button></div>
              {(selected.openings ?? []).map((opening, index) => <div className="opening-row" key={`${opening.kind}-${index}`}><span>{opening.kind === "door" ? `Door · ${opening.swing_direction ?? "none"} swing` : `Window · sill ${opening.sill_height_mm} mm · head ${opening.sill_height_mm + opening.height_mm} mm`} · edge {opening.edge_index + 1} · {opening.width_mm} mm</span><button className="archive-button" onClick={() => removeOpening(index)}>Remove</button></div>)}
            </div>
            <p className="inspector-help">Drag the room to move it. Drag a corner handle to reshape its boundary. Wall thickness is shown around the boundary; room area remains measured from the polygon. The server checks plot containment, room overlap and opening fit when saving.</p>
            <button className="danger-button" onClick={deleteSelected}>Delete room</button>
          </> : <>
            <p className="muted">Select a room to edit its properties, or draw a new room on the plan.</p>
            {tool === "draw" && <><label>New room name<input value={roomName} maxLength={100} onChange={event => setRoomName(event.target.value)}/></label><label>Room type<select value={roomType} onChange={event => setRoomType(event.target.value)}>{ROOM_TYPE_OPTIONS.map(type => <option key={type} value={type}>{type[0].toUpperCase() + type.slice(1)}</option>)}</select></label><p className="inspector-help">Press and drag inside the plot to define the room rectangle. Minimum room size is 300 × 300 mm.</p></>}
          </>}
          {selected && <>
            <FurnitureStudio roomType={selected.room_type} items={selected.furniture ?? []} presets={furniturePresets} selectedId={selectedFurnitureId} busy={optimizationBusy}
              onSelect={setSelectedFurnitureId}
              onAdd={preset => { const item: FurnitureItem = { item_id: crypto.randomUUID(), catalog_type: preset.catalog_type, name: preset.name, x_mm: selected.vertices_mm.reduce((sum,p)=>sum+p.x,0)/selected.vertices_mm.length, y_mm: selected.vertices_mm.reduce((sum,p)=>sum+p.y,0)/selected.vertices_mm.length, width_mm: preset.width_mm, depth_mm: preset.depth_mm, rotation_deg: 0 }; setPast(current=>[...current,cloneRooms(rooms)]); setFuture([]); setRooms(current=>current.map(room=>room.id===selected.id?{...room,furniture:[...(room.furniture??[]),item]}:room)); setSelectedFurnitureId(item.item_id); }}
              onUpdate={(id,patch) => { setPast(current=>[...current,cloneRooms(rooms)]); setFuture([]); setRooms(current=>current.map(room=>room.id===selected.id?{...room,furniture:room.furniture.map(item=>item.item_id===id?resizeFurniture({...item,...patch},patch.width_mm ?? item.width_mm,patch.depth_mm ?? item.depth_mm):item)}:room)); }}
              onRotate={(id,direction) => { setPast(current=>[...current,cloneRooms(rooms)]); setFuture([]); setRooms(current=>current.map(room=>room.id===selected.id?{...room,furniture:room.furniture.map(item=>item.item_id===id?rotateFurniture(item,direction) as FurnitureItem:item)}:room)); }}
              onDuplicate={id => { const original=selected.furniture.find(item=>item.item_id===id); if(!original)return; const copy=duplicateFurniture(original,crypto.randomUUID()); setPast(current=>[...current,cloneRooms(rooms)]); setFuture([]); setRooms(current=>current.map(room=>room.id===selected.id?{...room,furniture:[...room.furniture,copy]}:room)); setSelectedFurnitureId(copy.item_id); }}
              onRemove={id => { setPast(current=>[...current,cloneRooms(rooms)]); setFuture([]); setRooms(current=>current.map(room=>room.id===selected.id?{...room,furniture:room.furniture.filter(item=>item.item_id!==id)}:room)); setSelectedFurnitureId(null); }}
              onReview={reviewSelectedRoom} onArrange={previewFurnitureArrangement}/>
            <OptimizationReviewPanel candidates={optimizationPreview?.candidates ?? []} selectedKey={optimizationPreview?.selectedKey ?? null} status={optimizationPreview ? optimizationPreview.status : ""} issues={designReview?.room_analyses.flatMap(analysis=>analysis.issues) ?? []} openingSuggestions={designReview?.opening_suggestions ?? []} busy={optimizationBusy}
              onSelect={key=>setOptimizationPreview(current=>current?{...current,selectedKey:key,placements:current.candidates.find(candidate=>candidate.candidate_key===key)?.placements ?? current.placements}:current)}
              onCandidateChange={(key,itemId,patch)=>setOptimizationPreview(current=>current?{...current,candidates:current.candidates.map(candidate=>candidate.candidate_key===key?{...candidate,placements:candidate.placements.map(item=>item.item_id===itemId?{...item,...patch}:item)}:candidate)}:current)} onApply={applyFurnitureArrangement} onDiscard={()=>setOptimizationPreview(null)}/>
          </>}
          <div className="room-list-heading">WALL CLASSIFICATION</div>
          <p className="inspector-help">{wallClasses.external} plot-boundary wall segments · {wallClasses.internal} internal or non-boundary segments.</p>
          <div className="room-list-heading">ROOM ADJACENCY</div>
          {adjacencies.length ? adjacencies.map((item, index) => <div className="opening-row" key={`${item.room_names.join("-")}-${index}`}><span>{item.room_names.join(" ↔ ")} · {item.shared_wall_length_mm} mm · {item.connected_by_door ? "door connection" : "no door opening"}</span></div>) : <p className="inspector-help">No rooms currently share a complete wall segment.</p>}
          <div className="room-list-heading">DOOR-CONNECTED CIRCULATION</div>
          {circulationComponents.length ? circulationComponents.map((component, index) => <div className="opening-row" key={`circulation-${index}`}><span>{component.room_count > 1 ? `Connected: ${component.room_names.join(", ")}` : `Isolated: ${component.room_names[0]}`}</span></div>) : <p className="inspector-help">Add rooms to analyse circulation.</p>}
          <div className="room-list-heading">ROOMS ON THIS FLOOR <span>{rooms.length}</span></div>
          <div className="room-list">{rooms.map(room => <button key={room.id} className={selectedId === room.id ? "room-list-item selected" : "room-list-item"} onClick={() => { setTool("select"); setSelectedId(room.id); setSelectedFurnitureId(null); setOptimizationPreview(null); }}><i style={{ background: ROOM_TYPE_COLORS[room.room_type] ?? ROOM_TYPE_COLORS.other }}/><span>{room.name}</span><small>{polygonAreaSqFt(room.vertices_mm).toFixed(1)} sq ft</small></button>)}</div>
        </aside>
      </div>
      {proposalPreview && <ProposalPreview value={proposalPreview} onChange={(proposal, candidate) => setProposalPreview(current => {
        if (!current) return current;
        const candidateKey = candidate?.candidateKey ?? current.candidateKey;
        const candidates = current.candidates?.map(item => item.candidateKey === candidateKey
          ? { ...item, proposal, proposalId: candidate?.proposalId ?? item.proposalId, status: candidate?.status ?? item.status, validationIssues: candidate?.validationIssues ?? item.validationIssues }
          : item);
        return { ...current, proposal, proposalId: candidate?.proposalId ?? current.proposalId, status: candidate?.status ?? current.status, validationIssues: candidate?.validationIssues ?? current.validationIssues, candidateKey, candidates };
      })} onApply={applyProposal} onReject={rejectProposal} busy={proposalBusy} />}
      <DesignAssistant projectId={project.id} floorNumber={floor} csrfToken={csrfToken} onProposalPreview={receiveProposalPreview} onProposalClear={clearProposalPreview} />
      <StaircasePlanner projectId={project.id} csrfToken={csrfToken} />
      <DesignAnalysisPanel projectId={project.id} floorNumber={floor} refreshKey={JSON.stringify(rooms.map(room => ({ vertices_mm: room.vertices_mm, openings: room.openings })))} />
      <div className="plan-status" role="status"><span className="status-dot"/>{status}<span className="plan-status-right">AUTOSAVE · 100 MM GRID</span></div>
      <p className="plan-disclaimer">Conceptual layout tool. Room geometry and dimensions are saved, but this editor does not verify structural adequacy, building-code compliance, fire safety, or construction readiness.</p>
    </section>
  );
}
