import axios, { type AxiosResponse } from "axios";

const api = axios.create({
  baseURL: "/api",
  timeout: 15000,
  headers: { "Content-Type": "application/json" },
  withCredentials: true,
});

let onUnauthorized: (() => void) | null = null;
export function setUnauthorizedHandler(handler: (() => void) | null) {
  onUnauthorized = handler;
}

let sessionExpiredToast: (() => void) | null = null;
export function setSessionExpiredToast(handler: (() => void) | null) {
  sessionExpiredToast = handler;
}

let hasShownSessionExpired = false;

api.interceptors.response.use(
  (res) => res,
  (err) => {
    const status = err.response?.status;
    const url: string = err.config?.url ?? "";
    if (status === 401 && !url.startsWith("/auth/")) {
      if (!hasShownSessionExpired) {
        hasShownSessionExpired = true;
        sessionExpiredToast?.();
      }
      onUnauthorized?.();
      return Promise.resolve({ data: { data: null } } as AxiosResponse);
    }
    const message =
      err.response?.data?.error ??
      err.response?.data?.details?.join(", ") ??
      err.message ??
      "Unknown error";
    return Promise.reject(new Error(message));
  }
);

export function resetSessionExpiredFlag() {
  hasShownSessionExpired = false;
}

export default api;
