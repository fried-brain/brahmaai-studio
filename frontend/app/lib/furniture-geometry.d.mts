export type FurnitureGeometryItem = {
  x_mm: number;
  y_mm: number;
  width_mm: number;
  depth_mm: number;
  rotation_deg: 0 | 90 | 180 | 270;
};
export function furnitureToSvgRect(item: FurnitureGeometryItem): { x: number; y: number; width: number; height: number };
export function rotateFurniture<T extends FurnitureGeometryItem>(item: T, direction?: number): T;
export type FurnitureItem = FurnitureGeometryItem & { item_id: string; catalog_type: string; name: string };
export function moveFurniture<T extends FurnitureItem>(item: T, x_mm: number, y_mm: number): T;
export function resizeFurniture<T extends FurnitureItem>(item: T, width_mm: number, depth_mm: number): T;
export function duplicateFurniture<T extends FurnitureItem>(item: T, item_id: string): T;
export function serializeFurniture<T extends FurnitureItem>(items: T[]): T[];
export function pointInRoom(point: { x: number; y: number }, vertices: { x: number; y: number }[]): boolean;
