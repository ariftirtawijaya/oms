import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ColumnDef } from "@tanstack/react-table";
import { Download, Info } from "lucide-react";
import { Button } from "@/components/ui/button";
import { DateInput } from "@/components/DateInput";
import { DataTable, MobileRow } from "@/components/DataTable";
import { StatusBadge } from "@/components/badges";
import { Field, Loading, PageHeader, StatCard } from "@/components/common";
import { api } from "@/lib/api";
import { STATUS_META, downloadCSV, firstOfMonth, fmtDateTime, jktToday, rupiah, ymdToDisplay } from "@/lib/format";

export default function RekapPage() {
  const [from, setFrom] = useState(firstOfMonth());
  const [to, setTo] = useState(jktToday());
  const params = { date_from: from, date_to: to };
  const { data, isLoading } = useQuery({ queryKey: ["rekap", params], queryFn: () => api.get("/reports/reseller", { params }).then((r) => r.data), staleTime: 0, enabled: !!from && !!to && from <= to });

  const columns: ColumnDef<any>[] = [
    { accessorKey: "created_at", header: "Tanggal Order", cell: (c) => fmtDateTime(c.getValue()) },
    { accessorKey: "code", header: "Kode Order", cell: ({ row }) => <Link to={`/app/orders/${row.original.id}`} className="font-mono font-semibold text-blue-700 hover:underline" data-testid={`rekap-link-${row.original.code}`}>{row.original.code}</Link> },
    { accessorKey: "status", header: "Status", cell: (c) => <StatusBadge status={c.getValue()} /> },
    { accessorKey: "total_qty", header: "Total Qty" },
    { accessorKey: "grand_total", header: "Nilai Order", cell: (c) => <span className="tabular-nums">{rupiah(c.getValue())}</span> },
    { accessorKey: "total_paid", header: "Total Pembayaran", cell: (c) => <span className="tabular-nums">{rupiah(c.getValue())}</span> },
    { accessorKey: "remaining", header: "Sisa Tagihan", cell: (c) => <span className="font-semibold tabular-nums">{rupiah(c.getValue())}</span> },
  ];

  const exportCsv = () => {
    if (!data) return;
    downloadCSV(`rekap-order-${from}-sd-${to}.csv`, ["Tanggal Order", "Kode Order", "Status", "Total Qty", "Nilai Order", "Total Pembayaran", "Sisa Tagihan"],
      data.rows.map((r: any) => [fmtDateTime(r.created_at), r.code, STATUS_META[r.status]?.label, r.total_qty, r.grand_total, r.total_paid, r.remaining]));
  };

  return (
    <div className="space-y-5">
      <PageHeader title="Rekap Order" subtitle="Rekap berdasarkan tanggal order dibuat." actions={
        <Button variant="outline" onClick={exportCsv} disabled={!data?.rows?.length} data-testid="rekap-export-csv"><Download /> Ekspor CSV</Button>} />
      <div className="grid grid-cols-2 gap-3 rounded-xl border border-slate-200 bg-white p-4 sm:max-w-md">
        <Field label="Dari Tanggal"><DateInput value={from} onChange={setFrom} testid="rekap-date-from" /></Field>
        <Field label="Sampai Tanggal"><DateInput value={to} onChange={setTo} testid="rekap-date-to" /></Field>
      </div>
      <div className="flex gap-2 rounded-xl border border-blue-200 bg-blue-50 p-3 text-sm text-blue-900" data-testid="rekap-info">
        <Info className="mt-0.5 h-4 w-4 shrink-0" />
        <p>Filter tanggal berlaku untuk <b>tanggal order dibuat</b>. Total pembayaran mencakup <b>seluruh pembayaran</b> yang tercatat untuk order-order tersebut, termasuk pembayaran yang dilakukan di luar rentang tanggal ini. Semua nilai memakai harga saat order dibuat.</p>
      </div>
      {isLoading || !data ? <Loading /> : (
        <>
          <p className="text-sm text-slate-500">Periode {ymdToDisplay(data.date_from)} s/d {ymdToDisplay(data.date_to)}</p>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
            <StatCard label="Jumlah Order" value={data.summary.order_count} testid="rekap-order-count" />
            <StatCard label="Total Qty Produk" value={`${data.summary.total_qty} pcs`} testid="rekap-total-qty" />
            <StatCard label="Total Nilai Order" value={rupiah(data.summary.total_order)} testid="rekap-total-order" />
            <StatCard label="Total Pembayaran" value={rupiah(data.summary.total_paid)} testid="rekap-total-paid" />
            <StatCard label="Sisa Pembayaran" value={rupiah(data.summary.remaining)} hint={data.summary.overpaid ? `Kelebihan bayar ${rupiah(data.summary.overpaid)}` : undefined} testid="rekap-remaining" />
          </div>
          <DataTable testid="rekap-table" data={data.rows} columns={columns} pageSize={20} emptyText="Tidak ada order pada periode ini."
            mobileCard={(r: any) => (
              <div>
                <div className="flex items-start justify-between gap-2">
                  <Link to={`/app/orders/${r.id}`} className="font-mono text-sm font-bold text-blue-700">{r.code}</Link><StatusBadge status={r.status} />
                </div>
                <p className="text-xs text-slate-500">{fmtDateTime(r.created_at)}</p>
                <MobileRow label="Nilai Order">{rupiah(r.grand_total)}</MobileRow>
                <MobileRow label="Sisa Tagihan">{rupiah(r.remaining)}</MobileRow>
              </div>
            )}
            mobileDetail={(r: any) => <div><MobileRow label="Total Qty">{r.total_qty} pcs</MobileRow><MobileRow label="Total Pembayaran">{rupiah(r.total_paid)}</MobileRow></div>} />
        </>
      )}
    </div>
  );
}
