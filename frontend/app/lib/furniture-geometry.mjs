export function furnitureToSvgRect(item) {
  const quarterTurn = item.rotation_deg === 90 || item.rotation_deg === 270;
  const width = quarterTurn ? item.depth_mm : item.width_mm;
  const height = quarterTurn ? item.width_mm : item.depth_mm;
  return { x: item.x_mm - width / 2, y: item.y_mm - height / 2, width, height };
}

export function rotateFurniture(item, direction = 1) {
  const rotation = (item.rotation_deg + (direction >= 0 ? 90 : 270)) % 360;
  return { ...item, rotation_deg: rotation };
}

export function pointInRoom(point, vertices) {
  let inside = false;
  for (let i = 0, j = vertices.length - 1; i < vertices.length; j = i++) {
    const a = vertices[i]; const b = vertices[j];
    const crosses = (a.y > point.y) !== (b.y > point.y)
      && point.x < ((b.x - a.x) * (point.y - a.y)) / (b.y - a.y) + a.x;
    if (crosses) inside = !inside;
  }
  return inside;
}

export function moveFurniture(item, x_mm, y_mm) {
  return { ...item, x_mm: Number(x_mm), y_mm: Number(y_mm) };
}

export function resizeFurniture(item, width_mm, depth_mm) {
  return { ...item, width_mm: Math.max(100, Number(width_mm) || 100), depth_mm: Math.max(100, Number(depth_mm) || 100) };
}

export function duplicateFurniture(item, item_id) {
  return { ...item, item_id, x_mm: item.x_mm + 200, y_mm: item.y_mm + 200 };
}

export function serializeFurniture(items) {
  return items.map(item => ({ ...item }));
}
