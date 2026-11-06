import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { ImageUp, RotateCcw, Save, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Field, Section } from "@/components/common";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription,
  AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { api, errMsg } from "@/lib/api";
import { Branding, BrandMark, brandingFileUrl, useBranding } from "@/lib/branding";

type Pick = { file: File | null; remove: boolean };
const RULES = {
  logo: { accept: "image/png,image/jpeg,image/webp", types: ["image/png", "image/jpeg", "image/webp"], mb: 2, hint: "PNG (boleh transparan), JPG, atau WebP. Maksimal 2 MB." },
  favicon: { accept: "image/png,image/x-icon,image/vnd.microsoft.icon,.ico", types: ["image/png", "image/x-icon", "image/vnd.microsoft.icon"], mb: 1, hint: "PNG atau ICO, disarankan persegi 64×64 px. Maksimal 1 MB." },
};

function ImagePicker({ kind, label, current, value, onChange }: {
  kind: "logo" | "favicon"; label: string; current: string | null; value: Pick; onChange: (v: Pick) => void;
}) {
  const rule = RULES[kind];
  const [preview, setPreview] = useState<string | null>(null);
  useEffect(() => {
    if (!value.file) { setPreview(null); return; }
    const u = URL.createObjectURL(value.file);
    setPreview(u);
    return () => { URL.revokeObjectURL(u); };
  }, [value.file]);
  const src = preview || (!value.remove && current ? brandingFileUrl(current) : null);
  const pick = (f?: File) => {
    if (!f) return;
    const isIco = kind === "favicon" && f.name.toLowerCase().endsWith(".ico");
    if (!rule.types.includes(f.type) && !isIco) return toast.error(`Format ${label} tidak didukung. ${rule.hint}`);
    if (f.size > rule.mb * 1024 * 1024) return toast.error(`Ukuran ${label} maksimal ${rule.mb} MB.`);
    onChange({ file: f, remove: false });
  };
  return (
    <div className="space-y-2" data-testid={`branding-${kind}-picker`}>
      <p className="text-sm font-medium text-slate-700">{label}</p>
      <div className="flex flex-wrap items-center gap-4">
        <div className="flex h-20 w-20 items-center justify-center rounded-xl border border-dashed border-slate-300 bg-[repeating-conic-gradient(#f1f5f9_0%_25%,#fff_0%_50%)] bg-[length:16px_16px]">
          {src ? <img src={src} alt={`Pratinjau ${label}`} className="max-h-16 max-w-16 object-contain" data-testid={`branding-${kind}-preview`} />
            : kind === "logo" ? <BrandMark className="h-12 w-12" /> : <img src={`${process.env.PUBLIC_URL}/favicon.svg`} alt="Favicon bawaan" className="h-10 w-10" />}
        </div>
        <div className="flex flex-wrap gap-2">
          <label className="inline-flex h-9 cursor-pointer items-center gap-2 rounded-md border border-slate-200 bg-white px-3 text-sm font-medium hover:bg-slate-50">
            <ImageUp className="h-4 w-4" /> {src ? "Ganti" : "Pilih"} Gambar
            <input type="file" accept={rule.accept} className="sr-only" onChange={(e) => { pick(e.target.files?.[0]); e.target.value = ""; }} data-testid={`branding-${kind}-input`} />
          </label>
          {src && <Button type="button" variant="outline" size="sm" className="h-9" onClick={() => onChange({ file: null, remove: true })} data-testid={`branding-${kind}-remove`}><Trash2 /> Pakai Bawaan</Button>}
        </div>
      </div>
      <p className="text-xs text-slate-500">{rule.hint}</p>
    </div>
  );
}

export function BrandingTab() {
  const b = useBranding();
  const qc = useQueryClient();
  const [name, setName] = useState(b.app_name);
  const [tagline, setTagline] = useState(b.tagline);
  const [logo, setLogo] = useState<Pick>({ file: null, remove: false });
  const [fav, setFav] = useState<Pick>({ file: null, remove: false });
  const [busy, setBusy] = useState(false);
  const [confirm, setConfirm] = useState(false);
  useEffect(() => { setName(b.app_name); setTagline(b.tagline); }, [b.app_name, b.tagline]);

  const done = (data: Branding, msg: string) => {
    qc.setQueryData(["branding"], data);
    setLogo({ file: null, remove: false }); setFav({ file: null, remove: false });
    toast.success(msg);
  };
  const save = async () => {
    if (name.trim().length < 2) return toast.error("Nama aplikasi minimal 2 karakter.");
    const fd = new FormData();
    fd.append("app_name", name.trim()); fd.append("tagline", tagline.trim());
    fd.append("remove_logo", String(logo.remove)); fd.append("remove_favicon", String(fav.remove));
    if (logo.file) fd.append("logo", logo.file);
    if (fav.file) fd.append("favicon", fav.file);
    setBusy(true);
    try { done((await api.put("/settings/branding", fd)).data, "Branding aplikasi berhasil disimpan."); }
    catch (e) { toast.error(errMsg(e)); } finally { setBusy(false); }
  };
  const reset = async () => {
    setBusy(true);
    try { done((await api.post("/settings/branding/reset")).data, "Branding dikembalikan ke default."); }
    catch (e) { toast.error(errMsg(e)); } finally { setBusy(false); setConfirm(false); }
  };

  return (
    <Section title="Branding Aplikasi" testid="branding-section">
      <div className="grid gap-6 lg:grid-cols-2">
        <div className="space-y-4">
          <Field label="Nama Aplikasi"><Input value={name} maxLength={60} onChange={(e) => setName(e.target.value)} className="bg-white" data-testid="branding-name-input" /></Field>
          <Field label="Subtitle / Tagline" hint="Boleh dikosongkan."><Input value={tagline} maxLength={80} onChange={(e) => setTagline(e.target.value)} className="bg-white" data-testid="branding-tagline-input" /></Field>
        </div>
        <div className="space-y-5">
          <ImagePicker kind="logo" label="Logo Aplikasi" current={b.logo_file} value={logo} onChange={setLogo} />
          <ImagePicker kind="favicon" label="Favicon Browser" current={b.favicon_file} value={fav} onChange={setFav} />
        </div>
      </div>
      <p className="mt-5 text-xs text-slate-500">Perubahan langsung berlaku di sidebar, header mobile, halaman login, judul tab, dan favicon untuk semua akun admin maupun reseller.</p>
      <div className="mt-4 flex flex-wrap gap-2 border-t border-slate-100 pt-4">
        <Button onClick={save} disabled={busy} className="bg-blue-700 text-white hover:bg-blue-800" data-testid="branding-save-button"><Save /> {busy ? "Menyimpan..." : "Simpan"}</Button>
        <Button variant="outline" onClick={() => setConfirm(true)} disabled={busy} data-testid="branding-reset-button"><RotateCcw /> Kembalikan Default</Button>
      </div>
      <AlertDialog open={confirm} onOpenChange={setConfirm}>
        <AlertDialogContent data-testid="branding-reset-dialog">
          <AlertDialogHeader>
            <AlertDialogTitle>Kembalikan branding default?</AlertDialogTitle>
            <AlertDialogDescription>Nama menjadi "RelayLab OMS", subtitle "Autolight Order System", serta logo dan favicon kembali ke bawaan.</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel data-testid="branding-reset-cancel">Batal</AlertDialogCancel>
            <AlertDialogAction onClick={reset} data-testid="branding-reset-confirm">Kembalikan</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </Section>
  );
}
