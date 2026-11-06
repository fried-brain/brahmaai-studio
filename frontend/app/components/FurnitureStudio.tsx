"use client";

export type FurnitureItem = { item_id: string; catalog_type: string; name: string; x_mm: number; y_mm: number; width_mm: number; depth_mm: number; rotation_deg: 0 | 90 | 180 | 270 };
export type FurniturePreset = { catalog_type: string; name: string; width_mm: number; depth_mm: number; types: string[] };

export default function FurnitureStudio({ roomType, items, presets, selectedId, busy, onSelect, onAdd, onUpdate, onRotate, onDuplicate, onRemove, onReview, onArrange }: {
  roomType: string; items: FurnitureItem[]; presets: FurniturePreset[]; selectedId: string | null; busy: boolean;
  onSelect: (id: string) => void; onAdd: (preset: FurniturePreset) => void;
  onUpdate: (id: string, patch: Partial<FurnitureItem>) => void; onRotate: (id: string, direction: number) => void;
  onDuplicate: (id: string) => void; onRemove: (id: string) => void; onReview: () => void; onArrange: () => void;
}) {
  const selected = items.find(item => item.item_id === selectedId) ?? null;
  return <section className="furniture-studio" aria-label="Furniture studio">
    <div className="room-list-heading">FURNITURE STUDIO <span>{items.length}</span></div>
    <p className="inspector-help">Dimensions and positions are millimetres. Presets are planning references, not manufacturer specifications.</p>
    <div className="furniture-catalog" aria-label="Furniture catalog">{presets.filter(item => item.types.includes(roomType)).map(item => <button key={item.catalog_type} className="studio-tool" draggable onDragStart={event => event.dataTransfer.setData("application/brahmaai-furniture", item.catalog_type)} onClick={() => onAdd(item)}>＋ {item.name}</button>)}</div>
    {items.length > 0 && <div className="furniture-item-list" aria-label="Placed furniture">{items.map(item => <button key={item.item_id} className={selectedId === item.item_id ? "room-list-item selected" : "room-list-item"} onClick={() => onSelect(item.item_id)}><span>{item.name}</span><small>{item.width_mm} × {item.depth_mm}</small></button>)}</div>}
    {selected && <div className="furniture-inspector" aria-label={`Edit ${selected.name}`}>
      <strong>{selected.name}</strong>
      <div className="furniture-fields">
        <label>X (mm)<input type="number" value={selected.x_mm} onChange={event => onUpdate(selected.item_id, { x_mm: Number(event.target.value) })}/></label>
        <label>Y (mm)<input type="number" value={selected.y_mm} onChange={event => onUpdate(selected.item_id, { y_mm: Number(event.target.value) })}/></label>
        <label>Width (mm)<input type="number" min="100" max="20000" value={selected.width_mm} onChange={event => onUpdate(selected.item_id, { width_mm: Math.max(100, Number(event.target.value) || 100) })}/></label>
        <label>Depth (mm)<input type="number" min="100" max="20000" value={selected.depth_mm} onChange={event => onUpdate(selected.item_id, { depth_mm: Math.max(100, Number(event.target.value) || 100) })}/></label>
      </div>
      <div className="tool-group"><button className="archive-button" onClick={() => onRotate(selected.item_id, -1)}>↶ Rotate</button><button className="archive-button" onClick={() => onRotate(selected.item_id, 1)}>Rotate ↷</button><button className="archive-button" onClick={() => onDuplicate(selected.item_id)}>Duplicate</button><button className="danger-button" onClick={() => onRemove(selected.item_id)}>Remove</button></div>
    </div>}
    <div className="tool-group"><button className="studio-tool" disabled={busy} onClick={onReview}>Review usability & openings</button><button className="studio-tool" disabled={busy || !items.length} onClick={onArrange}>Preview arrangement</button></div>
  </section>;
}
