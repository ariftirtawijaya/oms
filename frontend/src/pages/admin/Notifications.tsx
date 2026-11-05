import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ColumnDef } from "@tanstack/react-table";
import { toast } from "sonner";
import { RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { DataTable, MobileRow } from "@/components/DataTable";
import { NotifBadge } from "@/components/badges";
import { Loading, PageHeader } from "@/components/common";
import { api, errMsg } from "@/lib/api";
import { NOTIF_META, fmtDateTime } from "@/lib/format";

const KIND: Record<string, string> = {
  order_baru_reseller: "Order Baru (Reseller)", order_baru_admin: "Order Baru (Admin)", order_diproses: "Order Diproses",
  pengiriman: "Pengiriman", balasan_cekorder: "Balasan /cekorder", balasan_pengumuman: "Balasan Pengumuman", pengumuman: "Pengumuman Grup",
};

export default function NotificationsPage() {
  const qc = useQueryClient();
  const [status, setStatus] = useState("semua");
  const [view, setView] = useState<any>(null);
  const params = status === "semua" ? {} : { status };
  const { data, isLoading } = useQuery({ queryKey: ["notifications", params], queryFn: () => api.get("/notifications", { params }).then((r) => r.data), staleTime: 0, refetchInterval: 15000 });
  const retry = async (n: any) => {
    try { const { data: d } = await api.post(`/notifications/${n.id}/retry`); toast.success(`Status: ${NOTIF_META[d.status]?.label || d.status}`); qc.invalidateQueries({ queryKey: ["notifications"] }); }
    catch (e) { toast.error(errMsg(e)); }
  };
  const Act = ({ n }: { n: any }) => (
    <div className="flex justify-end gap-1">
      <Button size="sm" variant="ghost" onClick={() => setView(n)} data-testid={`notif-view-${n.id}`}>Lihat</Button>
      {["failed", "pending"].includes(n.status) && <Button size="sm" variant="outline" onClick={() => retry(n)} data-testid={`notif-retry-${n.id}`}><RefreshCw /> Kirim Ulang</Button>}
    </div>
  );
  const columns: ColumnDef<any>[] = [
    { accessorKey: "created_at", header: "Waktu", cell: (c) => fmtDateTime(c.getValue()) },
    { accessorKey: "kind", header: "Jenis", cell: (c) => KIND[c.getValue()] || c.getValue() },
    { accessorKey: "target", header: "Tujuan" },
    { accessorKey: "status", header: "Status", cell: (c) => <NotifBadge status={c.getValue()} /> },
    { accessorKey: "attempts", header: "Percobaan" },
    { accessorKey: "last_error", header: "Error", cell: (c) => <span className="block max-w-[220px] truncate text-xs text-red-600">{c.getValue() || "-"}</span> },
    { id: "aksi", header: "", enableSorting: false, cell: ({ row }) => <Act n={row.original} /> },
  ];
  return (
    <div>
      <PageHeader title="Riwayat Notifikasi WhatsApp" subtitle="Antrean dan log pengiriman via Fonnte. Status 'Diterima API Fonnte' belum berarti pesan sudah dibaca penerima." />
      {data && (
        <div className={`mb-4 rounded-xl border p-3 text-sm ${data.mode === "live" ? "border-emerald-200 bg-emerald-50 text-emerald-900" : "border-amber-200 bg-amber-50 text-amber-900"}`} data-testid="whatsapp-mode-banner">
          Mode WhatsApp: <b>{data.mode === "live" ? "LIVE (mengirim ke Fonnte)" : "SIMULASI (pesan tidak dikirim)"}</b> • Token Fonnte: <b>{data.token_configured ? "terkonfigurasi" : "belum diisi"}</b>.
          {data.mode !== "live" && " Atur WHATSAPP_MODE=live dan FONNTE_TOKEN di server untuk mengirim pesan sungguhan."}
        </div>
      )}
      {isLoading || !data ? <Loading /> : (
        <DataTable testid="notifications-table" data={data.items} columns={columns} searchText={(n: any) => `${n.target} ${KIND[n.kind] || n.kind} ${n.message}`}
          toolbar={
            <Select value={status} onValueChange={setStatus}>
              <SelectTrigger className="h-10 bg-white sm:w-52" data-testid="notif-status-filter"><SelectValue /></SelectTrigger>
              <SelectContent><SelectItem value="semua">Semua Status</SelectItem>{Object.entries(NOTIF_META).map(([k, v]) => <SelectItem key={k} value={k}>{v.label}</SelectItem>)}</SelectContent>
            </Select>}
          mobileCard={(n: any) => (
            <div><div className="flex justify-between gap-2"><p className="text-sm font-semibold">{KIND[n.kind] || n.kind}</p><NotifBadge status={n.status} /></div>
              <MobileRow label="Tujuan">{n.target}</MobileRow><MobileRow label="Waktu">{fmtDateTime(n.created_at)}</MobileRow>
              {n.last_error && <p className="text-xs text-red-600">{n.last_error}</p>}<div className="mt-2"><Act n={n} /></div></div>
          )} />
      )}
      <Dialog open={!!view} onOpenChange={(o) => !o && setView(null)}>
        <DialogContent className="max-h-[90vh] max-w-lg overflow-y-auto">
          <DialogHeader><DialogTitle>Detail Notifikasi</DialogTitle></DialogHeader>
          {view && (
            <div className="space-y-3 text-sm">
              <div className="flex items-center gap-2"><NotifBadge status={view.status} /><span>{view.target}</span></div>
              {view.file_path && <p className="text-xs">Lampiran foto: {view.media_sent === true ? "berhasil dilampirkan" : view.media_sent === false ? "gagal dilampirkan (pesan dikirim tanpa foto)" : "belum dikirim"}</p>}
              <pre className="whitespace-pre-wrap rounded-lg bg-slate-50 p-3 font-sans text-sm" data-testid="notif-message">{view.rendered_message || view.message}</pre>
              <p className="text-xs font-semibold">Log respons</p>
              <pre className="max-h-48 overflow-auto rounded-lg bg-slate-900 p-3 text-[11px] text-slate-100">{JSON.stringify(view.responses, null, 2)}</pre>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
