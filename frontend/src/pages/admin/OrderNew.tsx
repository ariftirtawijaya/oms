import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { PackagePlus, Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Field, PageHeader, Section } from "@/components/common";
import { SearchSelect, productOptions } from "@/components/SearchSelect";
import { ResellerType } from "@/pages/admin/Resellers";
import { api, errMsg, errorDetail } from "@/lib/api";
import { newKey, rupiah } from "@/lib/format";

type Line = { key: string; product_id?: string | null; custom_name?: string; qty: string; custom?: boolean };

export default function AdminOrderNew() {
  const nav = useNavigate();
  const qc = useQueryClient();
  const { data: resellers = [] } = useQuery({ queryKey: ["resellers"], queryFn: () => api.get("/resellers").then((r) => r.data) });
  const { data: products = [] } = useQuery({ queryKey: ["products"], queryFn: () => api.get("/products").then((r) => r.data), staleTime: 0 });
  const [rid, setRid] = useState<string | null>(null);
  const [lines, setLines] = useState<Line[]>([{ key: newKey(), qty: "" }]);
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const idem = useRef(newKey());
  const reseller = resellers.find((r: any) => r.id === rid);
  const minQty = reseller?.is_special ? 1 : 10;
  const pmap = Object.fromEntries(products.map((p: any) => [p.id, p]));
  const upd = (k: string, patch: Partial<Line>) => setLines((ls) => ls.map((l) => (l.key === k ? { ...l, ...patch } : l)));
  const sub = (l: Line) => (l.product_id && pmap[l.product_id] ? pmap[l.product_id].price * (parseInt(l.qty || "0", 10)) : 0);
  const total = lines.reduce((a, l) => a + sub(l), 0);

  const submit = async () => {
    if (!rid) return toast.error("Pilih reseller terlebih dahulu.");
    const valid = lines.filter((l) => l.product_id || (l.custom && l.custom_name?.trim()));
    if (!valid.length) return toast.error("Tambahkan minimal satu produk.");
    for (const l of valid) if (parseInt(l.qty || "0", 10) < minQty) return toast.error(`Qty minimal per item untuk reseller ini adalah ${minQty} pcs.`);
    setBusy(true);
    try {
      const { data } = await api.post("/orders", {
        reseller_id: rid, notes, idempotency_key: idem.current,
        items: valid.map((l) => (l.custom ? { custom_name: l.custom_name, qty: parseInt(l.qty, 10) } : { product_id: l.product_id, qty: parseInt(l.qty, 10) })),
      });
      toast.success(`Order ${data.code} dibuat.`);
      qc.invalidateQueries({ queryKey: ["orders"] });
      nav(`/admin/orders/${data.id}`);
    } catch (e) {
      const d = errorDetail(e);
      toast.error(d?.message || errMsg(e));
    } finally { setBusy(false); }
  };

  return (
    <div className="space-y-5">
      <PageHeader title="Buat Order atas Nama Reseller" subtitle="Harga diambil otomatis dari master produk dan disimpan sebagai snapshot." />
      <Section title="1. Pilih Reseller">
        <div className="grid gap-3 sm:grid-cols-[1fr_auto] sm:items-center">
          <SearchSelect testid="admin-order-reseller-select" value={rid} onChange={setRid} placeholder="Cari reseller..."
            options={resellers.map((r: any) => ({ id: r.id, label: r.name, sub: r.wa, search: `${r.name} ${r.wa}` }))} />
          {reseller && <ResellerType special={reseller.is_special} />}
        </div>
      </Section>
      <Section title="2. Produk & Qty" actions={
        <>
          <Button size="sm" variant="outline" onClick={() => setLines((l) => [...l, { key: newKey(), qty: "" }])} data-testid="admin-order-add-line"><Plus /> Produk</Button>
          <Button size="sm" variant="outline" onClick={() => setLines((l) => [...l, { key: newKey(), qty: "", custom: true, custom_name: "" }])} data-testid="admin-order-add-custom"><PackagePlus /> Custom</Button>
        </>}>
        <div className="space-y-3">
          {lines.map((l, i) => {
            const p = l.product_id ? pmap[l.product_id] : null;
            return (
              <div key={l.key} className="grid gap-2 rounded-lg border border-slate-200 p-3 md:grid-cols-[1fr_110px_140px_150px_40px] md:items-end" data-testid={`admin-order-line-${i}`}>
                {l.custom ? (
                  <Field label="Nama Produk Custom"><Input value={l.custom_name} onChange={(e) => upd(l.key, { custom_name: e.target.value })} data-testid={`admin-order-custom-name-${i}`} /></Field>
                ) : (
                  <Field label="Produk"><SearchSelect testid={`admin-order-product-${i}`} value={l.product_id} onChange={(id) => upd(l.key, { product_id: id })}
                    placeholder="Cari produk..." options={productOptions(products)} /></Field>
                )}
                <Field label="Qty"><Input type="number" inputMode="numeric" className="h-11" value={l.qty} onChange={(e) => upd(l.key, { qty: e.target.value })} placeholder={String(minQty)} data-testid={`admin-order-qty-${i}`} /></Field>
                <Field label="Harga"><p className="flex h-11 items-center text-sm tabular-nums">{l.custom ? <span className="text-xs text-orange-700">Ditentukan nanti</span> : p ? rupiah(p.price) : "-"}</p></Field>
                <Field label="Subtotal"><p className="flex h-11 items-center font-semibold tabular-nums" data-testid={`admin-order-subtotal-${i}`}>{l.custom ? "-" : rupiah(sub(l))}</p></Field>
                <Button size="icon" variant="ghost" className="text-red-600" onClick={() => setLines((ls) => ls.filter((x) => x.key !== l.key))} aria-label="Hapus baris" data-testid={`admin-order-remove-${i}`}><Trash2 /></Button>
              </div>
            );
          })}
        </div>
      </Section>
      <Section title="3. Catatan & Simpan">
        <Textarea rows={2} value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Catatan order (opsional)" data-testid="admin-order-notes" />
        <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <p className="font-heading text-xl font-extrabold">Total: <span className="tabular-nums" data-testid="admin-order-total">{rupiah(total)}</span></p>
          <Button onClick={submit} disabled={busy} className="h-11 bg-blue-700 text-white hover:bg-blue-800" data-testid="admin-order-submit">{busy ? "Menyimpan..." : "Simpan Order"}</Button>
        </div>
      </Section>
    </div>
  );
}
