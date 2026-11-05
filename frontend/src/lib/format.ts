const JKT = "Asia/Jakarta";

export function rupiah(n: number | null | undefined): string {
  if (n === null || n === undefined) return "-";
  const v = Math.round(Number(n));
  const s = Math.abs(v).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ".");
  return `${v < 0 ? "-" : ""}Rp${s}`;
}

function parts(iso: string) {
  const d = new Date(iso);
  const f = new Intl.DateTimeFormat("en-GB", {
    timeZone: JKT, year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hour12: false,
  }).formatToParts(d);
  const g = (t: string) => f.find((p) => p.type === t)?.value || "";
  return { dd: g("day"), mm: g("month"), yyyy: g("year"), hh: g("hour") === "24" ? "00" : g("hour"), mi: g("minute") };
}

export function fmtDateTime(iso?: string | null): string {
  if (!iso) return "-";
  const p = parts(iso);
  return `${p.dd}-${p.mm}-${p.yyyy} ${p.hh}:${p.mi}`;
}

export function fmtDate(iso?: string | null): string {
  if (!iso) return "-";
  const p = parts(iso);
  return `${p.dd}-${p.mm}-${p.yyyy}`;
}

export function jktToday(): string {
  const p = parts(new Date().toISOString());
  return `${p.yyyy}-${p.mm}-${p.dd}`;
}

export function jktNowLocalInput(): string {
  const p = parts(new Date().toISOString());
  return `${p.yyyy}-${p.mm}-${p.dd}T${p.hh}:${p.mi}`;
}

export function firstOfMonth(): string {
  return jktToday().slice(0, 8) + "01";
}

export function ymdToDisplay(ymd: string): string {
  const [y, m, d] = ymd.split("-");
  return `${d}-${m}-${y}`;
}

export function voltageLabel(v?: string | null): string {
  const s = (v || "").trim();
  if (!s || s === "-") return "";
  return /v$/i.test(s) ? s.toUpperCase() : `${s}V`;
}

export function productName(name: string, voltage?: string | null): string {
  const vl = voltageLabel(voltage);
  return vl ? `${name} ${vl}` : name;
}

export function tokenMatch(haystack: string, query: string): boolean {
  const tokens = query.toLowerCase().split(/\s+/).filter(Boolean);
  const h = haystack.toLowerCase();
  return tokens.every((t) => h.includes(t));
}

export function newKey(): string {
  if (window.crypto && "randomUUID" in window.crypto) return window.crypto.randomUUID();
  return `${Date.now()}-${Math.random().toString(36).slice(2)}-${Math.random().toString(36).slice(2)}`;
}

export function downloadCSV(filename: string, header: string[], rows: (string | number)[][]) {
  const esc = (v: any) => {
    const s = String(v ?? "");
    return /[";\n,]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  const csv = "\uFEFF" + [header, ...rows].map((r) => r.map(esc).join(";")).join("\n");
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  a.click();
  URL.revokeObjectURL(a.href);
}

export const STATUS_META: Record<string, { label: string; cls: string }> = {
  menunggu_konfirmasi: { label: "Menunggu Konfirmasi", cls: "bg-amber-100 text-amber-800 border-amber-200" },
  diproses: { label: "Diproses", cls: "bg-blue-100 text-blue-800 border-blue-200" },
  selesai: { label: "Selesai", cls: "bg-emerald-100 text-emerald-800 border-emerald-200" },
};

export const PAYMENT_META: Record<string, { label: string; cls: string }> = {
  belum_ada_pembayaran: { label: "Belum Ada Pembayaran", cls: "bg-slate-100 text-slate-700 border-slate-200" },
  belum_lunas: { label: "Belum Lunas", cls: "bg-amber-100 text-amber-800 border-amber-200" },
  lunas: { label: "Lunas", cls: "bg-emerald-100 text-emerald-800 border-emerald-200" },
  lebih_bayar: { label: "Lebih Bayar", cls: "bg-violet-100 text-violet-800 border-violet-200" },
};

export const NOTIF_META: Record<string, { label: string; cls: string }> = {
  pending: { label: "Menunggu Kirim", cls: "bg-amber-100 text-amber-800 border-amber-200" },
  sending: { label: "Sedang Dikirim", cls: "bg-blue-100 text-blue-800 border-blue-200" },
  sent: { label: "Diterima API Fonnte", cls: "bg-emerald-100 text-emerald-800 border-emerald-200" },
  simulated: { label: "Simulasi", cls: "bg-slate-100 text-slate-700 border-slate-200" },
  failed: { label: "Gagal", cls: "bg-red-100 text-red-800 border-red-200" },
};
