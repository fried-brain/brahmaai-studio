import test from "node:test";
import assert from "node:assert/strict";
import { snapToGrid, rectangleVertices, translateRoom, resizeRoomFromCorner, deriveWalls } from "../app/components/geometry.mjs";

test("snaps a coordinate to the nearest 100 mm grid", () => {
  assert.equal(snapToGrid(149), 100);
  assert.equal(snapToGrid(151), 200);
});

test("creates a normalized rectangle polygon from drag endpoints", () => {
  assert.deepEqual(rectangleVertices({ x: 900, y: 700 }, { x: 100, y: 200 }), [
    { x: 100, y: 200 }, { x: 900, y: 200 }, { x: 900, y: 700 }, { x: 100, y: 700 },
  ]);
});

test("translates every room vertex without mutating the original", () => {
  const room = { vertices_mm: [{ x: 100, y: 100 }, { x: 500, y: 100 }, { x: 500, y: 400 }, { x: 100, y: 400 }] };
  const moved = translateRoom(room, 200, -100);
  assert.deepEqual(moved.vertices_mm[0], { x: 300, y: 0 });
  assert.deepEqual(room.vertices_mm[0], { x: 100, y: 100 });
});

test("resizes a rectangular room by moving its bottom-right corner", () => {
  const room = { vertices_mm: [{ x: 0, y: 0 }, { x: 500, y: 0 }, { x: 500, y: 400 }, { x: 0, y: 400 }] };
  const resized = resizeRoomFromCorner(room, 800, 600);
  assert.deepEqual(resized.vertices_mm, [
    { x: 0, y: 0 }, { x: 800, y: 0 }, { x: 800, y: 600 }, { x: 0, y: 600 },
  ]);
});

test("deduplicates shared wall segments and preserves both room ids", () => {
  const rooms = [
    { id: "a", vertices_mm: [{x:0,y:0},{x:500,y:0},{x:500,y:400},{x:0,y:400}] },
    { id: "b", vertices_mm: [{x:500,y:0},{x:900,y:0},{x:900,y:400},{x:500,y:400}] },
  ];
  const walls = deriveWalls(rooms);
  assert.equal(walls.length, 7);
  assert.deepEqual(walls.find(w => w.room_ids.length === 2).room_ids.sort(), ["a", "b"]);
});

test("moves one polygon vertex to reshape a non-rectangular room", async () => {
  const { moveRoomVertex } = await import("../app/components/geometry.mjs");
  const room = { vertices_mm: [{x:0,y:0},{x:500,y:0},{x:500,y:300},{x:250,y:300},{x:0,y:300}] };
  const reshaped = moveRoomVertex(room, 2, 650, 350);
  assert.deepEqual(reshaped.vertices_mm[2], { x: 650, y: 350 });
  assert.deepEqual(room.vertices_mm[2], { x: 500, y: 300 });
});

test("calculates live room area and perimeter from millimetre vertices", async () => {
  const { polygonAreaSqFt, polygonPerimeterMm } = await import("../app/components/geometry.mjs");
  const rectangle = [{x:0,y:0},{x:3000,y:0},{x:3000,y:4000},{x:0,y:4000}];
  assert.equal(Number(polygonAreaSqFt(rectangle).toFixed(3)), 129.167);
  assert.equal(polygonPerimeterMm(rectangle), 14000);
});
