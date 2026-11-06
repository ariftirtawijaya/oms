import { useEffect, useState } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

export const PAGE_SIZES = [10, 20, 50, 100];

export function usePageSize(key: string, fallback = 10, sizes: number[] = PAGE_SIZES): [number, (n: number) => void] {
  const storageKey = `relaylab_pagesize_${key}`;
  const [size, setSize] = useState<number>(() => {
    const v = Number(localStorage.getItem(storageKey));
    return sizes.includes(v) ? v : fallback;
  });
  useEffect(() => { localStorage.setItem(storageKey, String(size)); }, [size, storageKey]);
  return [size, setSize];
}

/** Clamp page (1-based) when total shrinks. */
export function usePager(key: string, total: number, resetDeps: unknown[] = [], sizes: number[] = PAGE_SIZES) {
  const [pageSize, setPageSize] = usePageSize(key, sizes[0], sizes);
  const [page, setPage] = useState(1);
  const pages = Math.max(1, Math.ceil(total / pageSize));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { setPage(1); }, [pageSize, ...resetDeps]);
  useEffect(() => { if (page > pages) setPage(pages); }, [page, pages]);
  const cur = Math.min(page, pages);
  return { page: cur, setPage, pageSize, setPageSize, pages, start: (cur - 1) * pageSize };
}

function pageList(cur: number, total: number): number[] {
  const n = Math.min(5, total);
  const start = Math.max(1, Math.min(cur - 2, total - n + 1));
  return Array.from({ length: n }, (_, i) => start + i);
}

export function Pager({ total, page, pageSize, onPage, onPageSize, testid, sizes = PAGE_SIZES, compact }: {
  total: number; page: number; pageSize: number; onPage: (p: number) => void; onPageSize: (n: number) => void; testid: string; sizes?: number[]; compact?: boolean;
}) {
  const pages = Math.max(1, Math.ceil(total / pageSize));
  const from = total ? (page - 1) * pageSize + 1 : 0;
  const to = Math.min(page * pageSize, total);
  const label = compact ? "hidden" : "hidden sm:inline";
  return (
    <div className={compact ? "flex flex-col gap-2 text-sm text-slate-500" : "flex flex-col gap-3 text-sm text-slate-500 sm:flex-row sm:items-center sm:justify-between"} data-testid={`${testid}-pager`}>
      <div className={compact ? "flex items-center justify-between gap-2" : "flex flex-wrap items-center gap-2"}>
        <span className={compact ? "whitespace-nowrap text-xs sm:text-sm" : undefined} data-testid={`${testid}-count`}>{total ? `Menampilkan ${from}–${to} dari ${total} data` : "0 data"}</span>
        <Select value={String(pageSize)} onValueChange={(v) => onPageSize(Number(v))}>
          <SelectTrigger className="h-9 w-[92px] bg-white" aria-label="Jumlah data per halaman" data-testid={`${testid}-page-size`}><SelectValue /></SelectTrigger>
          <SelectContent>{sizes.map((n) => <SelectItem key={n} value={String(n)}>{n} data</SelectItem>)}</SelectContent>
        </Select>
      </div>
      <div className={compact ? "flex items-center justify-center gap-1" : "flex items-center gap-1 self-center sm:self-auto"}>
        <Button variant="outline" size="sm" className="h-9 px-2 sm:px-3" disabled={page <= 1} onClick={() => onPage(page - 1)} aria-label="Sebelumnya" data-testid={`${testid}-prev`}>
          <ChevronLeft /><span className={label}>Sebelumnya</span>
        </Button>
        {pageList(page, pages).map((n) => (
          <Button key={n} size="sm" variant={n === page ? "default" : "outline"} onClick={() => onPage(n)} aria-current={n === page ? "page" : undefined}
            className={`h-9 w-9 p-0 tabular-nums ${n === page ? "bg-blue-700 text-white hover:bg-blue-800" : ""}`} data-testid={`${testid}-page-${n}`}>{n}</Button>
        ))}
        <Button variant="outline" size="sm" className="h-9 px-2 sm:px-3" disabled={page >= pages} onClick={() => onPage(page + 1)} aria-label="Berikutnya" data-testid={`${testid}-next`}>
          <span className={label}>Berikutnya</span><ChevronRight />
        </Button>
      </div>
    </div>
  );
}
