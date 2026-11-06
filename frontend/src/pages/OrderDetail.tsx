import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { ArrowLeft, Banknote, Factory, Save, Truck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { PaymentBadge, PricePendingBadge, StatusBadge } from "@/components/badges";
import { Empty, Loading, Section, StatCard } from "@/components/common";
import { ItemsTable, ProgressList } from "@/components/order/ItemsTable";
import { PaymentsList, ShipmentCards } from "@/components/order/History";
import { PaymentDialog, PriceAdjustDialog, ProgressDialog, ResolveCustomDialog, ShipmentDialog } from "@/components/order/AdminDialogs";
import { api, errMsg } from "@/lib/api";
import { STATUS_META, fmtDateTime, rupiah } from "@/lib/format";

function Summary({ o }: { o: any }) {
  return (
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
      <StatCard label="Total Qty" value={`${o.total_qty} pcs`} testid="order-total-qty" />
      <StatCard label="Nilai Order" value={rupiah(o.grand_total)} hint={o.price_pending ? "Belum termasuk item custom yang harganya belum ditentukan" : undefined} testid="order-grand-total" />
      <StatCard label="Sudah Dibayar" value={rupiah(o.total_paid)} testid="order-total-paid" />
      {o.remaining < 0
        ? <StatCard label="Kelebihan Bayar" value={rupiah(-o.remaining)} hint="Tercatat sebagai kredit reseller" tone="violet" testid="order-overpaid" />
        : <StatCard label="Sisa Tagihan" value={rupiah(o.remaining)} testid="order-remaining" />}
    </div>
  );
}

function StatusControl({ o, onDone }: { o: any; onDone: () => void }) {
  const [s, setS] = useState(o.status);
  const [busy, setBusy] = useState(false);
  useEffect(() => { setS(o.status); }, [o.status]);
  const save = async () => {
    setBusy(true);
    try { await api.patch(`/orders/${o.id}/status`, { status: s }); toast.success("Status order diperbarui."); onDone(); }
    catch (e) { toast.error(errMsg(e)); } finally { setBusy(false); }
  };
  return (
    <div className="flex gap-2">
      <Select value={s} onValueChange={setS}>
        <SelectTrigger className="h-10 w-full bg-white sm:w-52" data-testid="order-status-select"><SelectValue /></SelectTrigger>
        <SelectContent>{Object.entries(STATUS_META).map(([k, v]) => <SelectItem key={k} value={k}>{v.label}</SelectItem>)}</SelectContent>
      </Select>
      <Button onClick={save} disabled={busy || s === o.status} className="h-10 bg-blue-700 text-white hover:bg-blue-800" data-testid="order-status-save"><Save /> Simpan</Button>
    </div>
  );
}

function InternalNotes({ o, onDone }: { o: any; onDone: () => void }) {
  const [v, setV] = useState(o.internal_notes || "");
  const save = async () => {
    try { await api.put(`/orders/${o.id}/notes`, { internal_notes: v }); toast.success("Catatan internal disimpan."); onDone(); }
    catch (e) { toast.error(errMsg(e)); }
  };
  return (
    <div className="space-y-2">
      <Textarea rows={3} value={v} onChange={(e) => setV(e.target.value)} placeholder="Hanya terlihat oleh admin" data-testid="internal-notes-input" />
      <Button size="sm" variant="outline" onClick={save} data-testid="internal-notes-save">Simpan Catatan</Button>
    </div>
  );
}

function Adjustments({ list }: { list: any[] }) {
  if (!list?.length) return <Empty text="Belum ada penyesuaian harga." />;
  return (
    <div className="space-y-2" data-testid="price-adjustments-list">
      {[...list].reverse().map((a, i) => (
        <div key={i} className="rounded-lg border border-slate-200 p-3 text-sm">
          <p className="font-medium">{a.type === "penetapan_custom" ? "Penetapan harga custom" : "Penyesuaian harga"} — {a.product_name}</p>
          <p className="tabular-nums text-slate-600">{a.old_price === null ? "Belum berharga" : rupiah(a.old_price)} → <b>{rupiah(a.new_price)}</b> • Total {rupiah(a.old_grand_total)} → {rupiah(a.new_grand_total)}</p>
          <p className="text-xs text-slate-500">{fmtDateTime(a.at)} oleh {a.admin_name} • Alasan: {a.reason}</p>
        </div>
      ))}
    </div>
  );
}

export default function OrderDetailPage({ admin }: { admin?: boolean }) {
  const { id } = useParams();
  const qc = useQueryClient();
  const { data, isLoading, error } = useQuery({ queryKey: ["order", id], queryFn: () => api.get(`/orders/${id}`).then((r) => r.data), staleTime: 0 });
  const [dlg, setDlg] = useState<string | null>(null);
  const [item, setItem] = useState<any>(null);
  const refresh = () => { qc.invalidateQueries({ queryKey: ["order", id] }); qc.invalidateQueries({ queryKey: ["orders"] }); qc.invalidateQueries({ queryKey: ["dashboard"] }); };
  if (isLoading) return <Loading />;
  if (error) return <Empty text={errMsg(error)} testid="order-detail-error" />;
  const { order: o, payments, shipments } = data;
  const back = admin ? "/admin/orders" : "/app/orders";
  const unfinished = o.items.filter((i: any) => i.qty_order > i.qty_shipped);
  const finished = o.items.filter((i: any) => i.qty_shipped >= i.qty_order);
  const close = () => { setDlg(null); setItem(null); };

  return (
    <div className="space-y-5 fade-up" data-testid="order-detail-page">
      <Link to={back} className="inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-900" data-testid="order-back-link"><ArrowLeft className="h-4 w-4" /> Kembali</Link>
      <div className="flex flex-col gap-4 rounded-xl border border-slate-200 bg-white p-4 shadow-sm sm:p-5 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <p className="text-xs uppercase tracking-wide text-slate-500">Kode Order</p>
          <h1 className="font-heading text-2xl font-extrabold tracking-tight sm:text-3xl" data-testid="order-code">{o.code}</h1>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <StatusBadge status={o.status} /><PaymentBadge status={o.payment_status} />{o.price_pending && <PricePendingBadge />}
          </div>
          <p className="mt-2 text-sm text-slate-600">{fmtDateTime(o.created_at)} • {o.reseller_snapshot.name}{admin && o.reseller_snapshot.is_special ? " (Special)" : ""}</p>
        </div>
        {admin && <StatusControl o={o} onDone={refresh} />}
      </div>

      <Summary o={o} />

      {admin && (
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
          <Button variant="outline" className="h-11" onClick={() => setDlg("progress")} data-testid="open-progress-dialog"><Factory /> Update Progress Produksi</Button>
          <Button variant="outline" className="h-11" onClick={() => setDlg("payment")} data-testid="open-payment-dialog"><Banknote /> Input Pembayaran</Button>
          <Button className="h-11 bg-blue-700 text-white hover:bg-blue-800" onClick={() => setDlg("shipment")} data-testid="open-shipment-dialog"><Truck /> Buat Pengiriman</Button>
        </div>
      )}

      {!admin && (
        <div className="grid gap-5 lg:grid-cols-2">
          <Section title={`Item Belum Selesai (${unfinished.length})`} testid="unfinished-items"><ProgressList items={unfinished} /></Section>
          <Section title={`Item Selesai (${finished.length})`} testid="finished-items"><ProgressList items={finished} done /></Section>
        </div>
      )}

      <Section title="Detail Semua Item" testid="all-items-section">
        <ItemsTable items={o.items}
          onAdjust={admin ? (it) => { setItem(it); setDlg("adjust"); } : undefined}
          onResolve={admin ? (it) => { setItem(it); setDlg("resolve"); } : undefined}
          onProgress={admin ? () => setDlg("progress") : undefined} />
      </Section>

      <div className="grid gap-5 lg:grid-cols-2">
        <Section title="Catatan Reseller"><p className="whitespace-pre-wrap text-sm text-slate-700" data-testid="reseller-notes">{o.reseller_notes || "-"}</p></Section>
        {admin && <Section title="Catatan Internal"><InternalNotes o={o} onDone={refresh} /></Section>}
      </div>

      <Section title="Riwayat Pembayaran" testid="payments-section"><PaymentsList payments={payments} orderId={o.id} admin={admin} onChanged={refresh} /></Section>
      <Section title="Riwayat Pengiriman" testid="shipments-section"><ShipmentCards shipments={shipments} /></Section>
      {admin && <Section title="Histori Penyesuaian Harga"><Adjustments list={o.price_adjustments} /></Section>}
      {admin && (
        <Section title="Riwayat Status">
          <ul className="space-y-1 text-sm">{(o.status_history || []).map((h: any, i: number) => (
            <li key={i} className="flex flex-wrap gap-2"><span className="text-slate-500">{fmtDateTime(h.at)}</span><StatusBadge status={h.status} testid={`status-history-${i}`} /><span className="text-slate-600">{h.auto ? "otomatis (semua item terkirim)" : h.by_name}</span></li>
          ))}</ul>
        </Section>
      )}

      {admin && (
        <>
          <PaymentDialog open={dlg === "payment"} onClose={close} order={o} onDone={refresh} />
          <ProgressDialog open={dlg === "progress"} onClose={close} order={o} onDone={refresh} />
          <ShipmentDialog open={dlg === "shipment"} onClose={close} order={o} onDone={refresh} />
          <PriceAdjustDialog open={dlg === "adjust"} onClose={close} order={o} onDone={refresh} item={item} />
          <ResolveCustomDialog open={dlg === "resolve"} onClose={close} order={o} onDone={refresh} item={item} />
        </>
      )}
    </div>
  );
}
