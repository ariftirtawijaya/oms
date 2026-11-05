import { useQuery } from "@tanstack/react-query";
import { ColumnDef } from "@tanstack/react-table";
import { DataTable, MobileRow } from "@/components/DataTable";
import { Loading, PageHeader } from "@/components/common";
import { api } from "@/lib/api";
import { fmtDateTime } from "@/lib/format";

const label = (a: string) => a.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());

export default function AuditPage() {
  const { data = [], isLoading } = useQuery({ queryKey: ["audit"], queryFn: () => api.get("/audit-logs").then((r) => r.data), staleTime: 0 });
  const columns: ColumnDef<any>[] = [
    { accessorKey: "created_at", header: "Waktu", cell: (c) => fmtDateTime(c.getValue()) },
    { accessorKey: "actor_name", header: "Pengguna" },
    { accessorKey: "action", header: "Aksi", cell: (c) => <span className="font-medium">{label(c.getValue())}</span> },
    { accessorKey: "entity", header: "Data" },
    { id: "detail", header: "Detail", cell: ({ row }) => <code className="block max-w-[420px] truncate text-xs text-slate-600">{JSON.stringify(row.original.data)}</code> },
  ];
  return (
    <div>
      <PageHeader title="Log Audit" subtitle="Catatan perubahan data penting: harga, pembayaran, status, pengiriman, dan akun (500 terbaru)." />
      {isLoading ? <Loading /> : (
        <DataTable testid="audit-table" data={data} columns={columns} pageSize={20} searchText={(a: any) => `${a.action} ${a.actor_name} ${JSON.stringify(a.data)}`}
          mobileCard={(a: any) => <div><p className="text-sm font-semibold">{label(a.action)}</p><MobileRow label={fmtDateTime(a.created_at)}>{a.actor_name}</MobileRow></div>}
          mobileDetail={(a: any) => <code className="block whitespace-pre-wrap break-all text-xs">{JSON.stringify(a.data, null, 1)}</code>} />
      )}
    </div>
  );
}
