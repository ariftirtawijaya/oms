import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { AlertTriangle, Eye, Info, ShieldAlert, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Empty, Field, Section } from "@/components/common";
import { api, errMsg } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { fmtDateTime } from "@/lib/format";

const CATS = [
  { key: "orders", label: "Data Order", desc: "Seluruh order, pembayaran, pengiriman, histori status, penyesuaian harga, serta foto resi terkait." },
  { key: "resellers", label: "Data Reseller", desc: "Data reseller dan akun login reseller terkait." },
  { key: "products", label: "Data Produk", desc: "Seluruh master produk. Order lama tetap utuh." },
  { key: "notifications", label: "Riwayat Notifikasi WhatsApp", desc: "Histori pengiriman, antrean, serta log notifikasi." },
  { key: "audit", label: "Log Audit dan Aktivitas", desc: "Riwayat aktivitas aplikasi. Catatan keamanan pembersihan tetap disimpan." },
];
const COUNT_LABEL: Record<string, string> = {
  orders: "Order", order_payments: "Pembayaran", shipments: "Pengiriman", resi_files: "Foto resi",
  notifications_cancelled: "Notifikasi antrean dibatalkan", order_seq_counters: "Counter nomor urut order",
  resellers: "Reseller", users: "Akun login reseller", products: "Produk", notification_logs: "Riwayat notifikasi",
  announcement_states: "Status pengumuman", webhook_events: "Event webhook", audit_logs: "Log audit",
};
const CAT_LABEL = Object.fromEntries(CATS.map((c) => [c.key, c.label]));
const RESULT_LABEL: Record<string, string> = {
  berhasil: "Berhasil", dibatalkan_backup_gagal: "Dibatalkan: backup gagal",
  gagal_dipulihkan: "Gagal, data dipulihkan & terverifikasi", ditolak_password_salah: "Ditolak: password salah",
  gagal_pemulihan_otomatis: "Gagal, perlu pemulihan manual",
  dibatalkan_terputus_saat_backup: "Terputus saat backup, tidak ada data dihapus",
  dipulihkan_setelah_restart: "Terputus, dipulihkan otomatis setelah restart & terverifikasi",
  selesai_dicatat_saat_restart: "Berhasil (dicatat saat restart)",
  dipulihkan_manual: "Dipulihkan manual & terverifikasi",
};

function Counts({ counts }: { counts: Record<string, Record<string, number>> }) {
  return (
    <div className="grid gap-3 sm:grid-cols-2" data-testid="cleanup-preview-counts">
      {Object.entries(counts).map(([cat, c]) => (
        <div key={cat} className="rounded-lg border border-slate-200 p-3 text-sm">
          <p className="mb-1 font-semibold text-slate-900">{CAT_LABEL[cat]}</p>
          {Object.entries(c).map(([k, v]) => (
            <div key={k} className="flex justify-between py-0.5"><span className="text-slate-500">{COUNT_LABEL[k] || k}</span><b className="tabular-nums" data-testid={`cleanup-count-${k}`}>{v}</b></div>
          ))}
        </div>
      ))}
    </div>
  );
}

function Notice({ tone, items, testid }: { tone: "red" | "amber"; items: string[]; testid: string }) {
  if (!items.length) return null;
  const cls = tone === "red" ? "border-red-200 bg-red-50 text-red-800" : "border-amber-200 bg-amber-50 text-amber-800";
  return (
    <div className={`space-y-1 rounded-lg border p-3 text-sm ${cls}`} data-testid={testid}>
      {items.map((t, i) => <p key={i} className="flex gap-2"><AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />{t}</p>)}
    </div>
  );
}

