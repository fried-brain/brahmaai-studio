export function snapToGrid(value, grid = 100) {
  return Math.round(value / grid) * grid;
}

export function rectangleVertices(start, end) {
  const left = Math.min(start.x, end.x);
  const right = Math.max(start.x, end.x);
  const top = Math.min(start.y, end.y);
  const bottom = Math.max(start.y, end.y);
  return [
    { x: left, y: top },
    { x: right, y: top },
    { x: right, y: bottom },
    { x: left, y: bottom },
  ];
}

export function translateRoom(room, dx, dy) {
  return {
    ...room,
    vertices_mm: room.vertices_mm.map(point => ({ x: point.x + dx, y: point.y + dy })),
  };
}

export function resizeRoomFromCorner(room, x, y) {
  const vertices = room.vertices_mm;
  const left = Math.min(...vertices.map(point => point.x));
  const top = Math.min(...vertices.map(point => point.y));
  const right = Math.max(...vertices.map(point => point.x));
  const bottom = Math.max(...vertices.map(point => point.y));
  const nextRight = Math.max(left + 100, x);
  const nextBottom = Math.max(top + 100, y);
  if (vertices.length !== 4 || new Set(vertices.map(point => `${point.x}:${point.y}`)).size !== 4) {
    return room;
  }
  return {
    ...room,
    vertices_mm: [
      { x: left, y: top },
      { x: nextRight, y: top },
      { x: nextRight, y: nextBottom },
      { x: left, y: nextBottom },
    ],
  };
}

export function deriveWalls(rooms) {
  const walls = new Map();
  for (const room of rooms) {
    const points = room.vertices_mm;
    points.forEach((start, index) => {
      const end = points[(index + 1) % points.length];
      const a = `${start.x},${start.y}`;
      const b = `${end.x},${end.y}`;
      const key = [a, b].sort().join("|");
      const existing = walls.get(key);
      if (existing) {
        if (!existing.room_ids.includes(room.id)) existing.room_ids.push(room.id);
      } else {
        walls.set(key, {
          id: `wall-${walls.size + 1}`,
          start_mm: start.x < end.x || (start.x === end.x && start.y <= end.y) ? start : end,
          end_mm: start.x < end.x || (start.x === end.x && start.y <= end.y) ? end : start,
          length_mm: Math.hypot(end.x - start.x, end.y - start.y),
          room_ids: [room.id],
        });
      }
    });
  }
  return [...walls.values()];
}

export function moveRoomVertex(room, vertexIndex, x, y) {
  if (vertexIndex < 0 || vertexIndex >= room.vertices_mm.length) return room;
  return {
    ...room,
    vertices_mm: room.vertices_mm.map((point, index) => index === vertexIndex ? { x, y } : point),
  };
}

export function polygonAreaSqFt(vertices) {
  if (vertices.length < 3) return 0;
  let twiceArea = 0;
  vertices.forEach((point, index) => {
    const next = vertices[(index + 1) % vertices.length];
    twiceArea += point.x * next.y - next.x * point.y;
  });
  return Math.abs(twiceArea / 2) / (304.8 ** 2);
}

export function polygonPerimeterMm(vertices) {
  if (vertices.length < 2) return 0;
  return vertices.reduce((total, point, index) => {
    const next = vertices[(index + 1) % vertices.length];
    return total + Math.hypot(next.x - point.x, next.y - point.y);
  }, 0);
}
