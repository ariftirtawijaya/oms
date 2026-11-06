import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Area, AreaChart, Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { AlertTriangle, Banknote, CheckCircle2, ClipboardList, Clock, Factory, Package, Star, Store, Wallet } from "lucide-react";
import { Loading, PageHeader, Section, StatCard } from "@/components/common";
import { OrderMobileCard, orderColumns } from "@/pages/Orders";
import { DataTable } from "@/components/DataTable";
import { api } from "@/lib/api";
import { rupiah } from "@/lib/format";

const shortDate = (d: string) => `${d.slice(8, 10)}/${d.slice(5, 7)}`;
const compact = (n: number) => (n >= 1e6 ? `${(n / 1e6).toFixed(1).replace(".", ",")}jt` : n >= 1e3 ? `${Math.round(n / 1e3)}rb` : String(n));

export default function AdminDashboard() {
  const { data, isLoading } = useQuery({ queryKey: ["dashboard"], queryFn: () => api.get("/dashboard").then((r) => r.data), staleTime: 0 });
  if (isLoading || !data) return <Loading />;
  return (
    <div className="space-y-6 fade-up">
      <PageHeader title="Dashboard Admin" subtitle="Ringkasan operasional RelayLab. Semua nilai memakai harga snapshot transaksi." />
      {data.failed_notifications > 0 && (
        <Link to="/admin/notifications" className="flex items-center gap-2 rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-800" data-testid="failed-notif-alert">
          <AlertTriangle className="h-4 w-4" /> {data.failed_notifications} notifikasi WhatsApp gagal terkirim. Klik untuk melihat dan kirim ulang.
        </Link>
      )}
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatCard label="Total Reseller" value={data.reseller_count} icon={<Store className="h-4 w-4" />} tone="slate" testid="stat-resellers" />
        <StatCard label="Special Reseller" value={data.special_count} icon={<Star className="h-4 w-4" />} tone="violet" testid="stat-special" />
        <StatCard label="Produk Aktif" value={data.active_products} icon={<Package className="h-4 w-4" />} tone="blue" testid="stat-products" />
        <StatCard label="Total Order" value={data.order_count} icon={<ClipboardList className="h-4 w-4" />} tone="slate" testid="stat-orders" />
        <StatCard label="Menunggu Konfirmasi" value={data.by_status.menunggu_konfirmasi} icon={<Clock className="h-4 w-4" />} tone="amber" testid="stat-waiting" />
        <StatCard label="Diproses" value={data.by_status.diproses} icon={<Factory className="h-4 w-4" />} tone="blue" testid="stat-processing" />
        <StatCard label="Selesai" value={data.by_status.selesai} icon={<CheckCircle2 className="h-4 w-4" />} tone="green" testid="stat-done" />
        <StatCard label="Total Nilai Order" value={rupiah(data.total_order)} icon={<Wallet className="h-4 w-4" />} tone="blue" testid="stat-total-order" />
        <StatCard label="Pembayaran Masuk" value={rupiah(data.total_paid)} icon={<Banknote className="h-4 w-4" />} tone="green" testid="stat-total-paid" />
        <StatCard label="Total Piutang Reseller" value={rupiah(data.remaining)} icon={<AlertTriangle className="h-4 w-4" />} tone="red" testid="stat-receivable" />
      </div>
      <div className="grid gap-5 lg:grid-cols-2">
        <Section title="Jumlah Order 30 Hari Terakhir">
          <div className="h-64" data-testid="orders-count-chart">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data.chart}>
                <CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" vertical={false} />
                <XAxis dataKey="date" tickFormatter={shortDate} fontSize={11} interval={4} />
                <YAxis allowDecimals={false} fontSize={11} width={30} />
                <Tooltip labelFormatter={(d: any) => shortDate(d)} formatter={(v: any) => [v, "Order"]} />
                <Bar dataKey="count" fill="#1D4ED8" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Section>
        <Section title="Nilai Order 30 Hari Terakhir">
          <div className="h-64" data-testid="orders-value-chart">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={data.chart}>
                <CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" vertical={false} />
                <XAxis dataKey="date" tickFormatter={shortDate} fontSize={11} interval={4} />
                <YAxis tickFormatter={compact} fontSize={11} width={45} />
                <Tooltip labelFormatter={(d: any) => shortDate(d)} formatter={(v: any) => [rupiah(v), "Nilai"]} />
                <Area dataKey="value" stroke="#10B981" fill="#D1FAE5" strokeWidth={2} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </Section>
      </div>
      <Section title="Order Terbaru" actions={<Link to="/admin/orders" className="text-sm font-medium text-blue-700 hover:underline">Lihat semua</Link>}>
        <DataTable testid="recent-orders" data={data.recent} columns={orderColumns(true, "/admin/orders")}
          mobileCard={(o: any) => <OrderMobileCard o={o} base="/admin/orders" admin />} emptyText="Belum ada order." />
      </Section>
    </div>
  );
}
