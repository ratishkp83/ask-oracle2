import { ColumnMeta } from "../derive/columns";
import { SqlMeta } from "../derive/sql";
import { dimensionOrder } from "../derive/cascade";
import type { CascadePersisted } from "../api/schemas";

// The persisted shape of a cascading report (ADR-026). Stored on a saved report
// (additive Report.cascade) and resolved against a result at generate time. It is
// metadata only — column names + integers — and is never executed.
export interface CascadeSpec {
  dimensionOrder: string[]; // output column NAMES, top→down; [] = auto-derive from the SQL
  depth: number; // number of cascade levels (1..5)
  childrenPerLevel: number; // top-N child sections per level (the rest → "Others")
  rowsPerChild?: number; // per-section detail-row cap (default: server SafetyLimits)
}

export const DEFAULT_CASCADE_SPEC: CascadeSpec = {
  dimensionOrder: [],
  depth: 2,
  childrenPerLevel: 8,
};

export interface ResolvedCascade {
  dimIndices: number[]; // ordered dimension column indices, capped to depth
  childrenPerLevel: number;
  rowsPerChild?: number;
}

function clamp(n: number, lo: number, hi: number): number {
  if (!Number.isFinite(n)) return lo;
  return Math.max(lo, Math.min(hi, Math.round(n)));
}

// Resolve a spec against a concrete result: map dimension NAMES → column indices
// (or auto-derive the GROUP-BY order when none is given), and clamp depth/children
// to sane bounds. Pure; tolerant of unknown names (dropped) and bad numbers.
export function resolveCascade(
  spec: CascadeSpec,
  columns: string[],
  cols: ColumnMeta[],
  sqlMeta: SqlMeta | null,
): ResolvedCascade {
  const depth = clamp(spec.depth, 1, 5);
  const childrenPerLevel = clamp(spec.childrenPerLevel, 1, 50);

  let dimIndices: number[];
  if (spec.dimensionOrder && spec.dimensionOrder.length > 0) {
    dimIndices = spec.dimensionOrder.map((n) => columns.indexOf(n)).filter((i) => i >= 0);
  } else {
    dimIndices = dimensionOrder(cols, sqlMeta);
  }
  dimIndices = dimIndices.slice(0, depth);

  const rowsPerChild =
    spec.rowsPerChild != null && Number.isFinite(spec.rowsPerChild)
      ? Math.max(1, Math.round(spec.rowsPerChild))
      : undefined;

  return { dimIndices, childrenPerLevel, rowsPerChild };
}

// Map the internal camelCase spec to/from the persisted snake_case form stored on
// a Report (ADR-026). The wire shape matches the backend CascadeSpec exactly.
export function toPersistedSpec(s: CascadeSpec): CascadePersisted {
  return {
    dimension_order: s.dimensionOrder,
    depth: s.depth,
    children_per_level: s.childrenPerLevel,
    rows_per_child: s.rowsPerChild ?? null,
  };
}

export function fromPersistedSpec(p: CascadePersisted): CascadeSpec {
  return {
    dimensionOrder: p.dimension_order,
    depth: p.depth,
    childrenPerLevel: p.children_per_level,
    rowsPerChild: p.rows_per_child ?? undefined,
  };
}
