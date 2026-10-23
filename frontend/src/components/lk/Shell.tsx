import { Link, useRouterState } from "@tanstack/react-router";
import {
  BarChart3, Bell, BookOpen, CalendarDays, ChevronDown, ClipboardCheck, FileUp, Home, Layers, LogOut,
  MessageCircle, PenLine, Send, Sparkle, Star, TrendingUp, X,
} from "lucide-react";
import { useState, type ReactNode } from "react";
import { cn } from "@/lib/utils";

type Role = "faculty" | "student";
const NAV: Record<Role, { label: string; items: { to: string; t: string; i: typeof Home }[] }[]> = {
  faculty: [
    { label: "Overview", items: [{ to: "/faculty/dashboard", t: "Dashboard", i: Home }] },
    { label: "Teaching", items: [
      { to: "/faculty/upload", t: "Modules & CO", i: FileUp },
      { to: "/faculty/review", t: "Question Review", i: ClipboardCheck },
      { to: "/faculty/quiz-builder", t: "Quiz Builder", i: PenLine },
    ] },
    { label: "Reports", items: [{ to: "/faculty/analytics", t: "CO Sheet", i: BarChart3 }] },
  ],
  student: [
    { label: "Overview", items: [{ to: "/student/home", t: "Home", i: Home }] },
    { label: "Learn", items: [
      { to: "/student/quiz", t: "Quizzes", i: ClipboardCheck },
      { to: "/student/home", t: "My Progress", i: TrendingUp },
      { to: "/student/home", t: "Flashcards", i: Layers },
      { to: "/student/home", t: "Calendar", i: CalendarDays },
    ] },
  ],
};

export function Shell({ role, children }: { role: Role; children: ReactNode }) {
  const path = useRouterState({ select: (s) => s.location.pathname });
  const [open, setOpen] = useState(false);
  const who = role === "faculty" ? { n: "Dr. Meera Rao", id: "Faculty · CSE" } : { n: "Ananya S", id: "1RV22CS018" };

  return (
    <div className="flex min-h-screen w-full">
      <aside className="sticky top-0 flex h-screen w-64 shrink-0 flex-col bg-oxblood px-4 py-6 text-beige">
        <Link to="/" className="flex items-center gap-2 px-2">
          <span className="grid size-9 place-items-center rounded-full border border-beige/40"><Star className="size-4 fill-beige" /></span>
          <span>
            <span className="block font-serif text-2xl font-bold tracking-[0.12em] text-ivory">LAKSHYA</span>
            <span className="eyebrow block !text-[9px] !text-beige/60">The Academic Assistant</span>
          </span>
        </Link>
        <nav className="mt-8 flex-1 space-y-6">
          {NAV[role].map((g) => (
            <div key={g.label}>
              <div className="eyebrow mb-2 border-b border-beige/15 px-2 pb-1 !text-beige/50">{g.label}</div>
              {g.items.map((it) => {
                const active = path === it.to;
                return (
                  <Link key={it.t} to={it.to} className={cn("mb-1 flex items-center gap-3 rounded-full px-3 py-2 text-sm transition", active ? "bg-ivory font-medium text-wine" : "text-beige/80 hover:bg-beige/10")}>
                    <it.i className="size-4" strokeWidth={1.6} />{it.t}
                  </Link>
                );
              })}
            </div>
          ))}
        </nav>
        <div className="rounded-2xl bg-wine p-3">
          <div className="flex items-center gap-3">
            <div className="grid size-10 place-items-center rounded-full bg-beige font-serif text-lg font-bold text-wine">{who.n[0]}{who.n.split(" ")[1]?.[0]}</div>
            <div className="min-w-0">
              <div className="truncate text-sm font-medium text-ivory">{who.n}</div>
              <div className="font-mono text-[10px] text-beige/70">{who.id}</div>
            </div>
          </div>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-20 flex h-16 items-center gap-3 border-b border-wine/15 bg-beige/95 px-8 backdrop-blur-sm">
          <button className="flex items-center gap-2 rounded-full bg-wine px-4 py-1.5 text-sm text-ivory">
            <BookOpen className="size-4" /> 21CS53 · Database Systems <ChevronDown className="size-3.5" />
          </button>
          <span className="rounded-full border border-wine/30 px-3 py-1 font-mono text-[11px] text-wine">SEM 5 · Module 3</span>
          <div className="flex-1" />
          <span className="rounded-full bg-dusty px-3 py-1 text-xs font-medium capitalize text-oxblood">{role}</span>
          <span className="font-mono text-xs text-muted-foreground">{role === "student" ? who.id : who.n}</span>
          <button className="relative grid size-9 place-items-center rounded-full hover:bg-wine/10" aria-label="Notifications">
            <Bell className="size-4 text-wine" /><span className="absolute right-2 top-2 size-1.5 rounded-full bg-wine" />
          </button>
          <Link to="/" className="grid size-9 place-items-center rounded-full hover:bg-wine/10" aria-label="Log out"><LogOut className="size-4 text-wine" /></Link>
        </header>
        <main className="flex-1 px-8 py-8">{children}</main>
      </div>

      <button onClick={() => setOpen(true)} className="fixed bottom-6 right-6 z-30 flex items-center gap-2 rounded-full bg-wine px-5 py-3 text-sm font-medium text-ivory shadow-[var(--shadow-lift)] hover:bg-oxblood">
        <Sparkle className="size-4 fill-ivory" /> Ask Lakshya
      </button>
      <Assistant open={open} onClose={() => setOpen(false)} />
    </div>
  );
}

