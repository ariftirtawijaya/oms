import React, { useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import {
  BarChart3, Bell, ClipboardList, FileText, KeyRound, LayoutDashboard, LogOut, Menu, Package, PlusCircle,
  ScrollText, ShoppingCart, Store, UserCircle, Users, Zap,
} from "lucide-react";
import { Sheet, SheetContent, SheetTitle } from "@/components/ui/sheet";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";

type Item = { to: string; label: string; icon: React.ElementType; end?: boolean };

const ADMIN_NAV: Item[] = [
  { to: "/admin", label: "Dashboard", icon: LayoutDashboard, end: true },
  { to: "/admin/orders", label: "Daftar Order", icon: ClipboardList },
  { to: "/admin/orders/baru", label: "Buat Order", icon: PlusCircle },
  { to: "/admin/products", label: "Produk", icon: Package },
  { to: "/admin/resellers", label: "Reseller", icon: Store },
  { to: "/admin/users", label: "User Login", icon: Users },
  { to: "/admin/reports", label: "Laporan", icon: BarChart3 },
  { to: "/admin/notifications", label: "Notifikasi WA", icon: Bell },
  { to: "/admin/audit", label: "Log Audit", icon: ScrollText },
];

const RESELLER_NAV: Item[] = [
  { to: "/app", label: "Dashboard", icon: LayoutDashboard, end: true },
  { to: "/app/order-baru", label: "Buat Order", icon: ShoppingCart },
  { to: "/app/orders", label: "Order Saya", icon: ClipboardList },
  { to: "/app/rekap", label: "Rekap Order", icon: FileText },
  { to: "/app/profil", label: "Profil", icon: UserCircle },
];

function NavList({ items, onNav }: { items: Item[]; onNav?: () => void }) {
  return (
    <nav className="space-y-1">
      {items.map((it) => (
        <NavLink key={it.to} to={it.to} end={it.end} onClick={onNav}
          data-testid={`nav-${it.to.replace(/\//g, "-").slice(1)}`}
          className={({ isActive }) => cn(
            "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors",
            isActive ? "bg-blue-50 text-blue-700" : "text-slate-600 hover:bg-slate-100 hover:text-slate-900")}>
          <it.icon className="h-4 w-4" /> {it.label}
        </NavLink>
      ))}
    </nav>
  );
}

function Brand() {
  return (
    <div className="flex items-center gap-2.5">
      <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-blue-700 text-white"><Zap className="h-5 w-5" /></span>
      <div className="leading-tight">
        <p className="font-heading text-base font-extrabold tracking-tight text-slate-900">RelayLab OMS</p>
        <p className="text-[11px] text-slate-500">Autolight Order System</p>
      </div>
    </div>
  );
}

function UserBox({ onNav }: { onNav?: () => void }) {
  const { user, logout } = useAuth();
  const nav = useNavigate();
  if (!user) return null;
  return (
    <div className="space-y-1 border-t border-slate-200 pt-4">
      <div className="px-3 pb-2">
        <p className="truncate text-sm font-semibold text-slate-900" data-testid="current-user-name">{user.name}</p>
        <p className="truncate text-xs text-slate-500">{user.role === "admin" ? "Administrator" : "Reseller"}</p>
      </div>
      <button onClick={() => { onNav?.(); nav("/ganti-password"); }} data-testid="nav-change-password"
        className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm text-slate-600 hover:bg-slate-100">
        <KeyRound className="h-4 w-4" /> Ganti Password
      </button>
      <button onClick={async () => { await logout(); nav("/login"); }} data-testid="logout-button"
        className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm text-red-600 hover:bg-red-50">
        <LogOut className="h-4 w-4" /> Keluar
      </button>
    </div>
  );
}

export default function AppLayout() {
  const { user } = useAuth();
  const [open, setOpen] = useState(false);
  const items = user && user.role === "admin" ? ADMIN_NAV : RESELLER_NAV;
  return (
    <div className="min-h-screen bg-slate-50">
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-64 flex-col border-r border-slate-200 bg-white p-4 lg:flex">
        <div className="mb-6 px-1"><Brand /></div>
        <div className="flex-1 overflow-y-auto"><NavList items={items} /></div>
        <UserBox />
      </aside>
      <header className="sticky top-0 z-20 flex h-14 items-center justify-between border-b border-slate-200 bg-white/70 px-4 backdrop-blur-xl lg:hidden">
        <Brand />
        <button onClick={() => setOpen(true)} className="rounded-lg p-2 hover:bg-slate-100" aria-label="Buka menu" data-testid="mobile-menu-button">
          <Menu className="h-5 w-5" />
        </button>
      </header>
      <Sheet open={open} onOpenChange={setOpen}>
        <SheetContent side="left" className="flex w-72 flex-col p-4">
          <SheetTitle className="sr-only">Menu</SheetTitle>
          <div className="mb-6"><Brand /></div>
          <div className="flex-1 overflow-y-auto"><NavList items={items} onNav={() => setOpen(false)} /></div>
          <UserBox onNav={() => setOpen(false)} />
        </SheetContent>
      </Sheet>
      <main className="px-4 py-6 sm:px-6 lg:ml-64 lg:px-10 lg:py-8">
        <div className="mx-auto max-w-[1500px]"><Outlet /></div>
      </main>
    </div>
  );
}