function History() {
  const { data = [] } = useQuery({ queryKey: ["cleanup-history"], queryFn: () => api.get("/settings/cleanup/history").then((r) => r.data), staleTime: 0 });
  if (!data.length) return <Empty text="Belum ada riwayat pembersihan data." testid="cleanup-history-empty" />;
  return (
    <div className="space-y-2" data-testid="cleanup-history">
      {data.map((h: any) => (
        <div key={h.id} className="rounded-lg border border-slate-200 p-3 text-sm">
          <p className="font-medium">{fmtDateTime(h.created_at)} • {h.actor_name} ({h.actor_email})</p>
          <p className="text-slate-600">Kategori: {(h.categories || []).map((c: string) => CAT_LABEL[c] || c).join(", ")}</p>
          <p className="text-slate-600">Hasil: <b>{RESULT_LABEL[h.result] || h.result}</b>{h.deleted && Object.keys(h.deleted).length ? ` • ${h.result === "berhasil" || h.result === "selesai_dicatat_saat_restart" ? "Terhapus" : "Sempat terhapus"}: ${Object.entries(h.deleted).map(([k, v]) => `${COUNT_LABEL[k] || k} ${v}`).join(", ")}${h.result === "gagal_dipulihkan" ? " (sudah dipulihkan)" : ""}` : ""}</p>
          {h.backup && <p className="break-all text-xs text-slate-500">Backup: {h.backup}</p>}
        </div>
      ))}
    </div>
  );
}

