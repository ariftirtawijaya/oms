import React, { useState } from "react";
import { ChevronDown } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Button } from "@/components/ui/button";
import { Pager, usePager } from "@/components/Pager";
import { productName, rupiah, voltageLabel } from "@/lib/format";
import { cn } from "@/lib/utils";

export function PriceCell({ it }: { it: any }) {
  if (it.unit_price_snapshot === null || it.unit_price_snapshot === undefined)
    return <span className="text-xs font-semibold text-orange-700" data-testid="price-pending-text">Harga Menunggu Penentuan Admin</span>;
  return <span className="tabular-nums">{rupiah(it.unit_price_snapshot)}</span>;
}

function ItemName({ it }: { it: any }) {
  return (
    <div>
      <p className="break-words font-medium text-slate-900">{it.product_name_snapshot}{voltageLabel(it.voltage_snapshot) ? ` ${voltageLabel(it.voltage_snapshot)}` : ""}</p>
      <div className="mt-0.5 flex flex-wrap items-center gap-1.5 text-xs text-slate-500">
        {it.is_custom && <Badge variant="outline" className="border-orange-200 bg-orange-50 px-1.5 py-0 text-[10px] text-orange-700">Custom{it.custom_name && it.custom_name !== it.product_name_snapshot ? `: ${it.custom_name}` : ""}</Badge>}
      </div>
    </div>
  );
}

type Props = { items: any[]; onAdjust?: (it: any) => void; onResolve?: (it: any) => void; onProgress?: (it: any) => void };

