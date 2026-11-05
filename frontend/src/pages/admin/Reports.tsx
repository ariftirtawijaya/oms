import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ColumnDef } from "@tanstack/react-table";
import { Download, Info } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { DataTable, MobileRow } from "@/components/DataTable";
import { Field, Loading, PageHeader, StatCard } from "@/components/common";
import { ResellerType } from "@/pages/admin/Resellers";
import { api } from "@/lib/api";
import { downloadCSV, firstOfMonth, fmtDateTime, jktToday, rupiah } from "@/lib/format";

export default function ReportsPage() {
  const [from, setFrom] = useState(firstOfMonth());
  const [to, setTo] = useState(jktToday());
  const params = { date_from: from, date_to: to };
  const { data, isLoading } = useQuery({ queryKey: ["admin-report", params], queryFn: () => api.get("/reports/admin", { params }).then((r) => r.data), staleTime: 0, enabled: !!from && !!to && from <= to });

  const resCols: ColumnDef<any>[] = [
    { accessorKey: "name", header: "Reseller", cell: ({ row }) => <div className="flex items-center gap-2"><span className="font-semibold">{row.original.name}</span>{row.original.is_special && <ResellerType special />}</div> },
    { accessorKey: "order_count", header: "Order" },
    { accessorKey: "total_qty", header: "Qty" },
    { accessorKey: "total_order", header: "Nilai Order", cell: (c) => rupiah(c.getValue()) },
    { accessorKey: "total_paid", header: "Dibayar", cell: (c) => rupiah(c.getValue()) },
    { accessorKey: "remaining", header: "Sisa Tagihan", cell: (c) => <b>{rupiah(c.getValue())}</b> },
  ];
  const cashCols: ColumnDef<any>[] = [
    { accessorKey: "paid_at", header: "Tanggal Bayar", cell: (c) => fmtDateTime(c.getValue()) },
    { accessorKey: "order_code", header: "Kode Order", cell: (c) => <span className="font-mono">{c.getValue()}</span> },
    { accessorKey: "reseller_name", header: "Reseller" },
    { accessorKey: "amount", header: "Nominal", cell: (c) => <b>{rupiah(c.getValue())}</b> },
    { accessorKey: "notes", header: "Catatan" },
  ];

  const exportRes = () => downloadCSV(`laporan-reseller-${from}-sd-${to}.csv`, ["Reseller", "Jumlah Order", "Total Qty", "Nilai Order", "Dibayar", "Sisa Tagihan"],
    data.per_reseller.map((r: any) => [r.name, r.order_count, r.total_qty, r.total_order, r.total_paid, r.remaining]));
  const exportCash = () => downloadCSV(`arus-kas-${from}-sd-${to}.csv`, ["Tanggal Bayar", "Kode Order", "Reseller", "Nominal", "Catatan"],
    data.cashflow.map((p: any) => [fmtDateTime(p.paid_at), p.order_code, p.reseller_name, p.amount, p.notes]));

  return (
    <div className="space-y-5">
      <PageHeader title="Laporan Keuangan" subtitle="Seluruh nilai berasal dari harga snapshot transaksi, tidak terpengaruh perubahan harga master produk." />
      <div className="grid grid-cols-2 gap-3 rounded-xl border border-slate-200 bg-white p-4 sm:max-w-md">
        <Field label="Dari Tanggal"><Input type="date" value={from} max={to} onChange={(e) => setFrom(e.target.value)} className="h-11" data-testid="report-date-from" /></Field>
        <Field label="Sampai Tanggal"><Input type="date" value={to} min={from} onChange={(e) => setTo(e.target.value)} className="h-11" data-testid="report-date-to" /></Field>
      </div>
      {isLoading || !data ? <Loading /> : (
        <Tabs defaultValue="reseller">
          <TabsList><TabsTrigger value="reseller" data-testid="tab-per-reseller">Rekap per Reseller</TabsTrigger><TabsTrigger value="cash" data-testid="tab-cashflow">Arus Kas</TabsTrigger></TabsList>
          <TabsContent value="reseller" className="space-y-4">
            <p className="flex gap-2 text-sm text-slate-600"><Info className="h-4 w-4 shrink-0" />Berdasarkan tanggal order dibuat. Pembayaran mencakup seluruh pembayaran untuk order tersebut.</p>
            <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
              <StatCard label="Jumlah Order" value={data.summary.order_count} testid="report-order-count" />
              <StatCard label="Nilai Order" value={rupiah(data.summary.total_order)} testid="report-total-order" />
              <StatCard label="Dibayar" value={rupiah(data.summary.total_paid)} testid="report-total-paid" />
              <StatCard label="Piutang" value={rupiah(data.summary.remaining)} testid="report-remaining" />
            </div>
            <DataTable testid="report-reseller-table" data={data.per_reseller} columns={resCols} searchText={(r: any) => r.name}
              toolbar={<Button variant="outline" onClick={exportRes} data-testid="report-export-reseller"><Download /> Ekspor CSV</Button>}
              mobileCard={(r: any) => <div><p className="font-semibold">{r.name}</p><MobileRow label="Nilai Order">{rupiah(r.total_order)}</MobileRow><MobileRow label="Sisa">{rupiah(r.remaining)}</MobileRow></div>} />
          </TabsContent>
          <TabsContent value="cash" className="space-y-4">
            <p className="flex gap-2 text-sm text-slate-600"><Info className="h-4 w-4 shrink-0" />Berdasarkan tanggal pembayaran diterima (pembayaran yang dibatalkan tidak dihitung).</p>
            <StatCard label="Total Kas Masuk" value={rupiah(data.cashflow_total)} testid="report-cashflow-total" />
            <DataTable testid="report-cash-table" data={data.cashflow} columns={cashCols} searchText={(p: any) => `${p.order_code} ${p.reseller_name}`}
              toolbar={<Button variant="outline" onClick={exportCash} data-testid="report-export-cash"><Download /> Ekspor CSV</Button>}
              mobileCard={(p: any) => <div><p className="font-mono text-sm font-bold">{p.order_code}</p><MobileRow label={fmtDateTime(p.paid_at)}>{rupiah(p.amount)}</MobileRow><p className="text-xs text-slate-500">{p.reseller_name}</p></div>} />
          </TabsContent>
        </Tabs>
      )}
    </div>
  );
}