function ConfirmDialog({ open, onClose, onRun, busy }: { open: boolean; onClose: () => void; onRun: (text: string, pw: string) => void; busy: boolean }) {
  const [text, setText] = useState("");
  const [pw, setPw] = useState("");
  const ok = text === "HAPUS DATA" && pw.length > 0;
  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o && !busy) { setText(""); setPw(""); onClose(); } }}>
      <DialogContent data-testid="cleanup-confirm-dialog">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-red-700"><ShieldAlert className="h-5 w-5" /> Konfirmasi Pembersihan Data</DialogTitle>
          <DialogDescription>Backup otomatis dibuat sebelum penghapusan. Jika backup gagal, tidak ada data yang dihapus.</DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          <Field label="Ketik HAPUS DATA"><Input value={text} onChange={(e) => setText(e.target.value)} placeholder="HAPUS DATA" autoComplete="off" data-testid="cleanup-confirm-text" /></Field>
          <Field label="Password Super Admin saat ini"><Input type="password" value={pw} onChange={(e) => setPw(e.target.value)} autoComplete="current-password" data-testid="cleanup-confirm-password" /></Field>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={busy} data-testid="cleanup-confirm-cancel">Batal</Button>
          <Button className="bg-red-600 text-white hover:bg-red-700" disabled={!ok || busy} onClick={() => onRun(text, pw)} data-testid="cleanup-confirm-submit">
            <Trash2 /> {busy ? "Memproses..." : "Hapus Data Permanen"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export function CleanupTab() {
  const { user } = useAuth();
  const qc = useQueryClient();
  const [sel, setSel] = useState<string[]>([]);
  const [resetSeq, setResetSeq] = useState(false);
  const [pv, setPv] = useState<any>(null);
  const [result, setResult] = useState<any>(null);
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const { data: status } = useQuery({ queryKey: ["cleanup-status"], queryFn: () => api.get("/settings/cleanup/status").then((r) => r.data), staleTime: 0 });
  const locked = !!status?.blocked;

  if (!user || !user.is_super_admin)
    return <Section title="Pembersihan Data" testid="cleanup-section"><Empty text="Fitur pembersihan data hanya dapat digunakan oleh Super Admin." testid="cleanup-not-allowed" /></Section>;

  const toggle = (k: string, on: boolean) => {
    const next = on ? [...sel, k] : sel.filter((x) => x !== k);
    setSel(next); setPv(null); setResult(null);
    if (!next.includes("orders")) setResetSeq(false);
  };
  const body = { categories: sel, reset_order_seq: resetSeq };
  const preview = async () => {
    setBusy(true);
    try { setPv((await api.post("/settings/cleanup/preview", body)).data); }
    catch (e) { toast.error(errMsg(e)); } finally { setBusy(false); }
  };
  const run = async (confirm_text: string, password: string) => {
    setBusy(true);
    try {
      const { data } = await api.post("/settings/cleanup/execute", { ...body, confirm_text, password });
      setResult(data); setPv(null); setSel([]); setResetSeq(false); setOpen(false);
      await qc.invalidateQueries();
      toast.success("Pembersihan data selesai.");
    } catch (e) {
      toast.error(errMsg(e));
      qc.invalidateQueries({ queryKey: ["cleanup-history"] });
    } finally { setBusy(false); }
  };

  return (
    <div className="space-y-5">
      <Section title="Pembersihan Data" testid="cleanup-section">
        <div className="space-y-4">
          <p className="flex gap-2 rounded-lg border border-blue-200 bg-blue-50 p-3 text-sm text-blue-800" data-testid="cleanup-report-info">
            <Info className="mt-0.5 h-4 w-4 shrink-0" />Laporan dan dashboard dihitung otomatis dari data order dan pembayaran, sehingga tidak perlu dihapus terpisah dan akan ikut menyesuaikan setelah pembersihan.
          </p>
          <div className="grid gap-2 md:grid-cols-2">
            {CATS.map((c) => (
              <label key={c.key} className="flex cursor-pointer gap-3 rounded-lg border border-slate-200 p-3 hover:bg-slate-50">
                <Checkbox checked={sel.includes(c.key)} disabled={locked} onCheckedChange={(v) => toggle(c.key, v === true)} className="mt-0.5" data-testid={`cleanup-cat-${c.key}`} />
                <span><span className="block text-sm font-medium text-slate-900">{c.label}</span><span className="block text-xs text-slate-500">{c.desc}</span></span>
              </label>
            ))}
          </div>
          {sel.includes("orders") && (
            <label className="flex cursor-pointer gap-3 rounded-lg border border-amber-200 bg-amber-50/60 p-3">
              <Checkbox checked={resetSeq} onCheckedChange={(v) => { setResetSeq(v === true); setPv(null); }} className="mt-0.5" data-testid="cleanup-reset-seq" />
              <span className="text-sm"><span className="block font-medium text-slate-900">Opsional: reset nomor urut order</span>
                <span className="block text-xs text-slate-600">Nomor order berikutnya kembali ke 0001 untuk tanggal yang sama. Risiko: kode order baru bisa sama dengan kode order lama yang pernah dicatat di luar sistem (WhatsApp, nota, atau backup).</span></span>
            </label>
          )}
          <Button variant="outline" onClick={preview} disabled={!sel.length || busy || locked} data-testid="cleanup-preview-button"><Eye /> Lihat Pratinjau</Button>
          {pv && (
            <div className="space-y-3" data-testid="cleanup-preview">
              <Counts counts={pv.counts} />
              <Notice tone="red" items={pv.blocking} testid="cleanup-blocking" />
              <Notice tone="amber" items={pv.warnings} testid="cleanup-warnings" />
              <p className="text-sm text-slate-700">Total data yang akan dihapus: <b data-testid="cleanup-total">{pv.total}</b></p>
              <Button className="bg-red-600 text-white hover:bg-red-700" disabled={pv.blocking.length > 0 || busy || locked} onClick={() => setOpen(true)} data-testid="cleanup-execute-button"><Trash2 /> Hapus Data Terpilih</Button>
            </div>
          )}
          {result && (
            <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800" data-testid="cleanup-result">
              <p className="font-semibold">{RESULT_LABEL[result.result] || result.result}</p>
              <p>Terhapus: {Object.entries(result.deleted).map(([k, v]) => `${COUNT_LABEL[k] || k} ${v}`).join(", ")}</p>
              <p className="break-all text-xs">Backup: {result.backup}</p>
            </div>
          )}
        </div>
      </Section>
      <Section title="Catatan Keamanan Pembersihan" testid="cleanup-history-section"><History /></Section>
      <ConfirmDialog open={open} onClose={() => setOpen(false)} onRun={run} busy={busy} />
    </div>
  );
}
