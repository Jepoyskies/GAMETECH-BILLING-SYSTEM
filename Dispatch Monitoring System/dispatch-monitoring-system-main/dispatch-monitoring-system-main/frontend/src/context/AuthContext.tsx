import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import api, { setUnauthorizedHandler, setSessionExpiredToast, resetSessionExpiredFlag } from "../lib/api";
import { connectSocket, disconnectSocket } from "../lib/socket";
import { useToast } from "./ToastContext";
import type { AuthUser } from "../lib/types";

interface AuthContextValue {
  user: AuthUser | null;
  loading: boolean;
  needsSetup: boolean;
  mustChangePassword: boolean;
  login: (email: string, password: string) => Promise<void>;
  setup: (name: string, email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
  isSuperAdmin: boolean;
  changePassword: (currentPassword: string, newPassword: string) => Promise<void>;
  clearMustChangePassword: () => void;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [needsSetup, setNeedsSetup] = useState(false);
  const [mustChangePassword, setMustChangePassword] = useState(false);
  const { addToast } = useToast();

  const loadSession = useCallback(async () => {
    try {
      const res = await api.get("/auth/me");
      const data = res.data.data as AuthUser;
      setUser(data);
      setMustChangePassword(data.must_change_password);
    } catch {
      setUser(null);
      setMustChangePassword(false);
      try {
        const status = await api.get("/auth/setup");
        setNeedsSetup(Boolean(status.data.data?.needs_setup));
      } catch {
        setNeedsSetup(false);
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadSession();
  }, [loadSession]);

  useEffect(() => {
    setUnauthorizedHandler(() => {
      setUser(null);
      setMustChangePassword(false);
    });
    setSessionExpiredToast(() => {
      addToast("Session expired. Please log in again.", "error");
    });
    return () => {
      setUnauthorizedHandler(null);
      setSessionExpiredToast(null);
    };
  }, [addToast]);

  useEffect(() => {
    if (user) {
      connectSocket();
      return () => {
        disconnectSocket();
      };
    }

    disconnectSocket();
    return undefined;
  }, [user]);

  const login = useCallback(async (email: string, password: string) => {
    const res = await api.post("/auth/login", { email, password });
    const data = res.data.data as AuthUser;
    setUser(data);
    setMustChangePassword(data.must_change_password);
    setNeedsSetup(false);
    resetSessionExpiredFlag();
  }, []);

  const setup = useCallback(
    async (name: string, email: string, password: string) => {
      const res = await api.post("/auth/setup", { name, email, password });
      const data = res.data.data as AuthUser;
      setUser(data);
      setMustChangePassword(data.must_change_password);
      setNeedsSetup(false);
      resetSessionExpiredFlag();
    },
    []
  );

  const logout = useCallback(async () => {
    try {
      await api.post("/auth/logout");
    } finally {
      setUser(null);
      setMustChangePassword(false);
    }
  }, []);

  const changePassword = useCallback(
    async (currentPassword: string, newPassword: string) => {
      if (!user) return;
      const body: Record<string, string> = { new_password: newPassword };
      if (currentPassword) body.current_password = currentPassword;
      const res = await api.put(`/auth/accounts/${user.id}/password`, body);
      const data = res.data.data as AuthUser;
      if (currentPassword) {
        setUser(null);
        setMustChangePassword(false);
      } else {
        setUser((prev) => (prev ? { ...prev, ...data } : prev));
        setMustChangePassword(data.must_change_password);
      }
    },
    [user]
  );

  const clearMustChangePassword = useCallback(() => {
    setMustChangePassword(false);
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      loading,
      needsSetup,
      mustChangePassword,
      login,
      setup,
      logout,
      refresh: loadSession,
      isSuperAdmin: user?.role === "SUPERADMIN",
      changePassword,
      clearMustChangePassword,
    }),
    [
      user,
      loading,
      needsSetup,
      mustChangePassword,
      login,
      setup,
      logout,
      loadSession,
      changePassword,
      clearMustChangePassword,
    ]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within an AuthProvider");
  return ctx;
}
