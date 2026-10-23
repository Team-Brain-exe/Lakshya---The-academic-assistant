import { createFileRoute } from "@tanstack/react-router";
import { GripVertical, Plus, Search, Send, X } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { Toaster } from "@/components/ui/sonner";
import { Shell } from "@/components/lk/Shell";
import { Btn, Card, Chip, CO, Field, inputCls, PageHead, type Status } from "@/components/lk/ui";

export const Route = createFileRoute("/faculty/quiz-builder")({
  head: () => ({ meta: [
    { title: "Quiz Builder · LAKSHYA" },
    { name: "description", content: "Build and publish quizzes from approved questions." },
    { property: "og:title", content: "Quiz Builder · LAKSHYA" },
    { property: "og:description", content: "A paper-planner for composing quizzes." },
  ] }),
  component: Page,
});

const BANK = [
  { id: 1, q: "Which normal form eliminates transitive dependencies?", co: 3 },
  { id: 2, q: "Which SQL clause filters groups after aggregation?", co: 2 },
  { id: 3, q: "A lossless decomposition guarantees…", co: 3 },
  { id: 4, q: "Strict 2PL guarantees which schedule property?", co: 4 },
  { id: 5, q: "Primary key constraint enforces…", co: 1 },
  { id: 6, q: "Which join returns unmatched rows from both tables?", co: 2 },
];

function Page() {
  const [sel, setSel] = useState<number[]>([1, 2]);
  const [term, setTerm] = useState("");
  const [drag, setDrag] = useState<number | null>(null);
  const picked = sel.map((id) => BANK.find((b) => b.id === id)!);
  const perCO = [1, 2, 3, 4, 5, 6].map((n) => picked.filter((p) => p.co === n).length);
  const move = (to: number) => { if (drag === null) return; const n = [...sel]; const [x] = n.splice(drag, 1); n.splice(to, 0, x!); setSel(n); setDrag(to); };

  return (
    <Shell role="faculty">
      <Toaster />
      <PageHead eyebrow="Teaching · Planner" title="Compose a quiz" right={<Btn size="lg" onClick={() => toast("Quiz 4 published to Sections A & B")}><Send className="size-4" />Publish quiz</Btn>} />
      <div className="grid grid-cols-12 gap-5">
        <Card className="col-span-12">
          <div className="grid grid-cols-4 gap-4">
            <Field label="Quiz title"><input className={inputCls} defaultValue="Quiz 4 · Normalisation & SQL" /></Field>
            <Field label="Module"><select className={inputCls}><option>M3 · Normalisation</option></select></Field>
            <Field label="Opens"><input type="datetime-local" className={inputCls} defaultValue="2026-10-23T09:00" /></Field>
            <Field label="Closes"><input type="datetime-local" className={inputCls} defaultValue="2026-10-25T23:59" /></Field>
          </div>
        </Card>

        <Card className="col-span-6" title="Question bank" action={<span className="font-mono text-[11px] text-muted-foreground">approved only</span>}>
          <div className="relative mb-3"><Search className="absolute left-4 top-3.5 size-4 text-muted-foreground" /><input value={term} onChange={(e) => setTerm(e.target.value)} placeholder="Search questions" className={`${inputCls} pl-10`} /></div>
          <div className="mb-3 flex gap-1.5">{[1, 2, 3, 4, 5, 6].map((n) => <CO key={n} n={n} />)}</div>
          {BANK.filter((b) => b.q.toLowerCase().includes(term.toLowerCase())).map((b) => (
            <div key={b.id} className="flex items-center gap-3 border-b border-dashed border-wine/20 py-3 last:border-0">
              <CO n={b.co} /><span className="flex-1 text-sm">{b.q}</span>
              <Btn size="sm" variant={sel.includes(b.id) ? "ghost" : "secondary"} disabled={sel.includes(b.id)} onClick={() => setSel([...sel, b.id])}><Plus className="size-3.5" />{sel.includes(b.id) ? "Added" : "Add"}</Btn>
            </div>
          ))}
        </Card>

        <div className="col-span-6 space-y-5">
          <div className="paper-wine p-5">
            <div className="flex items-end justify-between"><div><div className="eyebrow !text-beige/70">Total marks</div><div className="display text-5xl text-ivory">{sel.length * 2}</div></div>
              <div className="flex gap-3">{perCO.map((c, i) => <div key={i} className="text-center"><div className="font-mono text-lg">{c}</div><div className="font-mono text-[10px] text-beige/70">CO{i + 1}</div></div>)}</div>
            </div>
          </div>
          <Card title={`Selected · ${sel.length}`}>
            {picked.length === 0 && <p className="py-8 text-center font-serif text-lg text-muted-foreground">Nothing pinned yet — add from the bank.</p>}
            {picked.map((p, i) => (
              <div key={p.id} draggable onDragStart={() => setDrag(i)} onDragOver={(e) => { e.preventDefault(); move(i); }} onDragEnd={() => setDrag(null)} className={`mb-2 flex cursor-grab items-center gap-3 rounded-xl border border-wine/15 bg-beige/40 px-3 py-2.5 ${drag === i ? "opacity-50" : ""}`}>
                <GripVertical className="size-4 text-wine/50" /><span className="font-mono text-xs text-wine">{i + 1}.</span><span className="flex-1 text-sm">{p.q}</span><CO n={p.co} />
                <button onClick={() => setSel(sel.filter((x) => x !== p.id))} aria-label="Remove"><X className="size-4 text-wine" /></button>
              </div>
            ))}
          </Card>
        </div>

        <Card className="col-span-12" title="Existing quizzes">
          <div className="grid grid-cols-4 gap-4">
            {([["Quiz 1 · Intro", "Closed", "12 Sep"], ["Quiz 2 · SQL", "Closed", "28 Sep"], ["Quiz 3 · Transactions", "Published", "21 Oct"], ["Quiz 4 · Normalisation", "Draft", "—"]] as [string, Status, string][]).map(([t, s, d]) => (
              <div key={t} className="rounded-xl border border-wine/15 p-4"><Chip s={s} /><div className="mt-2 font-serif text-lg text-wine">{t}</div><div className="font-mono text-[11px] text-muted-foreground">opens {d}</div></div>
            ))}
          </div>
        </Card>
      </div>
    </Shell>
  );
}
