import React, { useState } from "react";
import {
  ColumnDef, SortingState, flexRender, getCoreRowModel, getFilteredRowModel, getPaginationRowModel,
  getSortedRowModel, useReactTable,
} from "@tanstack/react-table";
import { ArrowUpDown, ChevronDown, ChevronLeft, ChevronRight, Search } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { tokenMatch } from "@/lib/format";

type Props<T> = {
  data: T[];
  columns: ColumnDef<T, any>[];
  searchText?: (row: T) => string;
  searchPlaceholder?: string;
  mobileCard: (row: T) => React.ReactNode;
  mobileDetail?: (row: T) => React.ReactNode;
  toolbar?: React.ReactNode;
  pageSize?: number;
  testid: string;
  emptyText?: string;
};

export function DataTable<T>({ data, columns, searchText, searchPlaceholder = "Cari...", mobileCard, mobileDetail,
  toolbar, pageSize = 10, testid, emptyText = "Belum ada data." }: Props<T>) {
  const [sorting, setSorting] = useState<SortingState>([]);
  const [filter, setFilter] = useState("");
  const [open, setOpen] = useState<Record<string, boolean>>({});
  const table = useReactTable({
    data, columns, state: { sorting, globalFilter: filter },
    onSortingChange: setSorting, onGlobalFilterChange: setFilter,
    globalFilterFn: (row, _id, value) => (searchText ? tokenMatch(searchText(row.original), String(value)) : true),
    getCoreRowModel: getCoreRowModel(), getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(), getPaginationRowModel: getPaginationRowModel(),
    initialState: { pagination: { pageSize } },
  });
  const rows = table.getRowModel().rows;
  const total = table.getFilteredRowModel().rows.length;
  const { pageIndex, pageSize: ps } = table.getState().pagination;

  return (
    <div data-testid={testid} className="space-y-3">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
        {searchText && (
          <div className="relative w-full sm:max-w-xs">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
            <Input value={filter} onChange={(e) => setFilter(e.target.value)} placeholder={searchPlaceholder}
              className="h-10 bg-white pl-9" data-testid={`${testid}-search`} />
          </div>
        )}
        {toolbar}
      </div>

      <div className="hidden overflow-x-auto rounded-xl border border-slate-200 bg-white md:block">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
            {table.getHeaderGroups().map((hg) => (
              <tr key={hg.id}>
                {hg.headers.map((h) => (
                  <th key={h.id} className="whitespace-nowrap px-4 py-3 font-semibold">
                    {h.column.getCanSort() ? (
                      <button className="inline-flex items-center gap-1 hover:text-slate-900" onClick={h.column.getToggleSortingHandler()}
                        data-testid={`${testid}-sort-${h.column.id}`}>
                        {flexRender(h.column.columnDef.header, h.getContext())}<ArrowUpDown className="h-3 w-3" />
                      </button>
                    ) : flexRender(h.column.columnDef.header, h.getContext())}
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody className="divide-y divide-slate-100">
            {rows.map((r) => (
              <tr key={r.id} className="transition-colors hover:bg-slate-50/70">
                {r.getVisibleCells().map((c) => (
                  <td key={c.id} className="whitespace-nowrap px-4 py-3 align-middle">{flexRender(c.column.columnDef.cell, c.getContext())}</td>
                ))}
              </tr>
            ))}
            {!rows.length && (
              <tr><td colSpan={columns.length} className="px-4 py-10 text-center text-slate-500">{emptyText}</td></tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="space-y-2 md:hidden">
        {rows.map((r) => (
          <div key={r.id} className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
            {mobileCard(r.original)}
            {mobileDetail && (
              <>
                <button className="mt-3 flex w-full items-center justify-center gap-1 rounded-md bg-slate-50 py-2 text-xs font-medium text-slate-600"
                  onClick={() => setOpen((o) => ({ ...o, [r.id]: !o[r.id] }))} data-testid={`${testid}-expand-${r.index}`}>
                  {open[r.id] ? "Sembunyikan detail" : "Lihat detail"}
                  <ChevronDown className={`h-3.5 w-3.5 transition-transform ${open[r.id] ? "rotate-180" : ""}`} />
                </button>
                {open[r.id] && <div className="mt-3 border-t border-slate-100 pt-3 text-sm">{mobileDetail(r.original)}</div>}
              </>
            )}
          </div>
        ))}
        {!rows.length && <p className="rounded-xl border border-dashed p-8 text-center text-sm text-slate-500">{emptyText}</p>}
      </div>

      <div className="flex flex-col items-center justify-between gap-2 text-sm text-slate-500 sm:flex-row">
        <span data-testid={`${testid}-count`}>
          {total ? `Menampilkan ${pageIndex * ps + 1}–${Math.min((pageIndex + 1) * ps, total)} dari ${total} data` : "0 data"}
        </span>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={() => table.previousPage()} disabled={!table.getCanPreviousPage()}
            data-testid={`${testid}-prev`}><ChevronLeft /> Sebelumnya</Button>
          <span className="tabular-nums">{pageIndex + 1} / {Math.max(table.getPageCount(), 1)}</span>
          <Button variant="outline" size="sm" onClick={() => table.nextPage()} disabled={!table.getCanNextPage()}
            data-testid={`${testid}-next`}>Berikutnya <ChevronRight /></Button>
        </div>
      </div>
    </div>
  );
}

export function MobileRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-3 py-1">
      <span className="text-xs text-slate-500">{label}</span>
      <span className="text-right text-sm font-medium tabular-nums text-slate-900">{children}</span>
    </div>
  );
}
