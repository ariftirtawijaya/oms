import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { AlertTriangle, ShoppingCart } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetTitle } from "@/components/ui/sheet";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Loading, PageHeader } from "@/components/common";
import { Catalog } from "@/components/order/Catalog";
import { CartPanel, CustomProductDialog } from "@/components/order/Cart";
import { api, errMsg, errorDetail } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useCart } from "@/lib/cart";
import { productName, rupiah } from "@/lib/format";

export default function OrderCreatePage() {
  const { user } = useAuth();
  const nav = useNavigate();
  const qc = useQueryClient();
  const uid = user ? user.id : "anon";
  const cart = useCart(`relaylab_cart_${uid}`);
  const { data: products = [], isLoading, refetch } = useQuery({ queryKey: ["catalog"], queryFn: () => api.get("/products").then((r) => r.data), staleTime: 0, refetchOnWindowFocus: true });
  const { data: profile } = useQuery({ queryKey: ["profile"], queryFn: () => api.get("/me/profile").then((r) => r.data), staleTime: 0 });
  const minQty = profile?.min_qty ?? 10;
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [custom, setCustom] = useState(false);
  const [sheet, setSheet] = useState(false);
  const [confirm, setConfirm] = useState(false);
  const [busy, setBusy] = useState(false);

  const inCart = useMemo(() => Object.fromEntries(cart.items.filter((i) => i.product_id).map((i) => [i.product_id, i.qty])), [cart.items]);
  const priceChanges = useMemo(() => {
    const map = Object.fromEntries(products.map((p: any) => [p.id, p]));
    return cart.items.filter((i) => i.product_id && map[i.product_id] && map[i.product_id].price !== i.price)
      .map((i) => ({ key: i.key, product_id: i.product_id, name: productName(i.name, i.voltage), old_price: i.price, new_price: map[i.product_id!].price }));
  }, [products, cart.items]);

  const validate = (fresh: any[]) => {
    const errs: Record<string, string> = {};
    const ids = new Set(fresh.map((p: any) => p.id));
    cart.items.forEach((i) => { if (i.qty < minQty) errs[i.key] = `Qty minimal per item untuk akun Anda adalah ${minQty} pcs.`; });
    cart.items.forEach((i) => { if (i.product_id && !ids.has(i.product_id)) errs[i.key] = "Produk sudah tidak tersedia. Hapus dari keranjang."; });
    setErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const checkout = async () => {
    const res = await refetch();
    if (!validate(res.data || products)) {
      toast.error(`Qty minimal per item untuk akun Anda adalah ${minQty} pcs. Perbaiki item yang ditandai merah.`);
      return;
    }
    setSheet(false);
    setConfirm(true);
  };

  const applyPrices = () => cart.updatePrices(Object.fromEntries(priceChanges.map((c) => [c.product_id, c.new_price])));

  const submit = async () => {
    if (busy) return;
    setBusy(true);
    try {
      const body = {
        items: cart.items.map((i) => i.product_id ? { product_id: i.product_id, qty: i.qty, expected_price: i.price } : { custom_name: i.custom_name, qty: i.qty }),
        notes: cart.notes, idempotency_key: cart.idem,
      };
      const { data } = await api.post("/orders", body);
      toast.success(`Order ${data.code} berhasil dibuat.`);
      cart.clear();
      qc.invalidateQueries({ queryKey: ["orders"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
      nav(`/app/orders/${data.id}`);
    } catch (e) {
      const d = errorDetail(e);
      if (d?.code === "PRICE_CHANGED") {
        await refetch();
        toast.warning(d.message);
      } else if (d?.code === "VALIDATION") {
        const errs: Record<string, string> = {};
        (d.errors || []).forEach((er: any) => {
          const it = cart.items.find((i) => (er.product_id && i.product_id === er.product_id) || (er.custom_name && i.custom_name === er.custom_name)) || cart.items[er.index];
          if (it) errs[it.key] = er.message;
        });
        setErrors(errs);
        setConfirm(false);
        toast.error(d.message);
      } else {
        toast.error(errMsg(e));
      }
    } finally {
      setBusy(false);
    }
  };

  const panel = <CartPanel cart={cart} minQty={minQty} errors={errors} busy={busy} onCustom={() => setCustom(true)} onCheckout={checkout} />;

  return (
    <div className="pb-24 lg:pb-0">
      <PageHeader title="Buat Order" subtitle={`Minimum order untuk akun Anda: ${minQty} pcs per item.`} />
      {priceChanges.length > 0 && (
        <div className="mb-4 rounded-xl border border-amber-300 bg-amber-50 p-4 text-sm text-amber-900" data-testid="price-change-alert">
          <p className="flex items-center gap-2 font-semibold"><AlertTriangle className="h-4 w-4" /> Harga beberapa produk di keranjang telah berubah</p>
          <ul className="mt-2 space-y-1">{priceChanges.map((c) => <li key={c.key}>{c.name}: {rupiah(c.old_price)} → <b>{rupiah(c.new_price)}</b></li>)}</ul>
          <Button size="sm" className="mt-3 bg-amber-600 text-white hover:bg-amber-700" onClick={applyPrices} data-testid="apply-new-prices">Gunakan Harga Terbaru</Button>
        </div>
      )}
      <div className="grid gap-6 lg:grid-cols-[1fr_360px]">
        {isLoading || !profile ? <Loading /> : <Catalog products={products} inCart={inCart} onAdd={(p) => { cart.addProduct(p, minQty); toast.success(`${productName(p.name, p.voltage)} ditambahkan.`); }} />}
        <aside className="hidden lg:block">
          <div className="sticky top-6 max-h-[calc(100vh-3rem)] rounded-xl border border-slate-200 bg-slate-50/60 p-4">{panel}</div>
        </aside>
      </div>

      <div className="fixed inset-x-0 bottom-0 z-30 border-t border-slate-200 bg-white/80 p-3 backdrop-blur-xl lg:hidden">
        <Button onClick={() => setSheet(true)} className="h-12 w-full justify-between bg-blue-700 text-white hover:bg-blue-800" data-testid="mobile-cart-button">
          <span className="flex items-center gap-2"><ShoppingCart /> Keranjang ({cart.items.length})</span>
          <span className="tabular-nums">{rupiah(cart.total)}</span>
        </Button>
      </div>
      <Sheet open={sheet} onOpenChange={setSheet}>
        <SheetContent side="bottom" className="h-[88vh] rounded-t-2xl p-4 pt-10">
          <SheetTitle className="sr-only">Keranjang</SheetTitle>{panel}
        </SheetContent>
      </Sheet>

      <CustomProductDialog open={custom} onClose={() => setCustom(false)} minQty={minQty} onAdd={(n, q) => { cart.addCustom(n, q); toast.success("Produk custom ditambahkan."); }} />

      <Dialog open={confirm} onOpenChange={(o) => !o && !busy && setConfirm(false)}>
        <DialogContent className="max-h-[90vh] max-w-lg overflow-y-auto">
          <DialogHeader><DialogTitle>Konfirmasi Order</DialogTitle>
            <DialogDescription>Periksa kembali item dan harga sebelum order dikirim.</DialogDescription></DialogHeader>
          {priceChanges.length > 0 && (
            <div className="rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900" data-testid="confirm-price-change">
              <p className="font-semibold">Harga berubah sejak ditambahkan ke keranjang:</p>
              <ul className="mt-1">{priceChanges.map((c) => <li key={c.key}>{c.name}: {rupiah(c.old_price)} → <b>{rupiah(c.new_price)}</b></li>)}</ul>
              <Button size="sm" className="mt-2 bg-amber-600 text-white hover:bg-amber-700" onClick={applyPrices} data-testid="confirm-apply-prices">Setujui Harga Terbaru</Button>
            </div>
          )}
          <ul className="divide-y text-sm">
            {cart.items.map((i) => (
              <li key={i.key} className="flex justify-between gap-3 py-2">
                <span>{productName(i.name, i.voltage)} <span className="text-slate-500">× {i.qty}</span></span>
                <span className="shrink-0 font-semibold tabular-nums">{i.price === null ? "Menunggu harga" : rupiah(i.price * i.qty)}</span>
              </li>
            ))}
          </ul>
          <div className="flex justify-between border-t pt-3 font-heading text-lg font-extrabold"><span>Total</span><span className="tabular-nums" data-testid="confirm-total">{rupiah(cart.total)}</span></div>
          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={() => setConfirm(false)} disabled={busy} data-testid="confirm-back-button">Kembali</Button>
            <Button onClick={submit} disabled={busy || priceChanges.length > 0} className="bg-blue-700 text-white hover:bg-blue-800" data-testid="confirm-order-button">
              {busy ? "Mengirim..." : "Kirim Order"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
