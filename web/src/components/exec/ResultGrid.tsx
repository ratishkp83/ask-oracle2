import { useMemo, useRef } from "react";
import { flexRender, getCoreRowModel, useReactTable } from "@tanstack/react-table";
import { useVirtualizer } from "@tanstack/react-virtual";
import { ColumnMeta } from "@/lib/derive/columns";
import { formatCell } from "@/lib/format";

// Band 4 (B-3/B-6): the detail grid — the ONLY scroll region. Fixed height from
// the parent, sticky header, virtualized rows (spacer pattern keeps a single
// <table> so columns stay aligned). Numeric columns right-aligned + tabular.
export function ResultGrid({
  columns: cnames,
  rows: data,
  cols,
}: {
  columns: string[];
  rows: unknown[][];
  cols: ColumnMeta[];
}) {
  const parentRef = useRef<HTMLDivElement>(null);

  const columns = useMemo(
    () =>
      cnames.map((name, i) => ({
        id: String(i),
        header: name,
        accessorFn: (row: unknown[]) => row[i],
        meta: { numeric: cols[i]?.numericAligned ?? false },
      })),
    [cnames, cols],
  );

  const table = useReactTable({ data, columns, getCoreRowModel: getCoreRowModel() });
  const rows = table.getRowModel().rows;

  const virt = useVirtualizer({
    count: rows.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 33,
    overscan: 12,
  });
  const items = virt.getVirtualItems();
  const padTop = items.length ? items[0].start : 0;
  const padBottom = items.length ? virt.getTotalSize() - items[items.length - 1].end : 0;
  const colCount = cnames.length;

  return (
    <div ref={parentRef} className="h-full overflow-auto rounded-b-card">
      <table className="w-full border-collapse text-[12.5px]">
        <thead className="sticky top-0 z-10">
          <tr className="bg-surface-sunken text-ink-muted">
            {table.getFlatHeaders().map((h) => (
              <th
                key={h.id}
                className={`whitespace-nowrap px-3.5 py-2 font-semibold ${
                  (h.column.columnDef.meta as { numeric?: boolean })?.numeric ? "text-right" : "text-left"
                }`}
              >
                {flexRender(h.column.columnDef.header, h.getContext())}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {padTop > 0 && (
            <tr>
              <td colSpan={colCount} style={{ height: padTop }} />
            </tr>
          )}
          {items.map((vi) => {
            const row = rows[vi.index];
            return (
              <tr key={row.id} className="border-t border-[#EDEAE3] hover:bg-surface-sunken">
                {row.getVisibleCells().map((cell) => (
                  <td
                    key={cell.id}
                    className={`whitespace-nowrap px-3.5 py-2 ${
                      (cell.column.columnDef.meta as { numeric?: boolean })?.numeric
                        ? "num text-right text-ink"
                        : "text-ink"
                    }`}
                  >
                    {formatCell(cell.getValue())}
                  </td>
                ))}
              </tr>
            );
          })}
          {padBottom > 0 && (
            <tr>
              <td colSpan={colCount} style={{ height: padBottom }} />
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
