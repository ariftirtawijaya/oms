import { useMemo, useState } from "react";
import { ChevronLeft, ChevronRight, Plus, Search, Zap } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { productName, rupiah, tokenMatch, voltageLabel } from "@/lib/format";
import { cn } from "@/lib/utils";

const PER_PAGE = 8;

function pageList(cur: number, total: number): number[] {
  const start = Math.max(1, Math.min(cur - 2, total - 4));
  return Array.from({ length: Math.min(5, total) }, (_, i) => start + i);
}

export function Catalog({ products, inCart, onAdd }: { products: any[]; inCart: Record<string, number>; onAdd: (p: any) => void }) {
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const filtered = useMemo(() => products.filter((p) => tokenMatch(`${p.code} ${productName(p.name, p.voltage)} ${p.voltage}`, q)), [products, q]);
  const pages = Math.max(1, Math.ceil(filtered.length / PER_PAGE));
  const cur = Math.min(page, pages);
  const shown = filtered.slice((cur - 1) * PER_PAGE, cur * PER_PAGE);

  return (
    <div data-testid="catalog">
      <div className="relative mb-4">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
        <Input value={q} onChange={(e) => { setQ(e.target.value); setPage(1); }} placeholder="Cari produk, contoh: headlamp aod 12v"
          className="h-11 bg-white pl-9" data-testid="catalog-search-input" />
      </div>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 2xl:grid-cols-4">
        {shown.map((p, i) => (
          <div key={p.id} style={{ animationDelay: `${i * 40}ms` }}
            className="fade-up group flex flex-col rounded-xl border border-slate-200 bg-white p-3 shadow-sm transition-transform duration-200 hover:-translate-y-1 hover:shadow-md sm:p-4"
            data-testid={`product-card-${p.code}`}>
            <div className="mb-3 flex items-center justify-between">
              <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-blue-50 text-blue-700"><Zap className="h-4 w-4" /></span>
              {voltageLabel(p.voltage) && <span className="rounded-md bg-slate-900 px-2 py-0.5 text-[11px] font-bold text-white">{voltageLabel(p.voltage)}</span>}
            </div>
            <p className="line-clamp-3 flex-1 text-sm font-semibold leading-snug text-slate-900">{p.name}</p>
            <p className="mt-1 font-mono text-[11px] text-slate-400">{p.code}</p>
            <p className="mt-2 font-heading text-base font-extrabold tabular-nums text-slate-900" data-testid={`product-price-${p.code}`}>{rupiah(p.price)}</p>
            <Button onClick={() => onAdd(p)} className={cn("mt-3 h-10 w-full text-white", inCart[p.id] ? "bg-emerald-600 hover:bg-emerald-700" : "bg-blue-700 hover:bg-blue-800")}
              data-testid={`add-to-cart-${p.code}`}>
              <Plus /> {inCart[p.id] ? `Tambah (${inCart[p.id]})` : "Tambah"}
            </Button>
          </div>
        ))}
      </div>
      {!shown.length && <p className="rounded-xl border border-dashed p-8 text-center text-sm text-slate-500" data-testid="catalog-empty">Produk tidak ditemukan.</p>}
      <div className="mt-4 flex flex-col items-center justify-between gap-2 sm:flex-row">
        <p className="text-sm text-slate-500" data-testid="catalog-count">
          {filtered.length ? `Menampilkan ${(cur - 1) * PER_PAGE + 1}–${Math.min(cur * PER_PAGE, filtered.length)} dari ${filtered.length} produk` : "0 produk"}
        </p>
        <div className="flex items-center gap-1">
          <Button size="icon" variant="outline" disabled={cur === 1} onClick={() => setPage(cur - 1)} aria-label="Sebelumnya" data-testid="catalog-prev"><ChevronLeft /></Button>
          {pageList(cur, pages).map((n) => (
            <Button key={n} size="icon" variant={n === cur ? "default" : "outline"} onClick={() => setPage(n)}
              className={n === cur ? "bg-blue-700 text-white hover:bg-blue-800" : ""} data-testid={`catalog-page-${n}`}>{n}</Button>
          ))}
          <Button size="icon" variant="outline" disabled={cur === pages} onClick={() => setPage(cur + 1)} aria-label="Berikutnya" data-testid="catalog-next"><ChevronRight /></Button>
        </div>
      </div>
    </div>
  );
}
