import test from "node:test";
import assert from "node:assert/strict";
import { appendConversationMessage, serializeProposalEdit, isProposalPreviewOnly } from "../app/components/assistant-state.mjs";

test("appends transcript messages without mutating the existing transcript", () => {
  const original = [{ role: "user", content: "Hello" }];
  const next = appendConversationMessage(original, { role: "assistant", content: "Hi" });
  assert.equal(original.length, 1);
  assert.deepEqual(next.map(item => item.role), ["user", "assistant"]);
});

test("serializes editable proposal fields while preserving local ids and openings", () => {
  const proposal = { schema_version: "1.0", title: "Draft", floor_number: 0, candidate_key: "candidate-a", planner_version: "1.0", template: "public_first", score: 91, score_breakdown: { adjacency: 25 }, unmet_preferences: [], rooms: [{
    proposal_id: "room-a", name: "Living", room_type: "living", vertices_mm: [{ x: 0, y: 0 }, { x: 1000, y: 0 }, { x: 1000, y: 1000 }],
    wall_thickness_mm: 150, openings: [{ kind: "door", edge_index: 0, offset_mm: 0, width_mm: 900, height_mm: 2100, sill_height_mm: 0, swing_direction: "left" }],
  }] };
  const serialized = JSON.parse(serializeProposalEdit(proposal));
  assert.equal(serialized.rooms[0].proposal_id, "room-a");
  assert.equal(serialized.rooms[0].openings[0].swing_direction, "left");
  assert.equal(serialized.rooms[0].name, "Living");
  assert.equal(serialized.candidate_key, "candidate-a");
  assert.equal(serialized.score, 91);
});

test("preview-only edits leave the saved-room snapshot unchanged", () => {
  const savedRooms = [{ id: "saved-1", name: "Living", vertices_mm: [{ x: 0, y: 0 }] }];
  const savedSnapshot = JSON.stringify(savedRooms);
  const preview = { rooms: [{ proposal_id: "draft-1", name: "Living enlarged" }], savedRoomsSnapshot: savedSnapshot, status: "draft" };
  assert.equal(isProposalPreviewOnly(savedRooms, preview), true);
  preview.rooms[0].name = "Edited preview";
  assert.equal(isProposalPreviewOnly(savedRooms, preview), true);
  savedRooms[0].name = "Changed saved room";
  assert.equal(isProposalPreviewOnly(savedRooms, preview), false);
});