export function ItemsTable({ items, onAdjust, onResolve, onProgress }: Props) {
  const admin = !!onAdjust;
  const Act = ({ it }: { it: any }) => admin ? (
    it.unit_price_snapshot === null
      ? <Button size="sm" className="bg-orange-600 text-white hover:bg-orange-700" onClick={() => onResolve?.(it)} data-testid={`resolve-custom-${it.item_id}`}>Tetapkan Harga</Button>
      : <Button size="sm" variant="outline" onClick={() => onAdjust?.(it)} data-testid={`adjust-price-${it.item_id}`}>Sesuaikan Harga</Button>
  ) : null;
  const [open, setOpen] = useState<Record<string, boolean>>({});
  const pg = usePager("order-items", items.length);
  const shown = items.slice(pg.start, pg.start + pg.pageSize);
  const Row = ({ label, children }: { label: string; children: React.ReactNode }) => (
    <div className="flex items-start justify-between gap-3 py-1"><span className="text-slate-500">{label}</span><span className="text-right font-medium tabular-nums">{children}</span></div>
  );
  return (
    <div className="space-y-3" data-testid="order-items-table">
      <div className="divide-y divide-slate-100 overflow-hidden rounded-lg border border-slate-200">
        {shown.map((it) => {
          const isOpen = !!open[it.item_id];
          const pending = it.unit_price_snapshot === null || it.unit_price_snapshot === undefined;
          return (
            <div key={it.item_id} data-testid={`order-item-row-${it.item_id}`}>
              <button type="button" onClick={() => setOpen((s) => ({ ...s, [it.item_id]: !isOpen }))}
                aria-expanded={isOpen} aria-controls={`item-panel-${it.item_id}`}
                className="flex w-full items-start gap-3 px-3 py-3 text-left transition-colors hover:bg-slate-50 focus-visible:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-blue-500 sm:px-4"
                data-testid={`order-item-toggle-${it.item_id}`}>
                <div className="min-w-0 flex-1">
                  <ItemName it={it} />
                  <p className="mt-1 text-sm text-slate-600">
                    Qty: <b className="tabular-nums">{it.qty_order} pcs</b> —{" "}
                    {pending ? <span className="font-semibold text-orange-700" data-testid="item-subtotal-pending">Harga Belum Ditentukan</span>
                      : <b className="tabular-nums" data-testid="item-subtotal">{rupiah(it.subtotal)}</b>}
                  </p>
                </div>
                <ChevronDown className={cn("mt-1 h-5 w-5 shrink-0 text-slate-400 transition-transform duration-200", isOpen && "rotate-180")} />
              </button>
              <div id={`item-panel-${it.item_id}`} role="region" className={cn("grid transition-all duration-200 ease-out", isOpen ? "grid-rows-[1fr] opacity-100" : "grid-rows-[0fr] opacity-0")}>
                <div className="overflow-hidden">
                  {isOpen && (
                    <div className="bg-slate-50/60 px-3 pb-4 pt-1 text-sm sm:px-4" data-testid={`order-item-detail-${it.item_id}`}>
                      <div className="grid gap-x-8 sm:grid-cols-2">
                        <Row label="Nama Produk"><span className="break-words">{it.product_name_snapshot}</span></Row>
                        <Row label="Voltase">{voltageLabel(it.voltage_snapshot) || "-"}</Row>
                        <Row label="Qty Pesan">{it.qty_order} pcs</Row>
                        <Row label="Harga Satuan"><span data-testid="item-unit-price"><PriceCell it={it} /></span></Row>
                        <Row label="Subtotal">{pending ? "Harga Belum Ditentukan" : rupiah(it.subtotal)}</Row>
                        <Row label="Selesai Produksi">{it.qty_done} pcs</Row>
                        <Row label="Sudah Dikirim">{it.qty_shipped} pcs</Row>
                        <Row label="Sisa Kirim"><span data-testid="item-remaining-ship">{it.qty_remaining_ship} pcs</span></Row>
                        {it.notes && <Row label="Catatan">{it.notes}</Row>}
                      </div>
                      {admin && (
                        <div className="mt-3 flex flex-wrap gap-2 border-t border-slate-200 pt-3">
                          <Act it={it} />
                          {onProgress && <Button size="sm" variant="outline" onClick={() => onProgress(it)} data-testid={`item-progress-${it.item_id}`}>Atur Selesai Produksi</Button>}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>
      {items.length > 0 && <Pager testid="order-items" total={items.length} page={pg.page} pageSize={pg.pageSize} onPage={pg.setPage} onPageSize={pg.setPageSize} />}
    </div>
  );
}

const PROGRESS_SIZES = [5, 10, 20, 50, 100];

export function ProgressList({ items, done }: { items: any[]; done?: boolean }) {
  const key = done ? "reseller-finished-items" : "reseller-unfinished-items";
  const pg = usePager(key, items.length, [], PROGRESS_SIZES);
  if (!items.length) return <p className="rounded-lg border border-dashed border-slate-200 bg-slate-50 p-6 text-center text-sm text-slate-500" data-testid={`${key}-empty`}>{done ? "Belum ada item yang terkirim penuh." : "Semua item sudah terkirim."}</p>;
  const shown = items.slice(pg.start, pg.start + pg.pageSize);
  return (
    <div className="space-y-3" data-testid={`${key}-list`}>
      {shown.map((it) => (
        <div key={it.item_id} className="rounded-lg border border-slate-200 p-3" data-testid={`progress-item-${it.item_id}`}>
          <div className="flex items-start justify-between gap-2">
            <p className="text-sm font-medium">{productName(it.product_name_snapshot, it.voltage_snapshot)}</p>
            <span className="shrink-0 text-xs font-semibold tabular-nums text-slate-600">{it.qty_order} pcs</span>
          </div>
          {!done && (
            <div className="mt-2 space-y-1.5 text-xs text-slate-600">
              <div className="flex justify-between"><span>Produksi {it.qty_done}/{it.qty_order}</span><span>Dikirim {it.qty_shipped}/{it.qty_order}</span></div>
              <Progress value={(it.qty_done / it.qty_order) * 100} className="h-1.5" />
              <p>Sisa kirim: <b className="tabular-nums">{it.qty_remaining_ship} pcs</b></p>
            </div>
          )}
        </div>
      ))}
      <Pager testid={key} total={items.length} page={pg.page} pageSize={pg.pageSize} onPage={pg.setPage} onPageSize={pg.setPageSize} sizes={PROGRESS_SIZES} compact />
    </div>
  );
}
