import React from "react";
import { cn } from "@/lib/utils";

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: string; actions?: React.ReactNode }) {
  return (
    <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <h1 className="font-heading text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl" data-testid="page-title">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-slate-500">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </div>
  );
}

export function StatCard({ label, value, hint, icon, tone = "slate", testid }: {
  label: string; value: React.ReactNode; hint?: string; icon?: React.ReactNode; tone?: string; testid?: string;
}) {
  const tones: Record<string, string> = {
    slate: "bg-slate-100 text-slate-700", blue: "bg-blue-100 text-blue-700", amber: "bg-amber-100 text-amber-700",
    green: "bg-emerald-100 text-emerald-700", red: "bg-red-100 text-red-700", violet: "bg-violet-100 text-violet-700",
  };
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm sm:p-5" data-testid={testid}>
      <div className="flex items-start justify-between gap-3">
        <p className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</p>
        {icon && <span className={cn("flex h-8 w-8 shrink-0 items-center justify-center rounded-lg", tones[tone])}>{icon}</span>}
      </div>
      <p className="mt-2 font-heading text-xl font-bold tracking-tight text-slate-900 tabular-nums sm:text-2xl" data-testid={testid ? `${testid}-value` : undefined}>{value}</p>
      {hint && <p className="mt-1 text-xs text-slate-500">{hint}</p>}
    </div>
  );
}

export function Section({ title, children, actions, className, testid }: {
  title?: string; children: React.ReactNode; actions?: React.ReactNode; className?: string; testid?: string;
}) {
  return (
    <section className={cn("rounded-xl border border-slate-200 bg-white shadow-sm", className)} data-testid={testid}>
      {(title || actions) && (
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 px-4 py-3 sm:px-5">
          {title && <h2 className="font-heading text-base font-bold text-slate-900">{title}</h2>}
          {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
        </div>
      )}
      <div className="p-4 sm:p-5">{children}</div>
    </section>
  );
}

export function Empty({ text, testid }: { text: string; testid?: string }) {
  return <p className="rounded-lg border border-dashed border-slate-200 bg-slate-50 p-6 text-center text-sm text-slate-500" data-testid={testid}>{text}</p>;
}

export function Loading() {
  return (
    <div className="flex items-center gap-3 p-8 text-sm text-slate-500" data-testid="loading-indicator">
      <span className="h-4 w-4 animate-spin rounded-full border-2 border-blue-600 border-t-transparent" /> Memuat data...
    </div>
  );
}

export function Field({ label, error, children, hint }: { label: string; error?: string; children: React.ReactNode; hint?: string }) {
  return (
    <div className="space-y-1.5">
      <label className="text-sm font-medium text-slate-700">{label}</label>
      {children}
      {hint && !error && <p className="text-xs text-slate-500">{hint}</p>}
      {error && <p className="text-xs font-medium text-red-600" data-testid="field-error">{error}</p>}
    </div>
  );
}
