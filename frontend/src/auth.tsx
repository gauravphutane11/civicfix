import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api } from "./api";
import type { AuthUser } from "./types";

type RegisterPayload = { name: string; email: string; phone?: string; password: string };
type AuthContextValue = {
  user: AuthUser | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<AuthUser>;
  register: (payload: RegisterPayload) => Promise<AuthUser>;
  logout: () => void;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem("civicfix_token");
    if (!token) {
      setLoading(false);
      return;
    }

    api.getMe()
      .then(setUser)
      .catch(() => {
        localStorage.removeItem("civicfix_token");
        localStorage.removeItem("civicfix_user");
        setUser(null);
      })
      .finally(() => setLoading(false));
  }, []);

  const value = useMemo<AuthContextValue>(() => ({
    user,
    loading,
    async login(email, password) {
      const result = await api.login(email, password);
      localStorage.setItem("civicfix_token", result.access_token);
      localStorage.setItem("civicfix_user", JSON.stringify(result.user));
      setUser(result.user);
      return result.user;
    },
    async register(payload) {
      const result = await api.register(payload);
      localStorage.setItem("civicfix_token", result.access_token);
      localStorage.setItem("civicfix_user", JSON.stringify(result.user));
      setUser(result.user);
      return result.user;
    },
    logout() {
      localStorage.removeItem("civicfix_token");
      localStorage.removeItem("civicfix_user");
      setUser(null);
    },
  }), [user, loading]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside AuthProvider");
  return context;
}
