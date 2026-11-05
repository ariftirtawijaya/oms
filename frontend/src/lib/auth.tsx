import React, { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api } from "@/lib/api";

export type User = {
  id: string;
  email: string;
  name: string;
  role: "admin" | "reseller";
  reseller_id?: string | null;
  must_change_password?: boolean;
  reseller?: any;
};

type Ctx = {
  user: User | null | false;
  setUser: (u: User | false) => void;
  refresh: () => Promise<void>;
  logout: () => Promise<void>;
};

const AuthContext = createContext<Ctx>({} as Ctx);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null | false>(null);

  const refresh = useCallback(async () => {
    try {
      const { data } = await api.get("/auth/me");
      setUser(data);
    } catch {
      setUser(false);
    }
  }, []);

  const logout = useCallback(async () => {
    try {
      await api.post("/auth/logout");
    } finally {
      setUser(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    const onLogout = () => setUser(false);
    window.addEventListener("relaylab:logout", onLogout);
    return () => window.removeEventListener("relaylab:logout", onLogout);
  }, [refresh]);

  return <AuthContext.Provider value={{ user, setUser, refresh, logout }}>{children}</AuthContext.Provider>;
}

export const useAuth = () => useContext(AuthContext);
