import React from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import "@/App.css";
import { Toaster } from "@/components/ui/sonner";
import { AuthProvider, useAuth } from "@/lib/auth";
import AppLayout from "@/components/AppLayout";
import { Loading } from "@/components/common";
import LoginPage from "@/pages/Login";
import ChangePasswordPage from "@/pages/ChangePassword";
import AdminDashboard from "@/pages/admin/Dashboard";
import ProductsPage from "@/pages/admin/Products";
import ResellersPage from "@/pages/admin/Resellers";
import UsersPage from "@/pages/admin/Users";
import AdminOrderNew from "@/pages/admin/OrderNew";
import ReportsPage from "@/pages/admin/Reports";
import NotificationsPage from "@/pages/admin/Notifications";
import AuditPage from "@/pages/admin/Audit";
import OrdersPage from "@/pages/Orders";
import OrderDetailPage from "@/pages/OrderDetail";
import ResellerDashboard from "@/pages/reseller/Dashboard";
import OrderCreatePage from "@/pages/reseller/OrderCreate";
import RekapPage from "@/pages/reseller/Rekap";
import ProfilePage from "@/pages/reseller/Profile";

function Guard({ role, children }: { role?: "admin" | "reseller"; children: React.ReactElement }) {
  const { user } = useAuth();
  if (user === null) return <Loading />;
  if (!user) return <Navigate to="/login" replace />;
  if (user.must_change_password) return <Navigate to="/ganti-password" replace />;
  if (role && user.role !== role) return <Navigate to={user.role === "admin" ? "/admin" : "/app"} replace />;
  return children;
}

function Home() {
  const { user } = useAuth();
  if (user === null) return <Loading />;
  if (!user) return <Navigate to="/login" replace />;
  return <Navigate to={user.role === "admin" ? "/admin" : "/app"} replace />;
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/ganti-password" element={<ChangePasswordPage />} />
          <Route element={<Guard role="admin"><AppLayout /></Guard>}>
            <Route path="/admin" element={<AdminDashboard />} />
            <Route path="/admin/orders" element={<OrdersPage admin />} />
            <Route path="/admin/orders/baru" element={<AdminOrderNew />} />
            <Route path="/admin/orders/:id" element={<OrderDetailPage admin />} />
            <Route path="/admin/products" element={<ProductsPage />} />
            <Route path="/admin/resellers" element={<ResellersPage />} />
            <Route path="/admin/users" element={<UsersPage />} />
            <Route path="/admin/reports" element={<ReportsPage />} />
            <Route path="/admin/notifications" element={<NotificationsPage />} />
            <Route path="/admin/audit" element={<AuditPage />} />
          </Route>
          <Route element={<Guard role="reseller"><AppLayout /></Guard>}>
            <Route path="/app" element={<ResellerDashboard />} />
            <Route path="/app/order-baru" element={<OrderCreatePage />} />
            <Route path="/app/orders" element={<OrdersPage />} />
            <Route path="/app/orders/:id" element={<OrderDetailPage />} />
            <Route path="/app/rekap" element={<RekapPage />} />
            <Route path="/app/profil" element={<ProfilePage />} />
          </Route>
          <Route path="*" element={<Home />} />
        </Routes>
      </BrowserRouter>
      <Toaster richColors position="top-center" />
    </AuthProvider>
  );
}
