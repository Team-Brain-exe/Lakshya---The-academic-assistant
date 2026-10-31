import { Link, useRouter, useRouterState } from "@tanstack/react-router";
import {
  BarChart3,
  Bell,
  BookOpen,
  CalendarDays,
  ChevronDown,
  ClipboardCheck,
  FileUp,
  Home,
  Layers,
  Loader2,
  LogOut,
  MessageCircle,
  PenLine,
  Send,
  Sparkle,
  Star,
  TrendingUp,
  X,
} from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";
import { cn } from "@/lib/utils";
import { useAuth } from "@/lib/auth-context";
import { agent, type AgentChatResponse, type AgentProposal, type ApiError } from "@/lib/api";

type Role = "faculty" | "student";

type NavItem = { to: string; t: string; i: React.ElementType; disabled?: boolean };

const NAV: Record<Role, { label: string; items: NavItem[] }[]> = {
  faculty: [
    { label: "Overview", items: [{ to: "/faculty/dashboard", t: "Dashboard", i: Home }] },
    {
      label: "Teaching",
      items: [
        { to: "/faculty/upload", t: "Modules & CO", i: FileUp },
        { to: "/faculty/review", t: "Question Review", i: ClipboardCheck },
        { to: "/faculty/quiz-builder", t: "Quiz Builder", i: PenLine },
      ],
    },
    { label: "Reports", items: [{ to: "/faculty/analytics", t: "CO Sheet", i: BarChart3 }] },
  ],
  student: [
    { label: "Overview", items: [{ to: "/student/home", t: "Home", i: Home }] },
    {
      label: "Learn",
      items: [
        { to: "/student/quiz", t: "Quizzes", i: ClipboardCheck },
        { to: "/student/home", t: "My Progress", i: TrendingUp },
        { to: "#", t: "Study Plan", i: BookOpen, disabled: true },
        { to: "#", t: "Flashcards", i: Layers, disabled: true },
        { to: "#", t: "Q&A", i: MessageCircle, disabled: true },
        { to: "#", t: "Calendar", i: CalendarDays, disabled: true },
      ],
    },
  ],
};

