import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ColumnDef } from "@tanstack/react-table";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import { KeyRound, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { DataTable, MobileRow } from "@/components/DataTable";
import { Field, Loading, PageHeader } from "@/components/common";
import { api, errMsg } from "@/lib/api";
import { fmtDateTime } from "@/lib/format";

const schema = z.object({
  name: z.string().trim().min(2, "Nama wajib diisi."),
  email: z.string().email("Format email tidak valid."),
  role: z.enum(["admin", "reseller"]),
  reseller_id: z.string().optional(),
  password: z.string().min(8, "Password minimal 8 karakter."),
  must_change_password: z.boolean(),
}).refine((v) => v.role === "admin" || !!v.reseller_id, { message: "Pilih reseller.", path: ["reseller_id"] });

function UserForm({ onDone }: { onDone: () => void }) {
  const { data: resellers = [] } = useQuery({ queryKey: ["resellers"], queryFn: () => api.get("/resellers").then((r) => r.data) });
  const { register, handleSubmit, setValue, watch, formState: { errors, isSubmitting } } = useForm<z.infer<typeof schema>>({
    resolver: zodResolver(schema), defaultValues: { role: "reseller", must_change_password: true, name: "", email: "", password: "" },
  });
  const role = watch("role");
  const submit = async (v: any) => {
    try {
      await api.post("/users", { ...v, reseller_id: v.role === "reseller" ? v.reseller_id : null });
      toast.success("Akun login dibuat.");
      onDone();
    } catch (e) { toast.error(errMsg(e)); }
  };
  return (
    <form onSubmit={handleSubmit(submit)} className="space-y-4" data-testid="user-form">
      <Field label="Role">
        <Select value={role} onValueChange={(v: any) => setValue("role", v)}>
          <SelectTrigger data-testid="user-role-select"><SelectValue /></SelectTrigger>
          <SelectContent><SelectItem value="reseller">Reseller</SelectItem><SelectItem value="admin">Admin</SelectItem></SelectContent>
        </Select>
      </Field>
      {role === "reseller" && (
        <Field label="Reseller" error={errors.reseller_id?.message}>
          <Select value={watch("reseller_id")} onValueChange={(v) => { setValue("reseller_id", v); const r = resellers.find((x: any) => x.id === v); if (r && !watch("name")) setValue("name", r.name); }}>
            <SelectTrigger data-testid="user-reseller-select"><SelectValue placeholder="Pilih reseller" /></SelectTrigger>
            <SelectContent>{resellers.map((r: any) => <SelectItem key={r.id} value={r.id}>{r.name}</SelectItem>)}</SelectContent>
          </Select>
        </Field>
      )}
      <Field label="Nama" error={errors.name?.message}><Input {...register("name")} data-testid="user-name-input" /></Field>
      <Field label="Email" error={errors.email?.message}><Input type="email" {...register("email")} data-testid="user-email-input" /></Field>
      <Field label="Password Awal" error={errors.password?.message}><Input {...register("password")} data-testid="user-password-input" /></Field>
      <label className="flex items-center gap-3 text-sm">
        <Switch checked={watch("must_change_password")} onCheckedChange={(c) => setValue("must_change_password", c)} data-testid="user-must-change-switch" />
        Wajib ganti password saat login pertama
      </label>
      <DialogFooter><Button type="submit" disabled={isSubmitting} className="bg-blue-700 text-white hover:bg-blue-800" data-testid="user-save-button">Simpan</Button></DialogFooter>
    </form>
  );
}

function ResetForm({ user, onDone }: { user: any; onDone: () => void }) {
  const [pw, setPw] = useState("");
  const [must, setMust] = useState(true);
  const [busy, setBusy] = useState(false);
  const submit = async () => {
    if (pw.length < 8) return toast.error("Password minimal 8 karakter.");
    setBusy(true);
    try {
      await api.post(`/users/${user.id}/reset-password`, { new_password: pw, must_change_password: must });
      toast.success("Password direset. Sesi lama pengguna otomatis berakhir.");
      onDone();
    } catch (e) { toast.error(errMsg(e)); } finally { setBusy(false); }
  };
  return (
    <div className="space-y-4">
      <p className="text-sm text-slate-600">Reset password untuk <b>{user.email}</b></p>
      <Field label="Password Baru"><Input value={pw} onChange={(e) => setPw(e.target.value)} data-testid="reset-password-input" /></Field>
      <label className="flex items-center gap-3 text-sm"><Switch checked={must} onCheckedChange={setMust} /> Wajib ganti password saat login</label>
      <DialogFooter><Button onClick={submit} disabled={busy} className="bg-blue-700 text-white hover:bg-blue-800" data-testid="reset-password-submit">Reset Password</Button></DialogFooter>
    </div>
  );
}

export default function UsersPage() {
  const qc = useQueryClient();
  const { data = [], isLoading } = useQuery({ queryKey: ["users"], queryFn: () => api.get("/users").then((r) => r.data) });
  const [creating, setCreating] = useState(false);
  const [reset, setReset] = useState<any>(null);
  const refresh = () => qc.invalidateQueries({ queryKey: ["users"] });
  const toggle = async (u: any) => {
    try { await api.patch(`/users/${u.id}`, { is_active: !u.is_active }); toast.success(u.is_active ? "Akun dinonaktifkan." : "Akun diaktifkan."); refresh(); }
    catch (e) { toast.error(errMsg(e)); }
  };
  const Actions = ({ u }: { u: any }) => (
    <div className="flex items-center justify-end gap-2">
      <Button size="sm" variant="outline" onClick={() => setReset(u)} data-testid={`user-reset-${u.email}`}><KeyRound /> Reset</Button>
      <Switch checked={u.is_active} onCheckedChange={() => toggle(u)} data-testid={`user-active-${u.email}`} aria-label="Aktif" />
    </div>
  );
  const columns: ColumnDef<any, any>[] = [
    { accessorKey: "name", header: "Nama", cell: (c) => <span className="font-semibold">{c.getValue()}</span> },
    { accessorKey: "email", header: "Email" },
    { accessorKey: "role", header: "Role", cell: (c) => <Badge variant={c.getValue() === "admin" ? "default" : "secondary"}>{c.getValue() === "admin" ? "Admin" : "Reseller"}</Badge> },
    { accessorKey: "reseller_name", header: "Reseller", cell: (c) => c.getValue() || "-" },
    { accessorKey: "last_login_at", header: "Login Terakhir", cell: (c) => fmtDateTime(c.getValue()) },
    { id: "pw", header: "Password", cell: ({ row }) => row.original.must_change_password ? <Badge className="bg-amber-100 text-amber-800">Sementara</Badge> : "-" },
    { id: "aksi", header: "Aktif", enableSorting: false, cell: ({ row }) => <Actions u={row.original} /> },
  ];
  return (
    <div>
      <PageHeader title="User Login" subtitle="Kelola akun admin dan reseller."
        actions={<Button onClick={() => setCreating(true)} className="bg-blue-700 text-white hover:bg-blue-800" data-testid="add-user-button"><Plus /> Tambah User</Button>} />
      {isLoading ? <Loading /> : (
        <DataTable testid="users-table" data={data} columns={columns} searchText={(u: any) => `${u.name} ${u.email} ${u.reseller_name || ""}`}
          mobileCard={(u: any) => (
            <div>
              <p className="font-semibold">{u.name}</p><p className="text-xs text-slate-500">{u.email}</p>
              <MobileRow label="Role">{u.role === "admin" ? "Admin" : `Reseller — ${u.reseller_name || "-"}`}</MobileRow>
              <div className="mt-2"><Actions u={u} /></div>
            </div>
          )} />
      )}
      <Dialog open={creating} onOpenChange={setCreating}>
        <DialogContent className="max-w-lg"><DialogHeader><DialogTitle>Tambah User</DialogTitle></DialogHeader>
          {creating && <UserForm onDone={() => { setCreating(false); refresh(); }} />}</DialogContent>
      </Dialog>
      <Dialog open={!!reset} onOpenChange={(o) => !o && setReset(null)}>
        <DialogContent className="max-w-md"><DialogHeader><DialogTitle>Reset Password</DialogTitle></DialogHeader>
          {reset && <ResetForm user={reset} onDone={() => { setReset(null); refresh(); }} />}</DialogContent>
      </Dialog>
    </div>
  );
}
