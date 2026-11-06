import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { Zap } from "lucide-react";
import { API_BASE, api } from "@/lib/api";
import { cn } from "@/lib/utils";

export type Branding = { app_name: string; tagline: string; logo_file: string | null; favicon_file: string | null; updated_at?: string | null };

export const DEFAULT_BRANDING: Branding = { app_name: "RelayLab OMS", tagline: "Autolight Order System", logo_file: null, favicon_file: null };

export const brandingFileUrl = (name: string) => `${API_BASE}/branding/files/${encodeURIComponent(name)}`;

export function useBranding(): Branding {
  const { data } = useQuery({ queryKey: ["branding"], queryFn: () => api.get("/branding").then((r) => r.data as Branding), staleTime: 300_000 });
  return data || DEFAULT_BRANDING;
}

/** Judul tab & favicon mengikuti branding tanpa rebuild frontend. */
export function BrandingHead() {
  const b = useBranding();
  useEffect(() => {
    document.title = b.app_name;
    let link = document.querySelector<HTMLLinkElement>("link[rel='icon']");
    if (!link) {
      link = document.createElement("link");
      link.rel = "icon";
      document.head.appendChild(link);
    }
    link.href = b.favicon_file ? brandingFileUrl(b.favicon_file) : `${process.env.PUBLIC_URL}/favicon.svg`;
  }, [b.app_name, b.favicon_file]);
  return null;
}

export function BrandMark({ className, iconClass, testid }: { className?: string; iconClass?: string; testid?: string }) {
  const b = useBranding();
  if (b.logo_file)
    return <img src={brandingFileUrl(b.logo_file)} alt={b.app_name} className={cn("object-contain", className)} data-testid={testid} />;
  return (
    <span className={cn("flex items-center justify-center rounded-lg bg-blue-700 text-white", className)} data-testid={testid}>
      <Zap className={iconClass || "h-5 w-5"} />
    </span>
  );
}
