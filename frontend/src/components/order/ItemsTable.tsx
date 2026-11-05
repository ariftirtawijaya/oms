import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Button } from "@/components/ui/button";
import { productName, rupiah, voltageLabel } from "@/lib/format";

export function PriceCell({ it }: { it: any }) {
  if (it.unit_price_snapshot === null || it.unit_price_snapshot === undefined)
    return <span className="text-xs font-semibold text-orange-700" data-testid="price-pending-text">Harga Menunggu Penentuan Admin</span>;
  return <span className="tabular-nums">{rupiah(it.unit_price_snapshot)}</span>;
}

function ItemName({ it }: { it: any }) {
  return (
    <div>
      <p className="font-medium text-slate-900">{it.product_name_snapshot}</p>
      <div className="mt-0.5 flex flex-wrap items-center gap-1.5 text-xs text-slate-500">
        <span className="font-mono">{it.product_code_snapshot}</span>
        {it.is_custom && <Badge variant="outline" className="border-orange-200 bg-orange-50 px-1.5 py-0 text-[10px] text-orange-700">Custom{it.custom_name && it.custom_name !== it.product_name_snapshot ? `: ${it.custom_name}` : ""}</Badge>}
      </div>
    </div>
  );
}

type Props = { items: any[]; onAdjust?: (it: any) => void; onResolve?: (it: any) => void };

export function ItemsTable({ items, onAdjust, onResolve }: Props) {
  const admin = !!onAdjust;
  const Act = ({ it }: { it: any }) => admin ? (
    it.unit_price_snapshot === null
      ? <Button size="sm" className="bg-orange-600 text-white hover:bg-orange-700" onClick={() => onResolve?.(it)} data-testid={`resolve-custom-${it.item_id}`}>Tetapkan Harga</Button>
      : <Button size="sm" variant="outline" onClick={() => onAdjust?.(it)} data-testid={`adjust-price-${it.item_id}`}>Sesuaikan Harga</Button>
  ) : null;
  return (
    <>
      <div className="hidden overflow-x-auto md:block">
        <table className="w-full text-sm" data-testid="order-items-table">
          <thead className="bg-slate-50 text-left text-xs tracking-wide text-slate-500">
            <tr>
              <th className="px-3 py-2.5">Produk</th><th className="px-3">Voltase</th><th className="px-3 text-right">Qty Pesan</th>
              <th className="px-3 text-right">Harga Satuan</th><th className="px-3 text-right">Subtotal</th>
              <th className="px-3 text-right">Selesai Produksi</th><th className="px-3 text-right">Dikirim</th><th className="px-3 text-right">Sisa Kirim</th>
              {admin && <th className="px-3" />}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {items.map((it) => (
              <tr key={it.item_id} data-testid={`order-item-row-${it.item_id}`}>
                <td className="px-3 py-3"><ItemName it={it} /></td>
                <td className="px-3">{voltageLabel(it.voltage_snapshot) || "-"}</td>
                <td className="px-3 text-right tabular-nums">{it.qty_order}</td>
                <td className="px-3 text-right" data-testid="item-unit-price"><PriceCell it={it} /></td>
                <td className="px-3 text-right font-semibold tabular-nums" data-testid="item-subtotal">{it.unit_price_snapshot === null ? "-" : rupiah(it.subtotal)}</td>
                <td className="px-3 text-right tabular-nums">{it.qty_done}</td>
                <td className="px-3 text-right tabular-nums">{it.qty_shipped}</td>
                <td className="px-3 text-right font-semibold tabular-nums" data-testid="item-remaining-ship">{it.qty_remaining_ship}</td>
                {admin && <td className="px-3 text-right"><Act it={it} /></td>}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="space-y-3 md:hidden">
        {items.map((it) => (
          <div key={it.item_id} className="rounded-lg border border-slate-200 p-3">
            <ItemName it={it} />
            <div className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
              <span className="text-slate-500">Voltase</span><span className="text-right">{voltageLabel(it.voltage_snapshot) || "-"}</span>
              <span className="text-slate-500">Qty Pesan</span><span className="text-right tabular-nums">{it.qty_order} pcs</span>
              <span className="text-slate-500">Harga Satuan</span><span className="text-right"><PriceCell it={it} /></span>
              <span className="text-slate-500">Subtotal</span><span className="text-right font-semibold tabular-nums">{it.unit_price_snapshot === null ? "-" : rupiah(it.subtotal)}</span>
              <span className="text-slate-500">Selesai Produksi</span><span className="text-right tabular-nums">{it.qty_done} pcs</span>
              <span className="text-slate-500">Sudah Dikirim</span><span className="text-right tabular-nums">{it.qty_shipped} pcs</span>
              <span className="text-slate-500">Sisa Kirim</span><span className="text-right font-semibold tabular-nums">{it.qty_remaining_ship} pcs</span>
            </div>
            {admin && <div className="mt-3"><Act it={it} /></div>}
          </div>
        ))}
      </div>
    </>
  );
}

export function ProgressList({ items, done }: { items: any[]; done?: boolean }) {
  if (!items.length) return <p className="text-sm text-slate-500">{done ? "Belum ada item yang terkirim penuh." : "Semua item sudah terkirim."}</p>;
  return (
    <div className="space-y-3">
      {items.map((it) => (
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
    </div>
  );
}
