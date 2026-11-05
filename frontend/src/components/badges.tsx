import { Badge } from "@/components/ui/badge";
import { NOTIF_META, PAYMENT_META, STATUS_META } from "@/lib/format";
import { cn } from "@/lib/utils";

function Pill({ meta, testid }: { meta: { label: string; cls: string }; testid?: string }) {
  return (
    <Badge variant="outline" data-testid={testid} className={cn("whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-semibold", meta.cls)}>
      {meta.label}
    </Badge>
  );
}

export const StatusBadge = ({ status, testid }: { status: string; testid?: string }) => (
  <Pill meta={STATUS_META[status] || { label: status, cls: "" }} testid={testid || "order-status-badge"} />
);

export const PaymentBadge = ({ status, testid }: { status: string; testid?: string }) => (
  <Pill meta={PAYMENT_META[status] || { label: status, cls: "" }} testid={testid || "payment-status-badge"} />
);

export const NotifBadge = ({ status }: { status: string }) => (
  <Pill meta={NOTIF_META[status] || { label: status, cls: "" }} testid="notif-status-badge" />
);

export const PricePendingBadge = () => (
  <Pill meta={{ label: "Harga Belum Final", cls: "bg-orange-100 text-orange-800 border-orange-200" }} testid="price-pending-badge" />
);
