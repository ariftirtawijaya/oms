import axios, { AxiosError } from "axios";

// Production: same-origin relatif (PUBLIC_URL + /api = /order/api). Preview: REACT_APP_BACKEND_URL.
export const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || process.env.PUBLIC_URL || "";
export const API_BASE = `${BACKEND_URL}/api`;

export const api = axios.create({ baseURL: API_BASE, withCredentials: true });

function readCookie(name: string): string | null {
  const m = document.cookie.match(new RegExp("(?:^|; )" + name + "=([^;]*)"));
  return m ? decodeURIComponent(m[1]) : null;
}

api.interceptors.request.use((config) => {
  const method = (config.method || "get").toLowerCase();
  if (["post", "put", "patch", "delete"].includes(method)) {
    const csrf = readCookie("csrf_token");
    if (csrf) config.headers["X-CSRF-Token"] = csrf;
  }
  return config;
});

let refreshing: Promise<any> | null = null;

api.interceptors.response.use(
  (r) => r,
  async (error: AxiosError) => {
    const original: any = error.config;
    const url = original?.url || "";
    if (error.response?.status === 401 && !original._retry && !url.includes("/auth/")) {
      original._retry = true;
      try {
        refreshing = refreshing || api.post("/auth/refresh");
        await refreshing;
        refreshing = null;
        return api(original);
      } catch (e) {
        refreshing = null;
        window.dispatchEvent(new Event("relaylab:logout"));
      }
    }
    return Promise.reject(error);
  }
);

export function errorDetail(e: any): any {
  return e?.response?.data?.detail;
}

export function errMsg(e: any, fallback = "Terjadi kesalahan. Silakan coba lagi."): string {
  const d = errorDetail(e);
  if (d == null) return e?.message === "Network Error" ? "Tidak dapat terhubung ke server." : fallback;
  if (typeof d === "string") return d;
  if (Array.isArray(d)) return d.map((x) => translateValidation(x)).join(" ");
  if (typeof d.message === "string") return d.message;
  return fallback;
}

function translateValidation(x: any): string {
  const field = Array.isArray(x?.loc) ? x.loc[x.loc.length - 1] : "";
  const msg = String(x?.msg || "");
  if (msg.includes("at least")) return `Isian ${field} terlalu pendek.`;
  if (msg.includes("greater than")) return `Isian ${field} harus lebih besar.`;
  if (msg.includes("email")) return "Format email tidak valid.";
  return `Isian ${field} tidak valid.`;
}

export function fileUrl(filename: string) {
  return `${API_BASE}/files/resi/${encodeURIComponent(filename)}`;
}
