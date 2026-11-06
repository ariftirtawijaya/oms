import { useQuery } from "@tanstack/react-query";
import { ShieldAlert } from "lucide-react";
import { api } from "@/lib/api";

/** Banner admin bila pembersihan data terputus dan perubahan data sedang diblokir. */
export function MaintenanceBanner() {
  const { data } = useQuery({
    queryKey: ["cleanup-status"], queryFn: () => api.get("/settings/cleanup/status").then((r) => r.data),
    refetchInterval: 60_000, staleTime: 0,
  });
  if (!data?.blocked) return null;
  return (
    <div className="mb-5 flex gap-3 rounded-xl border border-red-300 bg-red-50 p-4 text-sm text-red-800" role="alert" data-testid="maintenance-blocked-banner">
      <ShieldAlert className="mt-0.5 h-5 w-5 shrink-0" />
      <div>
        <p className="font-semibold">Perubahan data diblokir sementara</p>
        <p data-testid="maintenance-blocked-message">{data.blocked.message}</p>
        {data.blocked.backup && <p className="mt-1 break-all font-mono text-xs" data-testid="maintenance-blocked-backup">Backup: {data.blocked.backup}</p>}
      </div>
    </div>
  );
}
