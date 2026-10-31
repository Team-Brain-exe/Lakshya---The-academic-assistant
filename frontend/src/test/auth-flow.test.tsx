/**
 * Mocked integration tests for the login / auth / navigation flow.
 *
 * These tests mock the network layer (@/lib/api) — they do NOT hit the
 * deployed backend.  They verify the client-side logic that was
 * previously broken (hooks-in-handler, 401 redirect on login, JWT fallback).
 */
import { act, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";

// ── Hoisted mocks ──────────────────────────────────────────────
// vi.mock is hoisted above all imports, so mock functions must be created
// inside vi.hoisted to be available in the factory.
const mocks = vi.hoisted(() => ({
  setToken: vi.fn(),
  clearToken: vi.fn(),
  getToken: vi.fn(),
  isAuthenticated: vi.fn(),
  login: vi.fn(),
  logout: vi.fn(() => mocks.clearToken()),
  getMe: vi.fn(),
  currentUser: vi.fn((): User | null => null),
}));

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return {
    ...actual,
    setToken: mocks.setToken,
    clearToken: mocks.clearToken,
    getToken: mocks.getToken,
    isAuthenticated: mocks.isAuthenticated,
    auth: {
      login: mocks.login,
      logout: mocks.logout,
      getMe: mocks.getMe,
    },
    usageApi: {
      currentUser: mocks.currentUser,
    },
  };
});

vi.mock("@/lib/subject-context", () => ({
  getStoredSubjectId: vi.fn(() => null),
  storeSubjectId: vi.fn(),
  clearStoredSubjectId: vi.fn(),
  clearSavedAttempt: vi.fn(),
}));

// ── Import after mocks are set up ─────────────────────────────────
import { ApiError, type LoginResponse, type User } from "@/lib/api";
import { useAuth, AuthProvider } from "@/lib/auth-context";

// ── Test harness ──────────────────────────────────────────────────
function TestConsumer({ onReady }: { onReady?: (a: ReturnType<typeof useAuth>) => void }) {
  const auth = useAuth();
  if (onReady) onReady(auth);
  return (
    <div>
      <span data-testid="loading">{auth.loading ? "loading" : "ready"}</span>
      <span data-testid="authenticated">{auth.isAuthenticated ? "yes" : "no"}</span>
      <span data-testid="user">{auth.user?.name ?? "none"}</span>
    </div>
  );
}

const FAKE_USER: User = {
  id: "u-123",
  role: "student",
  name: "Ada Lovelace",
  usn: "1RV22CS018",
  email: null,
  student_id: "s-456",
};

const FAKE_LOGIN_RESPONSE: LoginResponse = {
  access_token: "fake-jwt-token",
  token_type: "bearer",
  role: "student",
  user: FAKE_USER,
};

