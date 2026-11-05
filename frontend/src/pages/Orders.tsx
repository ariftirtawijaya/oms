import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ColumnDef } from "@tanstack/react-table";
import { Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { DataTable, MobileRow } from "@/components/DataTable";
import { PaymentBadge, PricePendingBadge, StatusBadge } from "@/components/badges";
import { Loading, PageHeader } from "@/components/common";
import { api } from "@/lib/api";
import { PAYMENT_META, STATUS_META, fmtDateTime, rupiah } from "@/lib/format";

export function orderColumns(admin: boolean, base: string): ColumnDef<any>[] {
  const cols: ColumnDef<any>[] = [
    { accessorKey: "created_at", header: "Tanggal", cell: (c) => fmtDateTime(c.getValue()) },
    { accessorKey: "code", header: "Kode Order", cell: ({ row }) => (
      <Link to={`${base}/${row.original.id}`} className="font-mono text-sm font-semibold text-blue-700 hover:underline" data-testid={`order-link-${row.original.code}`}>{row.original.code}</Link>) },
  ];
  if (admin) cols.push({ id: "reseller", accessorFn: (o) => o.reseller_snapshot?.name, header: "Reseller" });
  cols.push(
    { accessorKey: "total_qty", header: "Total Qty", cell: (c) => <span className="tabular-nums">{c.getValue()}</span> },
    { accessorKey: "grand_total", header: "Nilai Order", cell: ({ row }) => (
      <span className="tabular-nums">{rupiah(row.original.grand_total)}{row.original.price_pending && <span className="ml-1 text-xs text-orange-600">*</span>}</span>) },
    { accessorKey: "total_paid", header: "Dibayar", cell: (c) => <span className="tabular-nums">{rupiah(c.getValue())}</span> },
    { accessorKey: "remaining", header: "Sisa Tagihan", cell: (c) => <span className="font-semibold tabular-nums">{rupiah(c.getValue())}</span> },
    { accessorKey: "status", header: "Status", cell: (c) => <StatusBadge status={c.getValue()} /> },
    { accessorKey: "payment_status", header: "Pembayaran", cell: (c) => <PaymentBadge status={c.getValue()} /> },
    { id: "aksi", header: "", enableSorting: false, cell: ({ row }) => (
      <Button asChild size="sm" variant="outline"><Link to={`${base}/${row.original.id}`} data-testid={`order-detail-btn-${row.original.code}`}>Detail</Link></Button>) },
  );
  return cols;
}

export function OrderMobileCard({ o, base, admin }: { o: any; base: string; admin?: boolean }) {
  return (
    <Link to={`${base}/${o.id}`} className="block" data-testid={`order-card-${o.code}`}>
      <div className="flex items-start justify-between gap-2">
        <div><p className="font-mono text-sm font-bold text-blue-700">{o.code}</p><p className="text-xs text-slate-500">{fmtDateTime(o.created_at)}{admin ? ` • ${o.reseller_snapshot?.name}` : ""}</p></div>
        <StatusBadge status={o.status} />
      </div>
      <div className="mt-2">
        <MobileRow label="Nilai Order">{rupiah(o.grand_total)}</MobileRow>
        <MobileRow label="Sisa Tagihan">{rupiah(o.remaining)}</MobileRow>
      </div>
      <div className="mt-1 flex flex-wrap gap-1"><PaymentBadge status={o.payment_status} />{o.price_pending && <PricePendingBadge />}</div>
    </Link>
  );
}

export const OrderMobileDetail = ({ o }: { o: any }) => (
  <div><MobileRow label="Total Qty">{o.total_qty} pcs</MobileRow><MobileRow label="Sudah Dibayar">{rupiah(o.total_paid)}</MobileRow></div>
);

export default function OrdersPage({ admin }: { admin?: boolean }) {
  const [status, setStatus] = useState("semua");
  const [pay, setPay] = useState("semua");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const params: any = {};
  if (status !== "semua") params.status = status;
  if (from) params.date_from = from;
  if (to) params.date_to = to;
  const { data = [], isLoading } = useQuery({ queryKey: ["orders", params], queryFn: () => api.get("/orders", { params }).then((r) => r.data), staleTime: 0 });
  const rows = pay === "semua" ? data : data.filter((o: any) => o.payment_status === pay);
  const base = admin ? "/admin/orders" : "/app/orders";

  const toolbar = (
    <div className="grid w-full grid-cols-2 gap-2 sm:flex sm:w-auto">
      <Select value={status} onValueChange={setStatus}>
        <SelectTrigger className="h-10 bg-white sm:w-48" data-testid="orders-status-filter"><SelectValue /></SelectTrigger>
        <SelectContent><SelectItem value="semua">Semua Status</SelectItem>{Object.entries(STATUS_META).map(([k, v]) => <SelectItem key={k} value={k}>{v.label}</SelectItem>)}</SelectContent>
      </Select>
      <Select value={pay} onValueChange={setPay}>
        <SelectTrigger className="h-10 bg-white sm:w-48" data-testid="orders-payment-filter"><SelectValue /></SelectTrigger>
        <SelectContent><SelectItem value="semua">Semua Pembayaran</SelectItem>{Object.entries(PAYMENT_META).map(([k, v]) => <SelectItem key={k} value={k}>{v.label}</SelectItem>)}</SelectContent>
      </Select>
      <Input type="date" value={from} onChange={(e) => setFrom(e.target.value)} className="h-10 bg-white" aria-label="Dari tanggal" data-testid="orders-date-from" />
      <Input type="date" value={to} onChange={(e) => setTo(e.target.value)} className="h-10 bg-white" aria-label="Sampai tanggal" data-testid="orders-date-to" />
    </div>
  );

  return (
    <div>
      <PageHeader title={admin ? "Daftar Order" : "Order Saya"} subtitle="Nilai order dihitung dari harga snapshot saat order dibuat. Tanda * berarti ada item custom yang harganya belum ditetapkan."
        actions={<Button asChild className="bg-blue-700 text-white hover:bg-blue-800"><Link to={admin ? "/admin/orders/baru" : "/app/order-baru"} data-testid="orders-new-button"><Plus /> Buat Order</Link></Button>} />
      {isLoading ? <Loading /> : (
        <DataTable testid="orders-table" data={rows} columns={orderColumns(!!admin, base)} toolbar={toolbar}
          searchPlaceholder={admin ? "Cari kode order atau reseller..." : "Cari kode order..."}
          searchText={(o: any) => `${o.code} ${o.reseller_snapshot?.name || ""}`}
          mobileCard={(o: any) => <OrderMobileCard o={o} base={base} admin={admin} />}
          mobileDetail={(o: any) => <OrderMobileDetail o={o} />}
          emptyText="Belum ada order." />
      )}
    </div>
  );
}
