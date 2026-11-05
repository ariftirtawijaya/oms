import { useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Lock, Mail, Zap } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/common";
import { api, errMsg } from "@/lib/api";
import { useAuth } from "@/lib/auth";

const schema = z.object({
  email: z.string().min(1, "Email wajib diisi.").email("Format email tidak valid."),
  password: z.string().min(1, "Password wajib diisi."),
});

export default function LoginPage() {
  const { user, setUser } = useAuth();
  const nav = useNavigate();
  const [error, setError] = useState("");
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<z.infer<typeof schema>>({ resolver: zodResolver(schema) });

  if (user && !user.must_change_password) return <Navigate to={user.role === "admin" ? "/admin" : "/app"} replace />;

  const onSubmit = async (values: z.infer<typeof schema>) => {
    setError("");
    try {
      const { data } = await api.post("/auth/login", values);
      setUser(data);
      nav(data.must_change_password ? "/ganti-password" : data.role === "admin" ? "/admin" : "/app", { replace: true });
    } catch (e) {
      setError(errMsg(e));
    }
  };

  return (
    <div className="grid min-h-screen lg:grid-cols-2">
      <div className="relative hidden overflow-hidden bg-slate-900 lg:block">
        <img src={`${process.env.PUBLIC_URL}/login-bg.jpg`}
          alt="Lampu kendaraan" className="absolute inset-0 h-full w-full object-cover opacity-40" />
        <div className="relative flex h-full flex-col justify-between p-12 text-white">
          <div className="flex items-center gap-3">
            <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-600"><Zap className="h-5 w-5" /></span>
            <span className="font-heading text-lg font-extrabold">RelayLab Autolight</span>
          </div>
          <div className="max-w-md">
            <h1 className="font-heading text-4xl font-extrabold leading-tight tracking-tight">Sistem Pemesanan Reseller RelayLab</h1>
            <p className="mt-4 text-slate-300">Pantau order, progress produksi, pembayaran, dan pengiriman relay set Anda dalam satu tempat.</p>
          </div>
          <p className="text-xs text-slate-400">Akses khusus akun terdaftar.</p>
        </div>
      </div>
      <div className="flex items-center justify-center bg-slate-50 px-5 py-12">
        <form onSubmit={handleSubmit(onSubmit)} className="w-full max-w-sm space-y-5 fade-up" data-testid="login-form">
          <div className="lg:hidden">
            <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-blue-700 text-white"><Zap className="h-6 w-6" /></span>
          </div>
          <div>
            <h2 className="font-heading text-3xl font-extrabold tracking-tight text-slate-900">Masuk</h2>
            <p className="mt-1 text-sm text-slate-500">Gunakan email dan password akun RelayLab OMS Anda.</p>
          </div>
          {error && <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700" data-testid="login-error">{error}</div>}
          <Field label="Email" error={errors.email?.message}>
            <div className="relative">
              <Mail className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
              <Input type="email" autoComplete="email" className="h-11 bg-white pl-9" placeholder="nama@email.com" {...register("email")} data-testid="login-email-input" />
            </div>
          </Field>
          <Field label="Password" error={errors.password?.message}>
            <div className="relative">
              <Lock className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
              <Input type="password" autoComplete="current-password" className="h-11 bg-white pl-9" placeholder="••••••••" {...register("password")} data-testid="login-password-input" />
            </div>
          </Field>
          <Button type="submit" disabled={isSubmitting} className="h-11 w-full bg-blue-700 text-white hover:bg-blue-800" data-testid="login-submit-button">
            {isSubmitting ? "Memproses..." : "Masuk"}
          </Button>
          <p className="text-center text-xs text-slate-500">Lupa password? Hubungi admin RelayLab untuk reset.</p>
        </form>
      </div>
    </div>
  );
}
