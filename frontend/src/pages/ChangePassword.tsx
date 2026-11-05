import { Navigate, useNavigate } from "react-router-dom";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import { KeyRound } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Field, Loading } from "@/components/common";
import { api, errMsg } from "@/lib/api";
import { useAuth } from "@/lib/auth";

const schema = z.object({
  current_password: z.string().min(1, "Password saat ini wajib diisi."),
  new_password: z.string().min(8, "Password baru minimal 8 karakter."),
  confirm: z.string(),
}).refine((v) => v.new_password === v.confirm, { message: "Konfirmasi password tidak sama.", path: ["confirm"] });

export default function ChangePasswordPage() {
  const { user, refresh } = useAuth();
  const nav = useNavigate();
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<z.infer<typeof schema>>({ resolver: zodResolver(schema) });
  if (user === null) return <Loading />;
  if (!user) return <Navigate to="/login" replace />;

  const onSubmit = async (v: z.infer<typeof schema>) => {
    try {
      await api.post("/auth/change-password", { current_password: v.current_password, new_password: v.new_password });
      toast.success("Password berhasil diubah.");
      await refresh();
      nav(user.role === "admin" ? "/admin" : "/app", { replace: true });
    } catch (e) {
      toast.error(errMsg(e));
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 px-5">
      <form onSubmit={handleSubmit(onSubmit)} className="w-full max-w-md space-y-5 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8" data-testid="change-password-form">
        <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-blue-50 text-blue-700"><KeyRound className="h-5 w-5" /></span>
        <div>
          <h1 className="font-heading text-2xl font-extrabold tracking-tight">Ganti Password</h1>
          {user.must_change_password ? (
            <p className="mt-1 text-sm text-amber-700" data-testid="must-change-password-notice">Akun Anda menggunakan password sementara. Silakan buat password baru sebelum melanjutkan.</p>
          ) : <p className="mt-1 text-sm text-slate-500">Gunakan minimal 8 karakter.</p>}
        </div>
        <Field label="Password saat ini" error={errors.current_password?.message}>
          <Input type="password" className="h-11" {...register("current_password")} data-testid="current-password-input" />
        </Field>
        <Field label="Password baru" error={errors.new_password?.message}>
          <Input type="password" className="h-11" {...register("new_password")} data-testid="new-password-input" />
        </Field>
        <Field label="Ulangi password baru" error={errors.confirm?.message}>
          <Input type="password" className="h-11" {...register("confirm")} data-testid="confirm-password-input" />
        </Field>
        <div className="flex gap-2">
          {!user.must_change_password && (
            <Button type="button" variant="outline" className="h-11 flex-1" onClick={() => nav(-1)} data-testid="change-password-cancel">Batal</Button>
          )}
          <Button type="submit" disabled={isSubmitting} className="h-11 flex-1 bg-blue-700 text-white hover:bg-blue-800" data-testid="change-password-submit">
            {isSubmitting ? "Menyimpan..." : "Simpan Password"}
          </Button>
        </div>
      </form>
    </div>
  );
}
