import test from 'node:test';
import assert from 'node:assert/strict';
import { furnitureToSvgRect, rotateFurniture, pointInRoom, moveFurniture, resizeFurniture, duplicateFurniture, serializeFurniture } from '../app/lib/furniture-geometry.mjs';

const bed = { item_id: 'bed', catalog_type: 'bed_double', name: 'Bed', x_mm: 1500, y_mm: 1200, width_mm: 1400, depth_mm: 2000, rotation_deg: 0 };

test('furniture footprint is centered in millimetres and swaps axes on quarter turns', () => {
  assert.deepEqual(furnitureToSvgRect(bed), { x: 800, y: 200, width: 1400, height: 2000 });
  assert.deepEqual(furnitureToSvgRect({ ...bed, rotation_deg: 90 }), { x: 500, y: 500, width: 2000, height: 1400 });
});

test('furniture rotation wraps and supports reverse rotation', () => {
  assert.equal(rotateFurniture(bed).rotation_deg, 90);
  assert.equal(rotateFurniture({ ...bed, rotation_deg: 270 }).rotation_deg, 0);
  assert.equal(rotateFurniture(bed, -1).rotation_deg, 270);
});

test('drop target must be inside the selected room polygon', () => {
  const polygon = [{x:0,y:0},{x:4000,y:0},{x:4000,y:3000},{x:0,y:3000}];
  assert.equal(pointInRoom({x:1000,y:1000}, polygon), true);
  assert.equal(pointInRoom({x:5000,y:1000}, polygon), false);
});

test('furniture inspector transforms preserve identity and enforce positive resized dimensions', () => {
  assert.deepEqual(moveFurniture(bed, 2200, 1800), { ...bed, x_mm: 2200, y_mm: 1800 });
  assert.deepEqual(resizeFurniture(bed, 0, 2300), { ...bed, width_mm: 100, depth_mm: 2300 });
  assert.equal(duplicateFurniture(bed, 'bed-copy').item_id, 'bed-copy');
  assert.deepEqual(serializeFurniture([bed]), [bed]);
});
