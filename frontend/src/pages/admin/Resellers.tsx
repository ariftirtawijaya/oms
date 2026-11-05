import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ColumnDef } from "@tanstack/react-table";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import { Pencil, Plus, Star } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { DataTable, MobileRow } from "@/components/DataTable";
import { Field, Loading, PageHeader } from "@/components/common";
import { api, errMsg } from "@/lib/api";
import { rupiah } from "@/lib/format";

const schema = z.object({
  name: z.string().trim().min(2, "Nama reseller wajib diisi."),
  wa: z.string().trim().regex(/^[0-9+\-\s]{8,20}$/, "Nomor WhatsApp tidak valid."),
  address: z.string().optional(),
  is_special: z.boolean(),
  notes: z.string().optional(),
  login_email: z.string().email("Format email tidak valid.").optional().or(z.literal("")),
  login_password: z.string().min(8, "Password minimal 8 karakter.").optional().or(z.literal("")),
});
type FormV = z.infer<typeof schema>;

export const ResellerType = ({ special }: { special: boolean }) => special
  ? <Badge className="gap-1 bg-violet-100 text-violet-800 hover:bg-violet-100" data-testid="reseller-type-special"><Star className="h-3 w-3" /> Special (min 1 pcs)</Badge>
  : <Badge variant="secondary" data-testid="reseller-type-regular">Biasa (min 10 pcs)</Badge>;

function ResellerForm({ reseller, onDone }: { reseller?: any; onDone: () => void }) {
  const { register, handleSubmit, setValue, watch, formState: { errors, isSubmitting } } = useForm<FormV>({
    resolver: zodResolver(schema),
    defaultValues: reseller ? { name: reseller.name, wa: reseller.wa, address: reseller.address || "", is_special: !!reseller.is_special, notes: reseller.notes || "", login_email: "", login_password: "" }
      : { name: "", wa: "", address: "", is_special: false, notes: "", login_email: "", login_password: "" },
  });
  const submit = async (v: FormV) => {
    const body: any = { ...v, login_email: v.login_email || null, login_password: v.login_password || null };
    try {
      if (reseller) await api.put(`/resellers/${reseller.id}`, { ...body, login_email: null, login_password: null });
      else await api.post("/resellers", body);
      toast.success(reseller ? "Data reseller diperbarui." : "Reseller ditambahkan.");
      onDone();
    } catch (e) {
      toast.error(errMsg(e));
    }
  };
  return (
    <form onSubmit={handleSubmit(submit)} className="space-y-4" data-testid="reseller-form">
      <Field label="Nama Reseller" error={errors.name?.message}><Input {...register("name")} data-testid="reseller-name-input" /></Field>
      <Field label="Nomor WhatsApp" error={errors.wa?.message} hint="Contoh: 081234567890. Dipakai untuk notifikasi dan /cekorder.">
        <Input inputMode="tel" {...register("wa")} data-testid="reseller-wa-input" />
      </Field>
      <Field label="Alamat"><Textarea rows={2} {...register("address")} data-testid="reseller-address-input" /></Field>
      <label className="flex items-center gap-3 rounded-lg border border-violet-200 bg-violet-50 p-3 text-sm">
        <Switch checked={watch("is_special")} onCheckedChange={(c) => setValue("is_special", c)} data-testid="reseller-special-switch" />
        <span><b>Special Reseller</b> — minimum order 1 pcs per item (reseller biasa 10 pcs). Tidak memengaruhi order lama.</span>
      </label>
      <Field label="Catatan"><Textarea rows={2} {...register("notes")} data-testid="reseller-notes-input" /></Field>
      {!reseller && (
        <div className="space-y-3 rounded-lg border border-slate-200 p-3">
          <p className="text-sm font-semibold">Akun Login (opsional)</p>
          <Field label="Email Login" error={errors.login_email?.message}><Input type="email" {...register("login_email")} data-testid="reseller-login-email-input" /></Field>
          <Field label="Password Awal" error={errors.login_password?.message} hint="Reseller wajib mengganti password saat login pertama.">
            <Input type="text" {...register("login_password")} data-testid="reseller-login-password-input" />
          </Field>
        </div>
      )}
      <DialogFooter>
        <Button type="submit" disabled={isSubmitting} className="bg-blue-700 text-white hover:bg-blue-800" data-testid="reseller-save-button">{isSubmitting ? "Menyimpan..." : "Simpan"}</Button>
      </DialogFooter>
    </form>
  );
}

