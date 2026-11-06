import { useState } from "react";
import { toast } from "sonner";
import { ImageIcon, Truck, XCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Empty, Field } from "@/components/common";
import { Pager, usePager } from "@/components/Pager";
import { api, errMsg, fileUrl } from "@/lib/api";
import { fmtDateTime, productName, rupiah } from "@/lib/format";

export function PaymentsList({ payments, orderId, admin, onChanged }: { payments: any[]; orderId: string; admin?: boolean; onChanged?: () => void }) {
  const [voiding, setVoiding] = useState<any>(null);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const pg = usePager("payments", payments.length);
  const doVoid = async () => {
    if (reason.trim().length < 3) return toast.error("Alasan koreksi wajib diisi.");
    setBusy(true);
    try {
      await api.post(`/orders/${orderId}/payments/${voiding.id}/void`, { reason });
      toast.success("Pembayaran dibatalkan dan tercatat di histori koreksi.");
      setVoiding(null); setReason(""); onChanged?.();
    } catch (e) { toast.error(errMsg(e)); } finally { setBusy(false); }
  };
  if (!payments.length) return <Empty text="Belum ada pembayaran." testid="payments-empty" />;
  return (
    <div className="space-y-2" data-testid="payments-list">
      {payments.slice(pg.start, pg.start + pg.pageSize).map((p, idx) => { const i = pg.start + idx; return (
        <div key={p.id} className={`flex flex-wrap items-start justify-between gap-2 rounded-lg border p-3 ${p.is_void ? "border-red-200 bg-red-50/50" : "border-slate-200"}`} data-testid={`payment-row-${i}`}>
          <div>
            <p className={`font-heading text-base font-bold tabular-nums ${p.is_void ? "text-slate-400 line-through" : "text-slate-900"}`}>{rupiah(p.amount)}</p>
            <p className="text-xs text-slate-500">{fmtDateTime(p.paid_at)}{admin && p.recorded_by_name ? ` • dicatat ${p.recorded_by_name}` : ""}</p>
            {p.notes && <p className="mt-1 text-sm text-slate-600">{p.notes}</p>}
            {p.is_void && <p className="mt-1 text-xs font-medium text-red-700">Dibatalkan {fmtDateTime(p.voided_at)} oleh {p.voided_by_name}: {p.void_reason}</p>}
          </div>
          {admin && !p.is_void && (
            <Button size="sm" variant="ghost" className="text-red-600 hover:bg-red-50 hover:text-red-700" onClick={() => setVoiding(p)} data-testid={`payment-void-${i}`}>
              <XCircle /> Koreksi
            </Button>
          )}
        </div>
      ); })}
      <Pager testid="payments" total={payments.length} page={pg.page} pageSize={pg.pageSize} onPage={pg.setPage} onPageSize={pg.setPageSize} />
      <Dialog open={!!voiding} onOpenChange={(o) => !o && setVoiding(null)}>
        <DialogContent className="max-w-md">
          <DialogHeader><DialogTitle>Koreksi Pembayaran</DialogTitle></DialogHeader>
          <p className="text-sm text-slate-600">Pembayaran {voiding && rupiah(voiding.amount)} akan dibatalkan (tidak dihapus) dan tercatat di histori. Jika nominal salah, tambahkan pembayaran baru dengan nominal yang benar.</p>
          <Field label="Alasan koreksi"><Input value={reason} onChange={(e) => setReason(e.target.value)} data-testid="payment-void-reason" /></Field>
          <DialogFooter><Button variant="destructive" onClick={doVoid} disabled={busy} data-testid="payment-void-confirm">Batalkan Pembayaran</Button></DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

export function ShipmentCards({ shipments }: { shipments: any[] }) {
  const [photo, setPhoto] = useState<string | null>(null);
  const pg = usePager("shipments", shipments.length);
  if (!shipments.length) return <Empty text="Belum ada pengiriman." testid="shipments-empty" />;
  return (
    <div className="space-y-3">
    <div className="grid gap-3 sm:grid-cols-2" data-testid="shipments-list">
      {shipments.slice(pg.start, pg.start + pg.pageSize).map((s, idx) => { const i = pg.start + idx; return (
        <div key={s.id} className="rounded-xl border border-slate-200 p-4" data-testid={`shipment-card-${i}`}>
          <div className="flex items-start justify-between gap-2">
            <div className="flex items-center gap-2">
              <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-50 text-blue-700"><Truck className="h-4 w-4" /></span>
              <div><p className="text-sm font-bold">{s.courier}</p><p className="text-xs text-slate-500">{fmtDateTime(s.shipped_at)}</p></div>
            </div>
            <span className="text-xs font-semibold text-slate-500">#{i + 1}</span>
          </div>
          <p className="mt-3 text-xs text-slate-500">Nomor Resi</p>
          <p className="font-mono text-sm font-semibold" data-testid={`shipment-tracking-${i}`}>{s.tracking_no}</p>
          {s.notes && <p className="mt-2 text-sm text-slate-600">Catatan: {s.notes}</p>}
          <ul className="mt-3 space-y-1 border-t border-slate-100 pt-3 text-sm">
            {s.items.map((it: any) => (
              <li key={it.item_id} className="flex justify-between gap-2"><span>{productName(it.product_name_snapshot, it.voltage_snapshot)}</span><b className="shrink-0 tabular-nums">{it.qty} pcs</b></li>
            ))}
          </ul>
          {s.photo_filename ? (
            <button onClick={() => setPhoto(s.photo_filename)} className="mt-3 block w-full overflow-hidden rounded-lg border" data-testid={`shipment-photo-${i}`}>
              <img src={fileUrl(s.photo_filename)} alt="Foto resi" className="h-40 w-full object-cover transition-transform duration-200 hover:scale-105" />
            </button>
          ) : <p className="mt-3 flex items-center gap-1 text-xs text-slate-400"><ImageIcon className="h-3.5 w-3.5" /> Tidak ada foto resi</p>}
        </div>
      ); })}
    </div>
      <Pager testid="shipments" total={shipments.length} page={pg.page} pageSize={pg.pageSize} onPage={pg.setPage} onPageSize={pg.setPageSize} />
      <Dialog open={!!photo} onOpenChange={(o) => !o && setPhoto(null)}>
        <DialogContent className="max-w-2xl">
          <DialogHeader><DialogTitle>Foto Resi</DialogTitle></DialogHeader>
          {photo && <img src={fileUrl(photo)} alt="Foto resi" className="max-h-[75vh] w-full rounded-lg object-contain" data-testid="shipment-photo-preview" />}
        </DialogContent>
      </Dialog>
    </div>
  );
}
