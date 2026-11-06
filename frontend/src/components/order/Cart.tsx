import { useState } from "react";
import { Minus, PackagePlus, Plus, ShoppingCart, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Field } from "@/components/common";
import { CartItem } from "@/lib/cart";
import { productName, rupiah } from "@/lib/format";
import { cn } from "@/lib/utils";

type CartApi = {
  items: CartItem[]; notes: string; total: number; totalQty: number;
  setQty: (k: string, q: number) => void; remove: (k: string) => void; setNotes: (n: string) => void;
};

export function CustomProductDialog({ open, onClose, minQty, onAdd }: { open: boolean; onClose: () => void; minQty: number; onAdd: (n: string, q: number) => void }) {
  const [name, setName] = useState("");
  const [qty, setQty] = useState(String(minQty));
  const submit = () => {
    const q = parseInt(qty || "0", 10);
    if (name.trim().length < 2) return toast.error("Nama produk custom wajib diisi.");
    if (q < minQty) return toast.error(`Qty minimal per item untuk akun anda adalah ${minQty} pcs.`);
    onAdd(name.trim(), q);
    setName(""); setQty(String(minQty)); onClose();
  };
  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-md">
        <DialogHeader><DialogTitle>Tambah Produk Custom</DialogTitle>
          <DialogDescription>Harga produk custom akan ditentukan oleh admin setelah order dibuat.</DialogDescription></DialogHeader>
        <Field label="Nama Produk Custom"><Input value={name} onChange={(e) => setName(e.target.value)} placeholder="contoh: Relay Set Biled Custom Kabel 2m" data-testid="custom-name-input" /></Field>
        <Field label="Qty (pcs)" hint={`Minimal ${minQty} pcs`}><Input type="number" inputMode="numeric" value={qty} onChange={(e) => setQty(e.target.value)} data-testid="custom-qty-input" /></Field>
        <DialogFooter><Button onClick={submit} className="bg-blue-700 text-white hover:bg-blue-800" data-testid="custom-add-button">Tambahkan ke Keranjang</Button></DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export function CartPanel({ cart, minQty, errors, onCustom, onCheckout, busy }: {
  cart: CartApi; minQty: number; errors: Record<string, string>; onCustom: () => void; onCheckout: () => void; busy: boolean;
}) {
  const hasCustom = cart.items.some((i) => i.price === null);
  return (
    <div className="flex h-full flex-col" data-testid="cart-panel">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="flex items-center gap-2 font-heading text-lg font-bold"><ShoppingCart className="h-5 w-5" /> Keranjang</h2>
        <span className="text-xs text-slate-500" data-testid="cart-count">{cart.items.length} item • {cart.totalQty} pcs</span>
      </div>
      <Button variant="outline" className="mb-3 h-10 w-full border-dashed" onClick={onCustom} data-testid="open-custom-product"><PackagePlus /> + Tambah Produk Custom</Button>
      <div className="flex-1 space-y-2 overflow-y-auto">
        {!cart.items.length && <p className="rounded-lg border border-dashed p-6 text-center text-sm text-slate-500" data-testid="cart-empty">Keranjang masih kosong.</p>}
        {cart.items.map((it) => {
          const err = errors[it.key] || (it.qty < minQty ? `Qty minimal per item untuk akun anda adalah ${minQty} pcs.` : "");
          return (
            <div key={it.key} className={cn("rounded-xl border bg-white p-3", err ? "border-red-300 bg-red-50/40" : "border-slate-200")} data-testid={`cart-item-${it.key}`}>
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="text-sm font-semibold leading-snug">{productName(it.name, it.voltage)}</p>
                  <p className="text-xs text-slate-500">{it.price === null ? <span className="font-semibold text-orange-700">Harga Menunggu Penentuan Admin</span> : `${rupiah(it.price)} / pcs`}</p>
                </div>
                <button onClick={() => cart.remove(it.key)} className="rounded-md p-1.5 text-slate-400 hover:bg-red-50 hover:text-red-600" aria-label="Hapus" data-testid={`cart-remove-${it.key}`}><Trash2 className="h-4 w-4" /></button>
              </div>
              <div className="mt-2 flex items-center justify-between gap-2">
                <div className="flex items-center gap-1">
                  <Button size="icon" variant="outline" className="h-9 w-9" onClick={() => cart.setQty(it.key, it.qty - 1)} aria-label="Kurangi" data-testid={`cart-dec-${it.key}`}><Minus /></Button>
                  <Input type="number" inputMode="numeric" value={it.qty} onChange={(e) => cart.setQty(it.key, parseInt(e.target.value || "0", 10))}
                    className="h-9 w-16 text-center tabular-nums" data-testid={`cart-qty-${it.key}`} />
                  <Button size="icon" variant="outline" className="h-9 w-9" onClick={() => cart.setQty(it.key, it.qty + 1)} aria-label="Tambah" data-testid={`cart-inc-${it.key}`}><Plus /></Button>
                </div>
                <p className="text-sm font-bold tabular-nums" data-testid={`cart-subtotal-${it.key}`}>{it.price === null ? "-" : rupiah(it.price * it.qty)}</p>
              </div>
              {err && <p className="mt-2 text-xs font-medium text-red-600" data-testid={`cart-error-${it.key}`}>{err}</p>}
            </div>
          );
        })}
      </div>
      <div className="mt-3 space-y-3 border-t border-slate-200 pt-3">
        <Textarea rows={2} value={cart.notes} onChange={(e) => cart.setNotes(e.target.value)} placeholder="Catatan untuk admin (opsional)" data-testid="cart-notes-input" />
        <div className="flex items-end justify-between">
          <div><p className="text-xs text-slate-500">Total Tagihan Sementara</p>
            {hasCustom && <p className="text-[11px] text-orange-700">Belum termasuk produk custom</p>}</div>
          <p className="font-heading text-xl font-extrabold tabular-nums" data-testid="cart-total">{rupiah(cart.total)}</p>
        </div>
        <Button onClick={onCheckout} disabled={!cart.items.length || busy} className="h-12 w-full bg-blue-700 text-base text-white hover:bg-blue-800" data-testid="cart-checkout-button">
          {busy ? "Memproses..." : "Buat Order"}
        </Button>
      </div>
    </div>
  );
}
