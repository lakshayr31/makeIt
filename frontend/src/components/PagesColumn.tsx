import { ChevronDown, ChevronUp, Copy, FilePlus, Trash2 } from "lucide-react";

/** Canva-style row above each page: "Page N - name" plus page actions. */
export function PageHeader({
  index,
  count,
  name,
  active,
  isNew,
  onMove,
  onDuplicate,
  onDelete,
  onAdd,
}: {
  index: number;
  count: number;
  name: string;
  active: boolean;
  isNew: boolean;
  onMove: (dir: -1 | 1) => void;
  onDuplicate: () => void;
  onDelete: () => void;
  onAdd: () => void;
}) {
  return (
    <div className={`page-header${active ? " page-header-active" : ""}`}>
      <span className="page-label">
        Page {index + 1} - <span className="page-name">{name}</span>
      </span>
      {isNew && <span className="page-new">New version</span>}
      <div className="page-actions">
        <button
          title="Move page up"
          disabled={index === 0}
          onClick={() => onMove(-1)}
        >
          <ChevronUp size={16} />
        </button>
        <button
          title="Move page down"
          disabled={index === count - 1}
          onClick={() => onMove(1)}
        >
          <ChevronDown size={16} />
        </button>
        <button title="Duplicate page" onClick={onDuplicate}>
          <Copy size={16} />
        </button>
        <button title="Delete page" disabled={count === 1} onClick={onDelete}>
          <Trash2 size={16} />
        </button>
        <button title="Add page" onClick={onAdd}>
          <FilePlus size={16} />
        </button>
      </div>
    </div>
  );
}
