import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Field, Loading, PageHeader, Section } from "@/components/common";
import { api, errMsg } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export default function ProfilePage() {
  const { user } = useAuth();
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({ queryKey: ["profile"], queryFn: () => api.get("/me/profile").then((r) => r.data), staleTime: 0 });
  const [address, setAddress] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => { if (data) setAddress(data.address || ""); }, [data]);
  if (isLoading || !data) return <Loading />;
  const save = async () => {
    setBusy(true);
    try { await api.put("/me/profile", { address }); toast.success("Profil diperbarui."); qc.invalidateQueries({ queryKey: ["profile"] }); }
    catch (e) { toast.error(errMsg(e)); } finally { setBusy(false); }
  };
  return (
    <div className="max-w-2xl space-y-5">
      <PageHeader title="Profil Saya" />
      <Section title="Informasi Reseller">
        <div className="space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-2"><p className="font-heading text-lg font-bold" data-testid="profile-name">{data.name}</p></div>
          <Field label="Email Login"><Input value={user ? user.email : ""} disabled /></Field>
          <Field label="Nomor WhatsApp" hint="Untuk mengubah nomor WhatsApp, hubungi admin RelayLab."><Input value={data.wa} disabled data-testid="profile-wa" /></Field>
          <Field label="Alamat Pengiriman"><Textarea rows={3} value={address} onChange={(e) => setAddress(e.target.value)} data-testid="profile-address-input" /></Field>
          <Button onClick={save} disabled={busy} className="bg-blue-700 text-white hover:bg-blue-800" data-testid="profile-save-button">Simpan Profil</Button>
        </div>
      </Section>
    </div>
  );
}