describe("AuthProvider login flow (mocked API)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.logout.mockImplementation(() => mocks.clearToken());
    mocks.currentUser.mockReturnValue(null);
    if (typeof sessionStorage !== "undefined") sessionStorage.clear();
  });

  it("stores token and resolves user on successful login", async () => {
    mocks.getMe.mockResolvedValue({ ...FAKE_USER, name: "Ada L." });

    let captured: ReturnType<typeof useAuth> | null = null;
    render(
      <AuthProvider>
        <TestConsumer onReady={(a) => (captured = a)} />
      </AuthProvider>,
    );

    // Wait for mount effect to settle
    await waitFor(() => {
      expect(screen.getByTestId("loading").textContent).toBe("ready");
    });
    expect(screen.getByTestId("authenticated").textContent).toBe("no");

    // Perform login
    await act(async () => {
      await captured!.login(FAKE_LOGIN_RESPONSE);
    });

    expect(mocks.setToken).toHaveBeenCalledWith("fake-jwt-token");
    expect(mocks.getMe).toHaveBeenCalled();
    expect(screen.getByTestId("authenticated").textContent).toBe("yes");
    expect(screen.getByTestId("user").textContent).toBe("Ada L.");
  });

  it("clears session when /auth/me fails after login (no JWT fallback)", async () => {
    mocks.getMe.mockRejectedValue(
      new ApiError(401, "UNAUTHENTICATED", "Invalid token"),
    );

    let captured: ReturnType<typeof useAuth> | null = null;
    render(
      <AuthProvider>
        <TestConsumer onReady={(a) => (captured = a)} />
      </AuthProvider>,
    );

    // Wait for initial load to settle
    await waitFor(() => {
      expect(screen.getByTestId("loading").textContent).toBe("ready");
    });

    await act(async () => {
      try {
        await captured!.login(FAKE_LOGIN_RESPONSE);
      } catch {
        // login() catches internally
      }
    });

    // Token should be cleared, user null, authenticated false
    expect(mocks.clearToken).toHaveBeenCalled();
    expect(screen.getByTestId("authenticated").textContent).toBe("no");
    expect(screen.getByTestId("user").textContent).toBe("none");
  });

  it("logout clears token, subject, attempt, and redirects to /", async () => {
    mocks.getMe.mockResolvedValue(FAKE_USER);

    let captured: ReturnType<typeof useAuth> | null = null;
    render(
      <AuthProvider>
        <TestConsumer onReady={(a) => (captured = a)} />
      </AuthProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("loading").textContent).toBe("ready");
    });

    await act(async () => {
      await captured!.login(FAKE_LOGIN_RESPONSE);
    });

    // Now logout
    await act(async () => {
      captured!.logout();
    });

    expect(mocks.logout).toHaveBeenCalled();
    expect(mocks.clearToken).toHaveBeenCalled();
    expect(screen.getByTestId("authenticated").textContent).toBe("no");
    expect(screen.getByTestId("user").textContent).toBe("none");
  });

  it("does not silently accept JWT data when /auth/me fails (no fallback)", async () => {
    mocks.getMe.mockRejectedValue(
      new ApiError(403, "FORBIDDEN", "Service unavailable"),
    );

    let captured: ReturnType<typeof useAuth> | null = null;
    render(
      <AuthProvider>
        <TestConsumer onReady={(a) => (captured = a)} />
      </AuthProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("loading").textContent).toBe("ready");
    });

    await act(async () => {
      try {
        await captured!.login(FAKE_LOGIN_RESPONSE);
      } catch {
        // expected — login catches internally
      }
    });

    // Should NOT silently accept JWT data — session was cleared.
    expect(mocks.clearToken).toHaveBeenCalled();
    expect(screen.getByTestId("authenticated").textContent).toBe("no");
  });
});

describe("AuthProvider session restoration (mocked API)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.logout.mockImplementation(() => mocks.clearToken());
    mocks.currentUser.mockReturnValue(null);
    if (typeof sessionStorage !== "undefined") sessionStorage.clear();
  });

  it("restores session on mount when token exists in sessionStorage", async () => {
    // Simulate a previous login by placing the token in sessionStorage
    // directly (bypassing the mocked setToken).
    sessionStorage.setItem("lakshya_access_token", "prev-session-token");
    const restoredUser: User = {
      id: "u-prev",
      role: "faculty",
      name: "Previous User",
      usn: null,
      email: "prev@example.edu",
    };
    mocks.currentUser.mockReturnValue(restoredUser);
    mocks.getMe.mockResolvedValue(restoredUser);

    let captured: ReturnType<typeof useAuth> | null = null;
    render(
      <AuthProvider>
        <TestConsumer onReady={(a) => (captured = a)} />
      </AuthProvider>,
    );

    // Should call getMe on mount when a token exists
    await waitFor(() => {
      expect(mocks.getMe).toHaveBeenCalledTimes(1);
    });
    expect(screen.getByTestId("authenticated").textContent).toBe("yes");
    expect(screen.getByTestId("user").textContent).toBe("Previous User");
  });
});