export function Shell({
  role,
  children,
  subjectLabel,
  moduleLabel,
}: {
  role: Role;
  children: ReactNode;
  subjectLabel?: string | undefined;
  moduleLabel?: string | undefined;
}) {
  const [assistantOpen, setAssistantOpen] = useState(false);

  const path = useRouterState({ select: (s) => s.location.pathname });
  const router = useRouter();
  const { user, isAuthenticated, loading, logout } = useAuth();

  // Protect routes: if the session is resolved and the user is not
  // authenticated, bounce to the login page.
  useEffect(() => {
    if (!loading && !isAuthenticated) {
      router.navigate({ to: "/" });
    }
  }, [loading, isAuthenticated, router]);

  if (loading || !isAuthenticated) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <Loader2 className="size-8 animate-spin text-wine" />
      </div>
    );
  }

  const displayName = user?.name ?? "";
  const idLabel =
    role === "faculty"
      ? user?.email ?? "Faculty"
      : user?.usn ?? user?.id ?? "Student";

  return (
    <div className="flex min-h-screen w-full">
      <aside className="sticky top-0 flex h-screen w-64 shrink-0 flex-col bg-oxblood px-4 py-6 text-beige">
        <Link to="/" className="flex items-center gap-2 px-2">
          <span className="grid size-9 place-items-center rounded-full border border-beige/40">
            <Star className="size-4 fill-beige" />
          </span>
          <span>
            <span className="block font-serif text-2xl font-bold tracking-[0.12em] text-ivory">
              LAKSHYA
            </span>
            <span className="eyebrow block !text-[9px] !text-beige/60">The Academic Assistant</span>
          </span>
        </Link>
        <nav className="mt-8 flex-1 space-y-6">
          {NAV[role].map((g) => (
            <div key={g.label}>
              <div className="eyebrow mb-2 border-b border-beige/15 px-2 pb-1 !text-beige/50">
                {g.label}
              </div>
              {g.items.map((it) => {
              const active = path === it.to;
              return it.disabled ? (
                <button
                  key={it.t}
                  type="button"
                  disabled
                  className="mb-1 flex w-full items-center gap-3 rounded-full px-3 py-2 text-sm text-beige/40 cursor-not-allowed"
                  title="Coming soon"
                >
                  <it.i className="size-4" strokeWidth={1.6} />
                  {it.t}
                </button>
              ) : (
                <Link
                  key={it.t}
                  to={it.to}
                  className={cn(
                    "mb-1 flex items-center gap-3 rounded-full px-3 py-2 text-sm transition",
                    active ? "bg-ivory font-medium text-wine" : "text-beige/80 hover:bg-beige/10",
                  )}
                >
                  <it.i className="size-4" strokeWidth={1.6} />
                  {it.t}
                </Link>
              );
              })}
            </div>
          ))}
        </nav>
        <div className="rounded-2xl bg-wine p-3">
          <div className="flex items-center gap-3">
            <div className="grid size-10 place-items-center rounded-full bg-beige font-serif text-lg font-bold text-wine">
              {displayName ? (
                <>
                  {displayName[0]}
                  {displayName.split(" ")[1]?.[0] ?? displayName[1] ?? ""}
                </>
              ) : (
                "?"
              )}
            </div>
            <div className="min-w-0">
              <div className="truncate text-sm font-medium text-ivory">{displayName || "LAKSHYA User"}</div>
              <div className="font-mono text-[10px] text-beige/70">{idLabel}</div>
            </div>
          </div>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-20 flex h-16 items-center gap-3 border-b border-wine/15 bg-beige/95 px-8 backdrop-blur-sm">
          {(subjectLabel || moduleLabel) && (
            <>
              {subjectLabel && (
                <button className="flex items-center gap-2 rounded-full bg-wine px-4 py-1.5 text-sm text-ivory">
                  <BookOpen className="size-4" /> {subjectLabel}
                  <ChevronDown className="size-3.5" />
                </button>
              )}
              {moduleLabel && (
                <span className="rounded-full border border-wine/30 px-3 py-1 font-mono text-[11px] text-wine">
                  {moduleLabel}
                </span>
              )}
              <div className="flex-1" />
            </>
          )}
          <span className="rounded-full bg-dusty px-3 py-1 text-xs font-medium capitalize text-oxblood">
            {role}
          </span>
          <span className="font-mono text-xs text-muted-foreground">
            {idLabel}
          </span>
          <button
            className="relative grid size-9 place-items-center rounded-full hover:bg-wine/10"
            aria-label="Notifications"
          >
            <Bell className="size-4 text-wine" />
            <span className="absolute right-2 top-2 size-1.5 rounded-full bg-wine" />
          </button>
          <button
            onClick={logout}
            className="grid size-9 place-items-center rounded-full hover:bg-wine/10"
            aria-label="Log out"
          >
            <LogOut className="size-4 text-wine" />
          </button>
        </header>
        <main className="flex-1 px-8 py-8">{children}</main>
      </div>

      <button
        onClick={() => setAssistantOpen(true)}
        className="fixed bottom-6 right-6 z-30 flex items-center gap-2 rounded-full bg-wine px-5 py-3 text-sm font-medium text-ivory shadow-[var(--shadow-lift)] hover:bg-oxblood"
      >
        <Sparkle className="size-4 fill-ivory" /> Ask Lakshya
      </button>
      <Assistant open={assistantOpen} onClose={() => setAssistantOpen(false)} role={role} />
    </div>
  );
}

// ── Assistant / Ask Lakshya panel ─────────────────────────────────────

type AssistantMessage = { role: "user" | "assistant"; content: string; error?: boolean };

const ASSISTANT_STORAGE_KEY = "lakshya_agent_conversation";

