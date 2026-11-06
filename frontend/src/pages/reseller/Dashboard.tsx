import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Banknote, CheckCircle2, ClipboardList, Clock, Factory, Package, ShoppingCart, Wallet } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Loading, PageHeader, Section, StatCard } from "@/components/common";
import { DataTable } from "@/components/DataTable";
import { OrderMobileCard, orderColumns } from "@/pages/Orders";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { rupiah } from "@/lib/format";

export default function ResellerDashboard() {
  const { user } = useAuth();
  const { data, isLoading } = useQuery({ queryKey: ["dashboard"], queryFn: () => api.get("/dashboard").then((r) => r.data), staleTime: 0 });
  if (isLoading || !data) return <Loading />;
  return (
    <div className="space-y-6 fade-up">
      <PageHeader title={`Halo, ${user ? user.name : ""}`} subtitle="Ringkasan order dan tagihan anda di RelayLab."
        actions={<Button asChild className="h-11 bg-blue-700 text-white hover:bg-blue-800"><Link to="/app/order-baru" data-testid="dashboard-new-order"><ShoppingCart /> Buat Order Baru</Link></Button>} />
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatCard label="Total Order" value={data.order_count} icon={<ClipboardList className="h-4 w-4" />} testid="stat-orders" />
        <StatCard label="Menunggu Konfirmasi" value={data.by_status.menunggu_konfirmasi} icon={<Clock className="h-4 w-4" />} tone="amber" testid="stat-waiting" />
        <StatCard label="Diproses" value={data.by_status.diproses} icon={<Factory className="h-4 w-4" />} tone="blue" testid="stat-processing" />
        <StatCard label="Selesai" value={data.by_status.selesai} icon={<CheckCircle2 className="h-4 w-4" />} tone="green" testid="stat-done" />
        <StatCard label="Total Qty Produk" value={`${data.total_qty} pcs`} icon={<Package className="h-4 w-4" />} testid="stat-qty" />
        <StatCard label="Total Nilai Order" value={rupiah(data.total_order)} icon={<Wallet className="h-4 w-4" />} tone="blue" testid="stat-total-order" />
        <StatCard label="Total Pembayaran" value={rupiah(data.total_paid)} icon={<Banknote className="h-4 w-4" />} tone="green" testid="stat-total-paid" />
        <StatCard label="Sisa Tagihan" value={rupiah(data.remaining)} tone="red" hint={data.overpaid ? `Kelebihan bayar: ${rupiah(data.overpaid)}` : undefined} testid="stat-remaining" />
      </div>
      <Section title="Order Terbaru" actions={<Link to="/app/orders" className="text-sm font-medium text-blue-700 hover:underline">Lihat semua</Link>}>
        <DataTable testid="recent-orders" data={data.recent} columns={orderColumns(false, "/app/orders")}
          mobileCard={(o: any) => <OrderMobileCard o={o} base="/app/orders" />} emptyText="Belum ada order. Yuk buat order pertama anda." />
      </Section>
    </div>
  );
}
