/**
 * Auth context: provides the authenticated user, login/logout, and a
 * RequireAuth guard for protected routes.
 *
 * Works safely under TanStack Start SSR: all sessionStorage access is
 * guarded by `typeof` checks, and the provider degrades to "loading"
 * until it can confirm auth status client-side.
 */
import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { auth, setSession, usageApi, type LoginResponse, type User } from "@/lib/api";

interface AuthContextValue {
  user: User | null;
  loading: boolean;
  /** True when a usable token exists (JWT present in storage). */
  isAuthenticated: boolean;
  /** Persist a login response (stores token + resolves the user). */
  login: (data: LoginResponse) => Promise<void>;
  /** Clear the token and reset user state. */
  logout: () => void;
  /** Re-fetch /auth/me and refresh the user object. */
  refetch: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  // Initialise from the JWT (fast, no network). /auth/me is then fetched to
  // obtain the full server-side profile.
  const [user, setUser] = useState<User | null>(() => usageApi.currentUser());
  const [loading, setLoading] = useState(true);
  const [authenticated, setAuthenticated] = useState(() => {
    return usageApi.currentUser() !== null;
  });
  const [error, setError] = useState<string | null>(null);

  const logout = () => {
    auth.logout();
    setUser(null);
    setAuthenticated(false);
    setError(null);
    // Redirect to the login page (root).
    if (typeof window !== "undefined") {
      window.location.href = "/";
    }
  };

  const resolveUser = async () => {
    try {
      const me = await auth.getMe();
      setUser(me);
      setAuthenticated(true);
      setError(null);
    } catch (e) {
      // Token may be missing/expired — user stays null.
      setUser(null);
      setAuthenticated(false);
    } finally {
      setLoading(false);
    }
  };

  const login = async (data: LoginResponse) => {
    setSession(data);
    setAuthenticated(true);
    try {
      const me = await auth.getMe();
      setUser(me);
    } catch {
      // Fall back to JWT-decoded identity if /me fails.
      setUser(usageApi.currentUser());
    }
    setError(null);
  };

  // On mount, confirm the session by calling /auth/me.
  useEffect(() => {
    if (authenticated) {
      void resolveUser();
    } else {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <AuthContext.Provider
      value={{
        user,
        loading,
        isAuthenticated: authenticated,
        login,
        logout,
        refetch: resolveUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}
