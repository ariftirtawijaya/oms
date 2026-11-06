import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { ColumnDef, SortingState } from "@tanstack/react-table";
import { usePageSize } from "@/components/Pager";
import { Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { DateInput } from "@/components/DateInput";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { DataTable, MobileRow } from "@/components/DataTable";
import { PaymentBadge, PricePendingBadge, StatusBadge } from "@/components/badges";
import { Loading, PageHeader } from "@/components/common";
import { api } from "@/lib/api";
import { PAYMENT_META, STATUS_META, fmtDateTime, rupiah } from "@/lib/format";

export function orderColumns(admin: boolean, base: string): ColumnDef<any, any>[] {
  const cols: ColumnDef<any, any>[] = [
    { accessorKey: "created_at", header: "Tanggal", cell: (c) => fmtDateTime(c.getValue()) },
    { accessorKey: "code", header: "Kode Order", cell: ({ row }) => (
      <Link to={`${base}/${row.original.id}`} className="font-mono text-sm font-semibold text-blue-700 hover:underline" data-testid={`order-link-${row.original.code}`}>{row.original.code}</Link>) },
  ];
  if (admin) cols.push({ id: "reseller", accessorFn: (o) => o.reseller_snapshot?.name, header: "Reseller" });
  cols.push(
    { accessorKey: "total_qty", header: "Total Qty", cell: (c) => <span className="tabular-nums">{c.getValue()}</span> },
    { accessorKey: "grand_total", header: "Nilai Order", cell: ({ row }) => (
      <span className="tabular-nums">{rupiah(row.original.grand_total)}</span>) },
    { accessorKey: "total_paid", header: "Dibayar", cell: (c) => <span className="tabular-nums">{rupiah(c.getValue())}</span> },
    { accessorKey: "remaining", header: "Sisa Tagihan", cell: (c) => <span className="font-semibold tabular-nums">{rupiah(c.getValue())}</span> },
    { accessorKey: "status", header: "Status", cell: ({ row }) => (
      <div className="flex flex-col items-start gap-1"><StatusBadge status={row.original.status} /><PaymentBadge status={row.original.payment_status} />{row.original.price_pending && <PricePendingBadge />}</div>) },
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
  const [search, setSearch] = useState("");
  const [q, setQ] = useState("");
  const [sorting, setSorting] = useState<SortingState>([]);
  const [pageSize, setPageSize] = usePageSize("orders-table");
  const [page, setPage] = useState(1);
  useEffect(() => { const t = setTimeout(() => setQ(search.trim()), 350); return () => clearTimeout(t); }, [search]);
  useEffect(() => { setPage(1); }, [status, pay, from, to, q, pageSize, sorting]);
  const params: any = { page, limit: pageSize };
  if (status !== "semua") params.status = status;
  if (pay !== "semua") params.payment_status = pay;
  if (from) params.date_from = from;
  if (to) params.date_to = to;
  if (q) params.q = q;
  if (sorting[0]) { params.sort = sorting[0].id; params.order = sorting[0].desc ? "desc" : "asc"; }
  const { data, isLoading } = useQuery({ queryKey: ["orders", params], queryFn: () => api.get("/orders", { params }).then((r) => r.data), staleTime: 0, placeholderData: keepPreviousData });
  useEffect(() => { if (data && data.page !== page) setPage(data.page); }, [data, page]);
  const base = admin ? "/admin/orders" : "/app/orders";
  const sortable = new Set(["created_at", "code", "total_qty", "grand_total", "total_paid", "status"]);
  const columns = orderColumns(!!admin, base).map((c: any) => ({ ...c, enableSorting: sortable.has(c.accessorKey) }));

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
      <div className="sm:w-40"><DateInput value={from} onChange={setFrom} testid="orders-date-from" placeholder="Dari tanggal" /></div>
      <div className="sm:w-40"><DateInput value={to} onChange={setTo} testid="orders-date-to" placeholder="Sampai tanggal" /></div>
    </div>
  );

  return (
    <div>
      <PageHeader title={admin ? "Daftar Order" : "Order Saya"}
        actions={<Button asChild className="bg-blue-700 text-white hover:bg-blue-800"><Link to={admin ? "/admin/orders/baru" : "/app/order-baru"} data-testid="orders-new-button"><Plus /> Buat Order</Link></Button>} />
      {isLoading && !data ? <Loading /> : (
        <DataTable testid="orders-table" data={data?.items || []} columns={columns} toolbar={toolbar}
          searchPlaceholder={admin ? "Cari kode order atau reseller..." : "Cari kode order..."}
          server={{ total: data?.total || 0, page: data?.page || page, pageSize, onPage: setPage, onPageSize: setPageSize, search, onSearch: setSearch, sorting, onSorting: setSorting }}
          mobileCard={(o: any) => <OrderMobileCard o={o} base={base} admin={admin} />}
          mobileDetail={(o: any) => <OrderMobileDetail o={o} />}
          emptyText="Belum ada order." />
      )}
    </div>
  );
}
