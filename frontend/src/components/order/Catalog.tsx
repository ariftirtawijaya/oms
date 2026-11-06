import { useMemo, useState } from "react";
import { Plus, Search, Zap } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Pager, usePager } from "@/components/Pager";
import { productName, rupiah, tokenMatch, voltageLabel } from "@/lib/format";
import { cn } from "@/lib/utils";

export function Catalog({ products, inCart, onAdd, disabled }: { products: any[]; inCart: Record<string, number>; onAdd: (p: any) => void; disabled?: boolean }) {
  const [q, setQ] = useState("");
  const filtered = useMemo(() => products.filter((p) => tokenMatch(`${productName(p.name, p.voltage)} ${p.voltage}`, q)), [products, q]);
  const pg = usePager("catalog", filtered.length, [q]);
  const shown = filtered.slice(pg.start, pg.start + pg.pageSize);

  return (
    <div data-testid="catalog">
      <div className="relative mb-4">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
        <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Cari produk, contoh: headlamp aod 12v"
          className="h-11 bg-white pl-9" data-testid="catalog-search-input" />
      </div>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 2xl:grid-cols-4">
        {shown.map((p, i) => (
          <div key={p.id} style={{ animationDelay: `${i * 40}ms` }}
            className="fade-up group flex h-full flex-col rounded-xl border border-slate-200 bg-white p-3 shadow-sm transition-transform duration-200 hover:-translate-y-1 hover:shadow-md sm:p-4"
            data-testid={`product-card-${p.id}`}>
            <div className="mb-3 flex items-center justify-between">
              <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-blue-50 text-blue-700"><Zap className="h-4 w-4" /></span>
              {voltageLabel(p.voltage) && <span className="rounded-md bg-slate-900 px-2 py-0.5 text-[11px] font-bold text-white">{voltageLabel(p.voltage)}</span>}
            </div>
            <p className="break-words text-sm font-semibold leading-snug text-slate-900" data-testid={`product-name-${p.id}`}>{p.name}</p>
            <div className="mt-auto pt-3">
              <p className="font-heading text-base font-extrabold tabular-nums text-slate-900" data-testid={`product-price-${p.id}`}>{rupiah(p.price)}</p>
              <Button onClick={() => onAdd(p)} disabled={disabled} className={cn("mt-3 h-10 w-full text-white", inCart[p.id] ? "bg-emerald-600 hover:bg-emerald-700" : "bg-blue-700 hover:bg-blue-800")}
                data-testid={`add-to-cart-${p.id}`}>
                <Plus /> {inCart[p.id] ? `Tambah (${inCart[p.id]})` : "Tambah"}
              </Button>
            </div>
          </div>
        ))}
      </div>
      {!shown.length && <p className="rounded-xl border border-dashed p-8 text-center text-sm text-slate-500" data-testid="catalog-empty">Produk tidak ditemukan.</p>}
      <div className="mt-4"><Pager testid="catalog" total={filtered.length} page={pg.page} pageSize={pg.pageSize} onPage={pg.setPage} onPageSize={pg.setPageSize} /></div>
    </div>
  );
}
