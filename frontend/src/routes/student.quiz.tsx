import { createFileRoute } from "@tanstack/react-router";
import { Check, Clock, RotateCcw } from "lucide-react";
import { useState } from "react";
import { Shell } from "@/components/lk/Shell";
import { Bar, Btn, Card, CO, PageHead } from "@/components/lk/ui";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/student/quiz")({
  head: () => ({ meta: [
    { title: "Quiz Attempt · LAKSHYA" },
    { name: "description", content: "Attempt your quiz and view your course outcome results." },
    { property: "og:title", content: "Quiz Attempt · LAKSHYA" },
    { property: "og:description", content: "Take Quiz 3 on Transactions." },
  ] }),
  component: Page,
});

const QS = [
  { q: "Which property ensures a transaction is all-or-nothing?", o: ["Atomicity", "Consistency", "Isolation", "Durability"] },
  { q: "Strict 2PL guarantees which schedule property?", o: ["Deadlock freedom", "Cascadeless", "Starvation freedom", "Serial order"] },
  { q: "A dirty read occurs when…", o: ["Reading committed data", "Reading uncommitted data", "Writing twice", "Locking a row"] },
  { q: "Which isolation level prevents phantom reads?", o: ["Read uncommitted", "Read committed", "Repeatable read", "Serializable"] },
  { q: "The wait-for graph is used to detect…", o: ["Deadlocks", "Phantoms", "Lost updates", "Cascades"] },
];

function Page() {
  const [i, setI] = useState(0);
  const [ans, setAns] = useState<(number | null)[]>(QS.map(() => null));
  const [saved, setSaved] = useState(false);
  const [confirm, setConfirm] = useState(false);
  const [done, setDone] = useState(false);
  const pick = (k: number) => { const a = [...ans]; a[i] = k; setAns(a); setSaved(true); setTimeout(() => setSaved(false), 1200); };
  const unanswered = ans.map((a, k) => (a === null ? k + 1 : null)).filter(Boolean);

  if (done) return (
    <Shell role="student">
      <PageHead eyebrow="Quiz 3 · Attempt 1 of 2" title="Your result" />
      <div className="grid grid-cols-12 gap-5">
        <div className="paper-wine col-span-5 p-8">
          <div className="eyebrow !text-beige/70">Total score</div>
          <div className="display mt-2 text-8xl text-ivory">7<span className="text-4xl text-beige">/10</span></div>
          <div className="font-mono text-beige">70% · 1 attempt remaining</div>
          <div className="mt-6 flex gap-3"><Btn variant="onWine">Review answers</Btn><Btn variant="ghost" className="text-ivory hover:bg-ivory/10" onClick={() => { setDone(false); setAns(QS.map(() => null)); setI(0); }}><RotateCcw className="size-4" />Retry</Btn></div>
        </div>
        <Card className="col-span-7" title="By course outcome">
          {([[4, 75], [5, 50], [6, 80]] as [number, number][]).map(([n, v]) => <div key={n} className="mb-4 flex items-center gap-3"><CO n={n} /><div className="flex-1"><Bar v={v} target={60} tone={v < 60 ? "wine" : "blue"} /></div><span className="font-mono text-sm">{v}%</span></div>)}
        </Card>
      </div>
    </Shell>
  );

  return (
    <Shell role="student">
      <PageHead eyebrow="Attempt 1 of 2" title="Quiz 3 · Transactions" right={<div className="flex items-center gap-2 rounded-full bg-wine px-4 py-2 font-mono text-sm text-ivory"><Clock className="size-4" />Closes in 2d 06:14:22</div>} />
      <div className="grid grid-cols-12 gap-5">
        <Card className="col-span-8">
          <div className="flex items-center justify-between text-sm"><span className="font-mono text-wine">Question {i + 1} of {QS.length}</span><span className={cn("text-xs text-success transition", saved ? "opacity-100" : "opacity-0")}>✓ Progress saved</span></div>
          <div className="mt-2"><Bar v={((i + 1) / QS.length) * 100} /></div>
          <p className="mt-8 font-serif text-3xl font-semibold text-espresso">{QS[i]!.q}</p>
          <div className="mt-6 space-y-3">
            {QS[i]!.o.map((o, k) => (
              <button key={o} onClick={() => pick(k)} className={cn("flex w-full items-center gap-4 rounded-2xl border px-5 py-4 text-left transition", ans[i] === k ? "border-wine bg-wine text-ivory" : "border-wine/20 bg-ivory hover:border-wine/60")}>
                <span className={cn("grid size-7 place-items-center rounded-full border font-mono text-xs", ans[i] === k ? "border-ivory" : "border-wine/40 text-wine")}>{"ABCD"[k]}</span>{o}
              </button>
            ))}
          </div>
          <div className="mt-8 flex justify-between">
            <Btn variant="secondary" disabled={i === 0} onClick={() => setI(i - 1)}>Previous</Btn>
            {i < QS.length - 1 ? <Btn onClick={() => setI(i + 1)}>Next</Btn> : <Btn onClick={() => setConfirm(true)}>Submit quiz</Btn>}
          </div>
        </Card>
        <Card className="col-span-4" title="Navigator">
          <div className="grid grid-cols-5 gap-2">
            {QS.map((_, k) => <button key={k} onClick={() => setI(k)} className={cn("aspect-square rounded-xl border font-mono text-sm", ans[k] !== null ? "border-wine bg-wine text-ivory" : "border-wine/30 text-wine", i === k && "ring-2 ring-dusty ring-offset-2 ring-offset-ivory")}>{k + 1}</button>)}
          </div>
          <div className="mt-4 flex gap-4 text-xs text-muted-foreground"><span className="flex items-center gap-1.5"><span className="size-3 rounded bg-wine" />Answered</span><span className="flex items-center gap-1.5"><span className="size-3 rounded border border-wine/30" />Unanswered</span></div>
          <Btn variant="secondary" className="mt-6 w-full" onClick={() => setConfirm(true)}>Submit quiz</Btn>
        </Card>
      </div>
      {confirm && (
        <div className="fixed inset-0 z-50 grid place-items-center bg-oxblood/40 p-4">
          <div className="paper w-full max-w-md p-8">
            <h2 className="display text-3xl">Submit this attempt?</h2>
            <p className="mt-2 text-sm text-muted-foreground">{unanswered.length ? <>You have <b className="text-wine">{unanswered.length} unanswered</b>: Q{unanswered.join(", Q")}.</> : "All questions answered."} You'll have 1 attempt left.</p>
            <div className="mt-6 flex justify-end gap-2"><Btn variant="ghost" onClick={() => setConfirm(false)}>Keep working</Btn><Btn onClick={() => { setConfirm(false); setDone(true); }}><Check className="size-4" />Submit</Btn></div>
          </div>
        </div>
      )}
    </Shell>
  );
}
