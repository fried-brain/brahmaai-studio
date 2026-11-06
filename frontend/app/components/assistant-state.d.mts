export function appendConversationMessage<T>(items: T[], message: T): T[];
export function serializeProposalEdit(proposal: unknown): string;
export function isProposalPreviewOnly(savedRooms: unknown[], proposalPreview: { savedRoomsSnapshot?: string; status?: string } | null): boolean;
export type LayoutCandidateState = { proposalId: string; candidateKey: string; score: number; proposal: unknown; scoreVersion?: string; searchStatus?: "complete" | "budget_exhausted"; utilization?: unknown; circulationComponents?: string[][] };
export function sortLayoutCandidates<T extends LayoutCandidateState>(candidates: T[]): T[];
export function selectLayoutCandidate<T extends LayoutCandidateState>(candidates: T[], candidateKey: string): T | null;
export function candidateActionTarget(candidates: LayoutCandidateState[], candidateKey: string): string | null;
export const ROOM_TYPE_OPTIONS: string[];
export const ROOM_TYPE_COLORS: Record<string, string>;
export function canPreviewLayoutCandidates(outcome: string, candidates: unknown[]): boolean;

export function getProposalPlanningSummary(proposal: unknown): { scoreVersion: string; searchStatus: string; utilization: { plot_area_mm2: number; assigned_area_mm2: number; unallocated_area_mm2: number; utilization_percent: number } | null; circulationComponents: string[][] };
