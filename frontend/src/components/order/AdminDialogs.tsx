import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Field } from "@/components/common";
import { SearchSelect, productOptions } from "@/components/SearchSelect";
import { api, errMsg } from "@/lib/api";
import { jktNowLocalInput, newKey, productName, rupiah } from "@/lib/format";

type Base = { open: boolean; onClose: () => void; order: any; onDone: () => void };

function useSubmit(onDone: () => void, onClose: () => void) {
  const [busy, setBusy] = useState(false);
  const run = async (fn: () => Promise<any>, ok: string) => {
    if (busy) return;
    setBusy(true);
    try { await fn(); toast.success(ok); onDone(); onClose(); }
    catch (e) { toast.error(errMsg(e)); }
    finally { setBusy(false); }
  };
  return { busy, run };
}

export function PaymentDialog({ open, onClose, order, onDone }: Base) {
  const [amount, setAmount] = useState("");
  const [paidAt, setPaidAt] = useState(jktNowLocalInput());
  const [notes, setNotes] = useState("");
  const key = useRef(newKey());
  const { busy, run } = useSubmit(onDone, onClose);
  useEffect(() => { if (open) { key.current = newKey(); setAmount(""); setNotes(""); setPaidAt(jktNowLocalInput()); } }, [open]);
  const n = parseInt(amount.replace(/\D/g, "") || "0", 10);
  const submit = () => {
    if (n <= 0) return toast.error("Nominal pembayaran harus lebih dari 0.");
    run(() => api.post(`/orders/${order.id}/payments`, { amount: n, paid_at: paidAt, notes, idempotency_key: key.current }), "Pembayaran dicatat.");
  };
  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-md">
        <DialogHeader><DialogTitle>Input Pembayaran</DialogTitle>
          <DialogDescription>Sisa tagihan saat ini: <b>{rupiah(Math.max(order.remaining, 0))}</b></DialogDescription></DialogHeader>
        <Field label="Nominal (Rp)" hint={n ? rupiah(n) : undefined}>
          <Input inputMode="numeric" value={amount} onChange={(e) => setAmount(e.target.value.replace(/\D/g, ""))} placeholder="contoh: 2000000" data-testid="payment-amount-input" />
        </Field>
        <Field label="Tanggal & Jam Pembayaran (WIB)"><Input type="datetime-local" value={paidAt} onChange={(e) => setPaidAt(e.target.value)} data-testid="payment-date-input" /></Field>
        <Field label="Catatan"><Input value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="contoh: DP pertama via transfer BCA" data-testid="payment-notes-input" /></Field>
        {n > order.remaining && order.remaining >= 0 && n > 0 && <p className="rounded-lg bg-violet-50 p-3 text-xs text-violet-800">Nominal melebihi sisa tagihan. Kelebihan {rupiah(n - order.remaining)} akan tercatat sebagai kelebihan bayar.</p>}
        <DialogFooter><Button onClick={submit} disabled={busy} className="bg-blue-700 text-white hover:bg-blue-800" data-testid="payment-save-button">{busy ? "Menyimpan..." : "Simpan Pembayaran"}</Button></DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export function ProgressDialog({ open, onClose, order, onDone }: Base) {
  const [vals, setVals] = useState<Record<string, string>>({});
  const { busy, run } = useSubmit(onDone, onClose);
  useEffect(() => { if (open) setVals(Object.fromEntries(order.items.map((i: any) => [i.item_id, String(i.qty_done)]))); }, [open, order]);
  const submit = () => {
    for (const it of order.items) {
      const v = parseInt(vals[it.item_id] || "0", 10);
      if (v > it.qty_order) return toast.error(`Qty selesai ${it.product_name_snapshot} tidak boleh melebihi ${it.qty_order}.`);
      if (v < it.qty_shipped) return toast.error(`Qty selesai ${it.product_name_snapshot} tidak boleh kurang dari qty terkirim (${it.qty_shipped}).`);
    }
    run(() => api.put(`/orders/${order.id}/progress`, { items: order.items.map((i: any) => ({ item_id: i.item_id, qty_done: parseInt(vals[i.item_id] || "0", 10) })) }), "Progress produksi diperbarui.");
  };
  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-h-[90vh] max-w-lg overflow-y-auto">
        <DialogHeader><DialogTitle>Update Progress Produksi</DialogTitle></DialogHeader>
        <div className="space-y-3">
          {order.items.map((it: any) => (
            <div key={it.item_id} className="flex items-center justify-between gap-3 rounded-lg border p-3">
              <div className="min-w-0"><p className="text-sm font-medium">{productName(it.product_name_snapshot, it.voltage_snapshot)}</p>
                <p className="text-xs text-slate-500">Pesan {it.qty_order} • Dikirim {it.qty_shipped}</p></div>
              <Input type="number" min={it.qty_shipped} max={it.qty_order} className="w-24 text-right" value={vals[it.item_id] ?? ""}
                onChange={(e) => setVals((s) => ({ ...s, [it.item_id]: e.target.value }))} data-testid={`progress-input-${it.item_id}`} />
            </div>
          ))}
        </div>
        <DialogFooter><Button onClick={submit} disabled={busy} className="bg-blue-700 text-white hover:bg-blue-800" data-testid="progress-save-button">Simpan Progress</Button></DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export function ShipmentDialog({ open, onClose, order, onDone }: Base) {
  const [f, setF] = useState({ courier: "", tracking_no: "", shipped_at: jktNowLocalInput(), notes: "" });
  const [qty, setQty] = useState<Record<string, string>>({});
  const [photo, setPhoto] = useState<File | null>(null);
  const key = useRef(newKey());
  const { busy, run } = useSubmit(onDone, onClose);
  useEffect(() => { if (open) { key.current = newKey(); setQty({}); setPhoto(null); setF({ courier: "", tracking_no: "", shipped_at: jktNowLocalInput(), notes: "" }); } }, [open]);
  const pending = order.items.filter((i: any) => i.qty_remaining_ship > 0);
  const submit = () => {
    if (f.courier.trim().length < 2 || f.tracking_no.trim().length < 2) return toast.error("Ekspedisi dan nomor resi wajib diisi.");
    const items = pending.map((i: any) => ({ item_id: i.item_id, qty: parseInt(qty[i.item_id] || "0", 10) })).filter((i: any) => i.qty > 0);
    if (!items.length) return toast.error("Isi minimal satu qty produk yang dikirim.");
    for (const i of items) {
      const it = pending.find((x: any) => x.item_id === i.item_id);
      if (i.qty > it.qty_remaining_ship) return toast.error(`Qty kirim ${it.product_name_snapshot} melebihi sisa kirim (${it.qty_remaining_ship}).`);
    }
    if (photo && photo.size > 5 * 1024 * 1024) return toast.error("Ukuran foto resi maksimal 5 MB.");
    const fd = new FormData();
    Object.entries(f).forEach(([k, v]) => fd.append(k, v));
    fd.append("items", JSON.stringify(items));
    fd.append("idempotency_key", key.current);
    if (photo) fd.append("photo", photo);
    run(() => api.post(`/orders/${order.id}/shipments`, fd), "Pengiriman disimpan.");
  };
  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-h-[92vh] max-w-lg overflow-y-auto">
        <DialogHeader><DialogTitle>Buat Pengiriman</DialogTitle></DialogHeader>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Ekspedisi"><Input value={f.courier} onChange={(e) => setF({ ...f, courier: e.target.value })} placeholder="POS / JNE / J&T" data-testid="shipment-courier-input" /></Field>
          <Field label="Nomor Resi"><Input value={f.tracking_no} onChange={(e) => setF({ ...f, tracking_no: e.target.value })} data-testid="shipment-tracking-input" /></Field>
        </div>
        <Field label="Tanggal & Jam (WIB)"><Input type="datetime-local" value={f.shipped_at} onChange={(e) => setF({ ...f, shipped_at: e.target.value })} data-testid="shipment-date-input" /></Field>
        <Field label="Foto Resi (opsional)" hint="JPG, JPEG, PNG, atau WebP. Maks 5 MB.">
          <Input type="file" accept=".jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp" onChange={(e) => setPhoto(e.target.files?.[0] || null)} data-testid="shipment-photo-input" />
        </Field>
        <Field label="Catatan"><Textarea rows={2} value={f.notes} onChange={(e) => setF({ ...f, notes: e.target.value })} data-testid="shipment-notes-input" /></Field>
        <div className="space-y-2">
          <p className="text-sm font-semibold">Qty Kirim per Produk</p>
          {!pending.length && <p className="text-sm text-slate-500">Semua item sudah terkirim.</p>}
          {pending.map((it: any) => (
            <div key={it.item_id} className="flex items-center justify-between gap-3 rounded-lg border p-3">
              <div className="min-w-0"><p className="text-sm font-medium">{productName(it.product_name_snapshot, it.voltage_snapshot)}</p>
                <p className="text-xs text-slate-500">Sisa kirim {it.qty_remaining_ship} pcs • Selesai produksi {it.qty_done}</p></div>
              <div className="flex items-center gap-1">
                <Input type="number" min={0} max={it.qty_remaining_ship} className="w-20 text-right" value={qty[it.item_id] ?? ""}
                  onChange={(e) => setQty((s) => ({ ...s, [it.item_id]: e.target.value }))} data-testid={`shipment-qty-${it.item_id}`} />
                <Button type="button" size="sm" variant="ghost" onClick={() => setQty((s) => ({ ...s, [it.item_id]: String(it.qty_remaining_ship) }))} data-testid={`shipment-max-${it.item_id}`}>Semua</Button>
              </div>
            </div>
          ))}
        </div>
        <DialogFooter><Button onClick={submit} disabled={busy || !pending.length} className="bg-blue-700 text-white hover:bg-blue-800" data-testid="shipment-save-button">{busy ? "Menyimpan..." : "Simpan Pengiriman"}</Button></DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export function PriceAdjustDialog({ open, onClose, order, onDone, item }: Base & { item: any }) {
  const [price, setPrice] = useState("");
  const [reason, setReason] = useState("");
  const { busy, run } = useSubmit(onDone, onClose);
  useEffect(() => { if (open && item) { setPrice(String(item.unit_price_snapshot ?? "")); setReason(""); } }, [open, item]);
  if (!item) return null;
  const n = parseInt(price || "0", 10);
  const submit = () => {
    if (reason.trim().length < 3) return toast.error("Alasan perubahan wajib diisi.");
    run(() => api.post(`/orders/${order.id}/price-adjustments`, { item_id: item.item_id, new_price: n, reason }), "Harga transaksi disesuaikan.");
  };
  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-md">
        <DialogHeader><DialogTitle>Penyesuaian Harga Order</DialogTitle>
          <DialogDescription>Hanya mengubah harga transaksi pada order {order.code}. Harga master produk dan order lain tidak berubah.</DialogDescription></DialogHeader>
        <p className="text-sm font-medium">{productName(item.product_name_snapshot, item.voltage_snapshot)} — {item.qty_order} pcs</p>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Harga Sebelumnya"><Input value={rupiah(item.unit_price_snapshot)} disabled /></Field>
          <Field label="Harga Baru (Rp)"><Input inputMode="numeric" value={price} onChange={(e) => setPrice(e.target.value.replace(/\D/g, ""))} data-testid="adjust-new-price-input" /></Field>
        </div>
        <p className="text-sm text-slate-600">Subtotal baru: <b className="tabular-nums">{rupiah(n * item.qty_order)}</b></p>
        <Field label="Alasan Perubahan"><Textarea rows={2} value={reason} onChange={(e) => setReason(e.target.value)} data-testid="adjust-reason-input" /></Field>
        <DialogFooter><Button onClick={submit} disabled={busy} className="bg-blue-700 text-white hover:bg-blue-800" data-testid="adjust-save-button">Simpan Penyesuaian</Button></DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export function ResolveCustomDialog({ open, onClose, order, onDone, item }: Base & { item: any }) {
  const { data: products = [] } = useQuery({ queryKey: ["products"], queryFn: () => api.get("/products").then((r) => r.data), enabled: open });
  const [pid, setPid] = useState<string | null>(null);
  const [price, setPrice] = useState("");
  const { busy, run } = useSubmit(onDone, onClose);
  useEffect(() => { if (open) { setPid(null); setPrice(""); } }, [open]);
  if (!item) return null;
  const onPick = (id: string) => { setPid(id); const p = products.find((x: any) => x.id === id); if (p) setPrice(String(p.price)); };
  const submit = () => {
    if (price === "") return toast.error("Harga transaksi wajib diisi.");
    run(() => api.post(`/orders/${order.id}/custom-items/resolve`, { item_id: item.item_id, product_id: pid, unit_price: parseInt(price, 10) }), "Harga produk custom ditetapkan.");
  };
  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-md">
        <DialogHeader><DialogTitle>Tetapkan Harga Produk Custom</DialogTitle>
          <DialogDescription>Item custom: <b>{item.custom_name}</b> ({item.qty_order} pcs)</DialogDescription></DialogHeader>
        <Field label="Mapping ke Produk Resmi (opsional)" hint="Kosongkan bila tetap sebagai produk custom.">
          <SearchSelect options={productOptions(products)} value={pid} onChange={onPick} placeholder="Pilih produk resmi" testid="resolve-product-select" />
        </Field>
        <Field label="Harga Transaksi per pcs (Rp)"><Input inputMode="numeric" value={price} onChange={(e) => setPrice(e.target.value.replace(/\D/g, ""))} data-testid="resolve-price-input" /></Field>
        {price !== "" && <p className="text-sm text-slate-600">Subtotal: <b>{rupiah(parseInt(price, 10) * item.qty_order)}</b></p>}
        <DialogFooter><Button onClick={submit} disabled={busy} className="bg-blue-700 text-white hover:bg-blue-800" data-testid="resolve-save-button">Simpan Harga</Button></DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