function Assistant({ open, onClose }: { open: boolean; onClose: () => void }) {
  return (
    <>
      <div onClick={onClose} className={cn("fixed inset-0 z-40 bg-oxblood/30 transition", open ? "opacity-100" : "pointer-events-none opacity-0")} />
      <aside className={cn("fixed right-0 top-0 z-50 flex h-screen w-[420px] flex-col bg-ivory shadow-[var(--shadow-lift)] transition-transform duration-300", open ? "translate-x-0" : "translate-x-full")}>
        <div className="paper-wine torn-bottom !rounded-none px-6 pt-5">
          <div className="flex items-center justify-between">
            <div className="eyebrow !text-beige/70">Notebook · Today</div>
            <button onClick={onClose} aria-label="Close"><X className="size-4" /></button>
          </div>
          <h2 className="display mt-1 text-3xl !text-ivory">Ask Lakshya</h2>
          <p className="pb-3 text-xs text-beige/80">Answers grounded in your course slides.</p>
        </div>
        <div className="flex-1 space-y-4 overflow-y-auto p-5" style={{ backgroundImage: "repeating-linear-gradient(transparent 0 27px, oklch(0.79 0.035 245 / 35%) 27px 28px)" }}>
          <div className="ml-auto max-w-[80%] rounded-2xl rounded-br-sm bg-wine px-4 py-2.5 text-sm text-ivory">Explain 3NF with an example?</div>
          <div className="max-w-[88%] rounded-2xl rounded-bl-sm bg-dusty/60 px-4 py-3 text-sm">
            A relation is in 3NF if it is in 2NF and no non-key attribute depends transitively on the key.
            <div className="mt-2 flex flex-wrap gap-1.5">
              <span className="rounded-full bg-ivory px-2 py-0.5 font-mono text-[10px] text-wine">M3 · Slide 14</span>
              <span className="rounded-full bg-ivory px-2 py-0.5 font-mono text-[10px] text-wine">M3 · Slide 17</span>
            </div>
          </div>
          <div className="flex gap-1 px-2"><span className="size-1.5 animate-bounce rounded-full bg-wine" /><span className="size-1.5 animate-bounce rounded-full bg-wine [animation-delay:.15s]" /><span className="size-1.5 animate-bounce rounded-full bg-wine [animation-delay:.3s]" /></div>
        </div>
        <div className="border-t border-wine/15 p-4">
          <div className="mb-3 flex flex-wrap gap-1.5">
            {["Summarise Module 3", "Quiz me on CO2", "What's due this week?"].map((s) => (
              <button key={s} className="rounded-full border border-wine/30 px-3 py-1 text-xs text-wine hover:bg-wine/10">{s}</button>
            ))}
          </div>
          <div className="flex items-center gap-2 rounded-full border border-wine/30 bg-beige/40 py-1 pl-4 pr-1">
            <MessageCircle className="size-4 text-wine/60" />
            <input placeholder="Ask about your course…" className="flex-1 bg-transparent text-sm outline-none" />
            <button className="grid size-9 place-items-center rounded-full bg-wine text-ivory" aria-label="Send"><Send className="size-4" /></button>
          </div>
        </div>
      </aside>
    </>
  );
}
