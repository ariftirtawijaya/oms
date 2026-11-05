import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ColumnDef } from "@tanstack/react-table";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import { History, Pencil, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { DataTable, MobileRow } from "@/components/DataTable";
import { Field, Loading, PageHeader } from "@/components/common";
import { api, errMsg } from "@/lib/api";
import { fmtDateTime, productName, rupiah, voltageLabel } from "@/lib/format";

const schema = z.object({
  code: z.string().trim().min(1, "Kode produk wajib diisi."),
  name: z.string().trim().min(2, "Nama produk wajib diisi."),
  voltage: z.string().trim().min(1, "Isi voltase, atau '-' bila tidak ada."),
  price: z.coerce.number({ invalid_type_error: "Harga harus angka." }).int("Harga harus bilangan bulat.").min(0, "Harga tidak boleh negatif."),
  is_active: z.boolean(),
  notes: z.string().optional(),
});
type FormV = z.infer<typeof schema>;

function ProductForm({ product, onDone }: { product?: any; onDone: () => void }) {
  const { register, handleSubmit, setValue, watch, formState: { errors, isSubmitting } } = useForm<FormV>({
    resolver: zodResolver(schema),
    defaultValues: product ? { ...product, notes: product.notes || "" } : { code: "", name: "", voltage: "12", price: 0, is_active: true, notes: "" },
  });
  const submit = async (v: FormV) => {
    try {
      if (product) await api.put(`/products/${product.id}`, v);
      else await api.post("/products", v);
      toast.success(product ? "Produk diperbarui. Harga baru hanya berlaku untuk order baru." : "Produk ditambahkan.");
      onDone();
    } catch (e) {
      toast.error(errMsg(e));
    }
  };
  return (
    <form onSubmit={handleSubmit(submit)} className="space-y-4" data-testid="product-form">
      <div className="grid grid-cols-2 gap-3">
        <Field label="Kode Produk" error={errors.code?.message}><Input {...register("code")} data-testid="product-code-input" /></Field>
        <Field label="Voltase" error={errors.voltage?.message} hint="Contoh: 12, 24, atau -"><Input {...register("voltage")} data-testid="product-voltage-input" /></Field>
      </div>
      <Field label="Nama Produk" error={errors.name?.message}><Input {...register("name")} data-testid="product-name-input" /></Field>
      <Field label="Harga (Rp)" error={errors.price?.message}><Input type="number" inputMode="numeric" {...register("price")} data-testid="product-price-input" /></Field>
      <Field label="Catatan"><Textarea rows={2} {...register("notes")} data-testid="product-notes-input" /></Field>
      <label className="flex items-center gap-3 text-sm">
        <Switch checked={watch("is_active")} onCheckedChange={(c) => setValue("is_active", c)} data-testid="product-active-switch" /> Produk aktif
      </label>
      {product && <p className="rounded-lg bg-blue-50 p-3 text-xs text-blue-800">Perubahan harga hanya berlaku untuk order baru. Order yang sudah dibuat tetap memakai harga snapshot saat order dibuat.</p>}
      <DialogFooter>
        <Button type="submit" disabled={isSubmitting} className="bg-blue-700 text-white hover:bg-blue-800" data-testid="product-save-button">
          {isSubmitting ? "Menyimpan..." : "Simpan"}
        </Button>
      </DialogFooter>
    </form>
  );
}

function PriceHistory({ product }: { product: any }) {
  const hist = [...(product.price_history || [])].reverse();
  if (!hist.length) return <p className="text-sm text-slate-500">Belum ada perubahan harga.</p>;
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm" data-testid="price-history-table">
        <thead className="text-left text-xs uppercase text-slate-500"><tr><th className="py-2">Tanggal</th><th className="text-right">Harga Lama</th><th className="text-right">Harga Baru</th><th className="pl-3">Admin</th></tr></thead>
        <tbody className="divide-y">
          {hist.map((h: any, i: number) => (
            <tr key={i}><td className="py-2">{fmtDateTime(h.changed_at)}</td><td className="text-right tabular-nums">{rupiah(h.old_price)}</td>
              <td className="text-right font-semibold tabular-nums">{rupiah(h.new_price)}</td><td className="pl-3">{h.admin_name}</td></tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function ProductsPage() {
  const qc = useQueryClient();
  const { data = [], isLoading } = useQuery({ queryKey: ["products"], queryFn: () => api.get("/products").then((r) => r.data) });
  const [edit, setEdit] = useState<any>(null);
  const [hist, setHist] = useState<any>(null);
  const done = () => { setEdit(null); qc.invalidateQueries({ queryKey: ["products"] }); };

  const columns: ColumnDef<any, any>[] = [
    { accessorKey: "code", header: "Kode", cell: (c) => <span className="font-mono text-xs font-semibold">{c.getValue()}</span> },
    { accessorKey: "name", header: "Nama Produk", cell: (c) => <span className="font-medium">{c.getValue()}</span> },
    { accessorKey: "voltage", header: "Voltase", cell: (c) => voltageLabel(c.getValue()) || "-" },
    { accessorKey: "price", header: "Harga", cell: (c) => <span className="tabular-nums">{rupiah(c.getValue())}</span> },
    { accessorKey: "is_active", header: "Status", cell: (c) => c.getValue() ? <Badge className="bg-emerald-100 text-emerald-800 hover:bg-emerald-100">Aktif</Badge> : <Badge variant="secondary">Nonaktif</Badge> },
    { id: "aksi", header: "", enableSorting: false, cell: ({ row }) => <Actions p={row.original} /> },
  ];
  const Actions = ({ p }: { p: any }) => (
    <div className="flex justify-end gap-1">
      <Button size="sm" variant="ghost" onClick={() => setHist(p)} data-testid={`product-history-${p.code}`}><History /> Riwayat</Button>
      <Button size="sm" variant="outline" onClick={() => setEdit(p)} data-testid={`product-edit-${p.code}`}><Pencil /> Ubah</Button>
    </div>
  );

  return (
    <div>
      <PageHeader title="Master Produk" subtitle="Kelola produk, harga, voltase, dan status aktif."
        actions={<Button onClick={() => setEdit({})} className="bg-blue-700 text-white hover:bg-blue-800" data-testid="add-product-button"><Plus /> Tambah Produk</Button>} />
      {isLoading ? <Loading /> : (
        <DataTable testid="products-table" data={data} columns={columns} searchPlaceholder="Cari kode, nama, voltase..."
          searchText={(p: any) => `${p.code} ${productName(p.name, p.voltage)} ${p.voltage}`}
          mobileCard={(p: any) => (
            <div>
              <div className="flex items-start justify-between gap-2">
                <div><p className="font-semibold">{productName(p.name, p.voltage)}</p><p className="font-mono text-xs text-slate-500">{p.code}</p></div>
                {p.is_active ? <Badge className="bg-emerald-100 text-emerald-800">Aktif</Badge> : <Badge variant="secondary">Nonaktif</Badge>}
              </div>
              <MobileRow label="Harga">{rupiah(p.price)}</MobileRow>
              <div className="mt-2"><Actions p={p} /></div>
            </div>
          )} />
      )}
      <Dialog open={!!edit} onOpenChange={(o) => !o && setEdit(null)}>
        <DialogContent className="max-w-lg">
          <DialogHeader><DialogTitle>{edit?.id ? "Ubah Produk" : "Tambah Produk"}</DialogTitle></DialogHeader>
          {edit && <ProductForm product={edit.id ? edit : undefined} onDone={done} />}
        </DialogContent>
      </Dialog>
      <Dialog open={!!hist} onOpenChange={(o) => !o && setHist(null)}>
        <DialogContent className="max-w-lg">
          <DialogHeader><DialogTitle>Riwayat Harga — {hist && productName(hist.name, hist.voltage)}</DialogTitle></DialogHeader>
          {hist && <PriceHistory product={hist} />}
        </DialogContent>
      </Dialog>
    </div>
  );
}