export default function ResellersPage() {
  const qc = useQueryClient();
  const { data = [], isLoading } = useQuery({ queryKey: ["resellers"], queryFn: () => api.get("/resellers").then((r) => r.data) });
  const [edit, setEdit] = useState<any>(null);
  const done = () => { setEdit(null); qc.invalidateQueries({ queryKey: ["resellers"] }); qc.invalidateQueries({ queryKey: ["users"] }); };
  const outstanding = (r: any) => Math.max(r.total_order - r.total_paid, 0);

  const columns: ColumnDef<any>[] = [
    { accessorKey: "name", header: "Nama", cell: (c) => <span className="font-semibold">{c.getValue()}</span> },
    { accessorKey: "wa", header: "WhatsApp" },
    { accessorKey: "is_special", header: "Jenis", cell: (c) => <ResellerType special={c.getValue()} /> },
    { id: "login", header: "Akun Login", cell: ({ row }) => row.original.users.map((u: any) => u.email).join(", ") || <span className="text-slate-400">Belum ada</span> },
    { accessorKey: "order_count", header: "Order" },
    { id: "piutang", header: "Sisa Tagihan", accessorFn: outstanding, cell: (c) => <span className="tabular-nums">{rupiah(c.getValue())}</span> },
    { id: "aksi", header: "", enableSorting: false, cell: ({ row }) => (
      <Button size="sm" variant="outline" onClick={() => setEdit(row.original)} data-testid={`reseller-edit-${row.index}`}><Pencil /> Ubah</Button>) },
  ];

  return (
    <div>
      <PageHeader title="Manajemen Reseller" subtitle="Data reseller, jenis reseller, dan akun login terkait."
        actions={<Button onClick={() => setEdit({})} className="bg-blue-700 text-white hover:bg-blue-800" data-testid="add-reseller-button"><Plus /> Tambah Reseller</Button>} />
      {isLoading ? <Loading /> : (
        <DataTable testid="resellers-table" data={data} columns={columns} searchPlaceholder="Cari nama atau nomor WA..."
          searchText={(r: any) => `${r.name} ${r.wa} ${r.address}`}
          mobileCard={(r: any) => (
            <div>
              <div className="flex items-start justify-between gap-2"><p className="font-semibold">{r.name}</p><ResellerType special={r.is_special} /></div>
              <MobileRow label="WhatsApp">{r.wa}</MobileRow>
              <MobileRow label="Sisa Tagihan">{rupiah(outstanding(r))}</MobileRow>
              <Button size="sm" variant="outline" className="mt-2 w-full" onClick={() => setEdit(r)}><Pencil /> Ubah</Button>
            </div>
          )}
          mobileDetail={(r: any) => (
            <div><MobileRow label="Order">{r.order_count}</MobileRow><MobileRow label="Akun">{r.users.map((u: any) => u.email).join(", ") || "-"}</MobileRow>
              <p className="mt-1 text-xs text-slate-500">{r.address}</p></div>
          )} />
      )}
      <Dialog open={!!edit} onOpenChange={(o) => !o && setEdit(null)}>
        <DialogContent className="max-h-[90vh] max-w-lg overflow-y-auto">
          <DialogHeader><DialogTitle>{edit?.id ? "Ubah Reseller" : "Tambah Reseller"}</DialogTitle></DialogHeader>
          {edit && <ResellerForm reseller={edit.id ? edit : undefined} onDone={done} />}
        </DialogContent>
      </Dialog>
    </div>
  );
}