function Assistant({ open, onClose, role }: { open: boolean; onClose: () => void; role: Role }) {
  const [messages, setMessages] = useState<AssistantMessage[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);

  // Persist conversation state across panel open/close within the session.
  useEffect(() => {
    if (open) {
      const stored = sessionStorage.getItem(ASSISTANT_STORAGE_KEY);
      if (stored) {
        const parsed = JSON.parse(stored) as {
          messages: AssistantMessage[];
          conversationId: string | null;
        };
        setMessages(parsed.messages);
        setConversationId(parsed.conversationId);
      }
    }
  }, [open]);

  useEffect(() => {
    if (open && (messages.length > 0 || conversationId)) {
      sessionStorage.setItem(
        ASSISTANT_STORAGE_KEY,
        JSON.stringify({ messages, conversationId }),
      );
    }
  }, [messages, conversationId, open]);

  useEffect(() => {
    if (open) {
      // Auto-scroll to bottom when new messages arrive
      const el = document.getElementById("assistant-scroll");
      if (el) el.scrollTop = el.scrollHeight;
    }
  }, [messages, open]);

  const send = async () => {
    if (!input.trim() || loading) return;
    const text = input.trim();
    setInput("");
    setLoading(true);

    const prev = messages;
    setMessages((m) => [...m, { role: "user", content: text }]);

    try {
      const resp: AgentChatResponse = await agent.chat(text, conversationId ?? undefined);
      setConversationId(resp.conversation_id);
      setMessages((m) => [...m, { role: "assistant", content: resp.reply }]);
    } catch (e) {
      const apiErr = e as ApiError;
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          content: apiErr?.message ?? "Something went wrong. Please try again.",
          error: true,
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleConfirm = async (proposal: AgentProposal, approve: boolean) => {
    try {
      await agent.confirm(proposal.id, approve);
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          content: approve
            ? `Proposal accepted: ${proposal.description}`
            : `Proposal cancelled: ${proposal.description}`,
        },
      ]);
    } catch (e) {
      const apiErr = e as ApiError;
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          content: `Could not process proposal: ${apiErr?.message ?? "unknown error"}`,
          error: true,
        },
      ]);
    }
  };

  const clearChat = () => {
    setMessages([]);
    setConversationId(null);
    sessionStorage.removeItem(ASSISTANT_STORAGE_KEY);
  };

  // Render messages — proposals are embedded in assistant messages.
  // The backend returns proposals alongside each reply; we surface them
  // as inline actionable cards.
  const renderMessages = () => {
    const out: React.ReactElement[] = [];
    for (let i = 0; i < messages.length; i++) {
      const msg = messages[i]!;
      out.push(
        <div key={i} className="space-y-3">
          <div
            className={cn(
              "max-w-[88%] rounded-2xl px-4 py-3 text-sm",
              msg.role === "user"
                ? "ml-auto bg-wine text-ivory"
                : "bg-dusty/60 text-espresso",
              msg.error && "border border-oxblood/40",
            )}
          >
            {msg.content}
          </div>
        </div>,
      );
    }
    if (loading) {
      out.push(
        <div key="loading" className="max-w-[88%] rounded-2xl rounded-bl-sm bg-dusty/60 px-4 py-3 text-sm">
          <div className="flex gap-1">
            <span className="size-1.5 animate-bounce rounded-full bg-wine" />
            <span className="size-1.5 animate-bounce rounded-full bg-wine [animation-delay:.15s]" />
            <span className="size-1.5 animate-bounce rounded-full bg-wine [animation-delay:.3s]" />
          </div>
        </div>,
      );
    }
    return out;
  };

  return (
    <>
      <div
        onClick={onClose}
        className={cn(
          "fixed inset-0 z-40 bg-oxblood/30 transition",
          open ? "opacity-100" : "pointer-events-none opacity-0",
        )}
      />
      <aside
        className={cn(
          "fixed right-0 top-0 z-50 flex h-screen w-[420px] flex-col bg-ivory shadow-[var(--shadow-lift)] transition-transform duration-300",
          open ? "translate-x-0" : "translate-x-full",
        )}
      >
        <div className="paper-wine torn-bottom !rounded-none px-6 pt-5">
          <div className="flex items-center justify-between">
            <div className="eyebrow !text-beige/70">Notebook · Today</div>
            <div className="flex gap-1">
              {messages.length > 0 && (
                <button
                  onClick={clearChat}
                  className="grid size-8 place-items-center rounded-full text-wine hover:bg-wine/10"
                  aria-label="New conversation"
                >
                  <X className="size-4" />
                </button>
              )}
              <button onClick={onClose} aria-label="Close">
                <X className="size-4" />
              </button>
            </div>
          </div>
          <h2 className="display mt-1 text-3xl !text-ivory">Ask Lakshya</h2>
          <p className="pb-3 text-xs text-beige/80">Answers grounded in your course slides.</p>
        </div>
        <div
          id="assistant-scroll"
          className="flex-1 space-y-4 overflow-y-auto p-5"
          style={{
            backgroundImage:
              "repeating-linear-gradient(transparent 0 27px, oklch(0.79 0.035 245 / 35%) 27px 28px)",
          }}
        >
          {messages.length === 0 && !open && (
            <div className="pb-3 text-xs text-muted-foreground">Ask me anything about your course.</div>
          )}
          {renderMessages()}
          {loading && messages.length > 0 && (
            <div className="max-w-[88%] rounded-2xl rounded-bl-sm bg-dusty/60 px-4 py-3 text-sm">
              <div className="flex gap-1">
                <span className="size-1.5 animate-bounce rounded-full bg-wine" />
                <span className="size-1.5 animate-bounce rounded-full bg-wine [animation-delay:.15s]" />
                <span className="size-1.5 animate-bounce rounded-full bg-wine [animation-delay:.3s]" />
              </div>
            </div>
          )}
        </div>
        <div className="border-t border-wine/15 p-4">
          <div className="flex items-center gap-2 rounded-full border border-wine/30 bg-beige/40 py-1 pl-4 pr-1">
            <MessageCircle className="size-4 text-wine/60" />
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  void send();
                }
              }}
              placeholder="Ask about your course…"
              className="flex-1 bg-transparent text-sm outline-none"
              disabled={loading}
            />
            <button
              onClick={() => void send()}
              disabled={loading || !input.trim()}
              className="grid size-9 place-items-center rounded-full bg-wine text-ivory disabled:opacity-50"
              aria-label="Send"
            >
              <Send className="size-4" />
            </button>
          </div>
        </div>
      </aside>
    </>
  );
}
