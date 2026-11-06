import React, { useState } from "react";
import {
  ColumnDef, SortingState, flexRender, getCoreRowModel, getFilteredRowModel,
  getSortedRowModel, useReactTable,
} from "@tanstack/react-table";
import { ArrowDown, ArrowUp, ArrowUpDown, ChevronDown, Search } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Pager, usePager } from "@/components/Pager";
import { tokenMatch } from "@/lib/format";

export type ServerPaging = {
  total: number; page: number; pageSize: number; onPage: (p: number) => void; onPageSize: (n: number) => void;
  search: string; onSearch: (s: string) => void; sorting: SortingState; onSorting: (s: SortingState) => void;
};

type Props<T> = {
  data: T[];
  columns: ColumnDef<T, any>[];
  searchText?: (row: T) => string;
  searchPlaceholder?: string;
  mobileCard: (row: T) => React.ReactNode;
  mobileDetail?: (row: T) => React.ReactNode;
  toolbar?: React.ReactNode;
  testid: string;
  emptyText?: string;
  server?: ServerPaging;
};

export function DataTable<T>({ data, columns, searchText, searchPlaceholder = "Cari...", mobileCard, mobileDetail,
  toolbar, testid, emptyText = "Belum ada data.", server }: Props<T>) {
  const [sorting, setSorting] = useState<SortingState>([]);
  const [filter, setFilter] = useState("");
  const [open, setOpen] = useState<Record<string, boolean>>({});
  const table = useReactTable({
    data, columns,
    state: server ? { sorting: server.sorting } : { sorting, globalFilter: filter },
    onSortingChange: server ? (u) => server.onSorting(typeof u === "function" ? u(server.sorting) : u) : setSorting,
    onGlobalFilterChange: setFilter,
    manualSorting: !!server, manualFiltering: !!server,
    globalFilterFn: (row, _id, value) => (searchText ? tokenMatch(searchText(row.original), String(value)) : true),
    getCoreRowModel: getCoreRowModel(), getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
  });
  const all = table.getRowModel().rows;
  const pager = usePager(testid, server ? 0 : all.length, [filter, data.length]);
  const rows = server ? all : all.slice(pager.start, pager.start + pager.pageSize);
  const searchValue = server ? server.search : filter;
  const onSearch = (v: string) => (server ? server.onSearch(v) : setFilter(v));

  return (
    <div data-testid={testid} className="space-y-3">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
        {(searchText || server) && (
          <div className="relative w-full sm:max-w-xs">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
            <Input value={searchValue} onChange={(e) => onSearch(e.target.value)} placeholder={searchPlaceholder}
              className="h-10 bg-white pl-9" data-testid={`${testid}-search`} />
          </div>
        )}
        {toolbar}
      </div>

      <div className="hidden overflow-x-auto rounded-xl border border-slate-200 bg-white md:block">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-xs tracking-wide text-slate-500">
            {table.getHeaderGroups().map((hg) => (
              <tr key={hg.id}>
                {hg.headers.map((h) => (
                  <th key={h.id} className="whitespace-nowrap px-3 py-3 font-semibold">
                    {h.column.getCanSort() ? (
                      <button className="inline-flex items-center gap-1 hover:text-slate-900" onClick={h.column.getToggleSortingHandler()}
                        data-testid={`${testid}-sort-${h.column.id}`}>
                        {flexRender(h.column.columnDef.header, h.getContext())}
                        {h.column.getIsSorted() === "asc" ? <ArrowUp className="h-3 w-3 text-blue-700" /> : h.column.getIsSorted() === "desc" ? <ArrowDown className="h-3 w-3 text-blue-700" /> : <ArrowUpDown className="h-3 w-3" />}
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
                  <td key={c.id} className="whitespace-nowrap px-3 py-3 align-middle">{flexRender(c.column.columnDef.cell, c.getContext())}</td>
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

      {server
        ? <Pager testid={testid} total={server.total} page={server.page} pageSize={server.pageSize} onPage={server.onPage} onPageSize={server.onPageSize} />
        : <Pager testid={testid} total={all.length} page={pager.page} pageSize={pager.pageSize} onPage={pager.setPage} onPageSize={pager.setPageSize} />}
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
