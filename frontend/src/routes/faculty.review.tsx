import { createFileRoute } from "@tanstack/react-router";
import { Check, Pencil, Sparkle, X } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { Toaster } from "@/components/ui/sonner";
import { Shell } from "@/components/lk/Shell";
import { Btn, Card, Chip, CO, Field, inputCls, PageHead, type Status } from "@/components/lk/ui";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/faculty/review")({
  head: () => ({ meta: [
    { title: "Question Review · LAKSHYA" },
    { name: "description", content: "Moderate AI-generated and faculty questions." },
    { property: "og:title", content: "Question Review · LAKSHYA" },
    { property: "og:description", content: "Approve, edit or reject questions before they reach students." },
  ] }),
  component: Page,
});

type Q = { id: number; q: string; o: string[]; a: number; ex: string; co: number; src: "AI" | "Faculty"; diff: string; s: Status; m: number };
const INIT: Q[] = [
  { id: 1, m: 3, q: "Which normal form eliminates transitive dependencies?", o: ["1NF", "2NF", "3NF", "BCNF"], a: 2, ex: "3NF requires no non-key attribute to depend transitively on a key.", co: 3, src: "AI", diff: "Easy", s: "Draft" },
  { id: 2, m: 3, q: "A relation R(A,B,C) with A→B and B→C is in which highest normal form?", o: ["1NF", "2NF", "3NF", "BCNF"], a: 1, ex: "B→C is a transitive dependency through a non-key attribute.", co: 3, src: "AI", diff: "Medium", s: "Draft" },
  { id: 3, m: 2, q: "Which SQL clause filters groups after aggregation?", o: ["WHERE", "HAVING", "GROUP BY", "ORDER BY"], a: 1, ex: "HAVING is applied after GROUP BY.", co: 2, src: "Faculty", diff: "Easy", s: "Approved" },
  { id: 4, m: 4, q: "Strict 2PL guarantees which property of schedules?", o: ["Deadlock freedom", "Cascadeless", "Starvation freedom", "Serial order"], a: 1, ex: "Holding exclusive locks until commit prevents cascading aborts.", co: 4, src: "AI", diff: "Hard", s: "Draft" },
];

function Page() {
  const [qs, setQs] = useState(INIT);
  const [f, setF] = useState<Status | "All">("All");
  const set = (id: number, s: Status) => { setQs((p) => p.map((q) => (q.id === id ? { ...q, s } : q))); toast(`Question ${s.toLowerCase()}`); };
  const vis = qs.filter((q) => f === "All" || q.s === f);
  const count = (s: Status) => qs.filter((q) => q.s === s).length;

  return (
    <Shell role="faculty">
      <Toaster />
      <PageHead eyebrow="Teaching · Moderation" title="Question review" right={<Btn onClick={() => { setQs((p) => p.map((q) => (vis.includes(q) && q.s === "Draft" ? { ...q, s: "Approved" } : q))); toast("All visible drafts approved"); }}><Check className="size-4" />Approve all visible</Btn>} />
      <div className="grid grid-cols-12 gap-5">
        <div className="col-span-8 space-y-4">
          <div className="flex flex-wrap items-center gap-2">
            {(["All", "Draft", "Approved", "Rejected"] as const).map((s) => (
              <button key={s} onClick={() => setF(s)} className={cn("rounded-full border px-4 py-1.5 text-sm", f === s ? "border-wine bg-wine text-ivory" : "border-wine/30 text-wine")}>
                {s} {s !== "All" && <span className="ml-1 font-mono text-[11px] opacity-70">{count(s)}</span>}
              </button>
            ))}
            <div className="flex-1" />
            {["Module", "CO", "Source", "Difficulty"].map((x) => <select key={x} className="h-9 rounded-full border border-wine/30 bg-ivory px-3 text-xs text-wine"><option>{x}: All</option></select>)}
          </div>
          {vis.map((q) => (
            <article key={q.id} className="paper p-5">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-mono text-[11px] text-muted-foreground">Q{String(q.id).padStart(3, "0")} · M{q.m}</span>
                <CO n={q.co} />
                <span className={cn("rounded-full px-2 py-0.5 text-[11px]", q.src === "AI" ? "bg-dusty text-oxblood" : "bg-beige text-wine")}>{q.src === "AI" ? "✦ AI" : "Faculty"}</span>
                <span className="text-[11px] text-muted-foreground">{q.diff}</span>
                <div className="flex-1" /><Chip s={q.s} />
              </div>
              <p className="mt-3 font-serif text-xl font-semibold text-espresso">{q.q}</p>
              <div className="mt-3 grid grid-cols-2 gap-2">
                {q.o.map((o, i) => (
                  <div key={o} className={cn("flex items-center gap-2 rounded-xl border px-3 py-2 text-sm", i === q.a ? "border-success bg-success/10" : "border-wine/15")}>
                    <span className="font-mono text-xs text-muted-foreground">{"ABCD"[i]}</span>{o}{i === q.a && <Check className="ml-auto size-4 text-success" />}
                  </div>
                ))}
              </div>
              <p className="mt-3 border-l-2 border-dusty pl-3 text-sm text-muted-foreground"><b className="text-espresso">Why:</b> {q.ex}</p>
              <div className="mt-4 flex justify-end gap-2">
                <Btn variant="ghost" size="sm"><Pencil className="size-3.5" />Edit</Btn>
                <Btn variant="secondary" size="sm" onClick={() => set(q.id, "Rejected")}><X className="size-3.5" />Reject</Btn>
                <Btn size="sm" onClick={() => set(q.id, "Approved")}><Check className="size-3.5" />Approve</Btn>
              </div>
            </article>
          ))}
        </div>
        <div className="col-span-4">
          <div className="sticky top-24 space-y-5">
            <div className="grid grid-cols-3 gap-3">
              {(["Draft", "Approved", "Rejected"] as const).map((s) => (
                <div key={s} className="paper p-4 text-center"><div className="display text-4xl text-wine">{count(s)}</div><div className="eyebrow">{s}</div></div>
              ))}
            </div>
            <div className="stripes-blue rounded-[1.25rem] p-2">
              <Card className="!shadow-none" title="Generate questions">
                <div className="space-y-3">
                  <Field label="Module"><select className={inputCls}><option>M3 · Normalisation</option></select></Field>
                  <Field label="Course outcome"><select className={inputCls}><option>CO3</option></select></Field>
                  <Field label="Difficulty"><div className="grid grid-cols-3 gap-1 rounded-full bg-beige p-1">{["Easy", "Medium", "Hard"].map((d, i) => <span key={d} className={cn("rounded-full py-1.5 text-center text-xs", i === 1 ? "bg-wine text-ivory" : "text-wine")}>{d}</span>)}</div></Field>
                  <Field label="Count"><input type="number" defaultValue={10} className={inputCls} /></Field>
                  <Btn className="w-full" onClick={() => toast("Generating 10 questions…")}><Sparkle className="size-4" />Generate</Btn>
                </div>
              </Card>
            </div>
          </div>
        </div>
      </div>
    </Shell>
  );
}
