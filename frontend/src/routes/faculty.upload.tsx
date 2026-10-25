import { createFileRoute } from "@tanstack/react-router";
import { AlertTriangle, FileText, UploadCloud } from "lucide-react";
import { useState } from "react";
import { Shell } from "@/components/lk/Shell";
import { Bar, Btn, Card, Chip, CO, Field, inputCls, PageHead, type Status } from "@/components/lk/ui";

export const Route = createFileRoute("/faculty/upload")({
  head: () => ({ meta: [
    { title: "Modules & CO Coverage · LAKSHYA" },
    { name: "description", content: "Upload module slides and check course outcome coverage." },
    { property: "og:title", content: "Modules & CO Coverage · LAKSHYA" },
    { property: "og:description", content: "Upload slides and map them to course outcomes." },
  ] }),
  component: Page,
});

const MODS: [number, string, Status, number][] = [
  [1, "Introduction to DBMS", "Done", 42],
  [2, "Relational Model & SQL", "Done", 61],
  [3, "Normalisation", "Done", 38],
  [4, "Transactions & Concurrency", "Processing", 0],
  [5, "Query Optimisation", "Failed", 0],
];
const COV = [34, 52, 41, 12, 18, 0];

function Page() {
  const [sel, setSel] = useState(3);
  const [prog, setProg] = useState<number | null>(null);
  const start = () => { setProg(0); const t = setInterval(() => setProg((p) => { if (p === null || p >= 100) { clearInterval(t); return 100; } return p + 10; }), 200); };

  return (
    <Shell role="faculty">
      <PageHead eyebrow="Teaching · Modules" title="Slides & CO coverage" sub="Upload a module deck. Lakshya splits it into chunks and maps each to course outcomes." />
      <div className="grid grid-cols-12 gap-5">
        <Card className="col-span-7">
          <button onClick={start} className="flex w-full flex-col items-center rounded-2xl border-2 border-dashed border-wine/50 bg-beige/30 px-6 py-12 text-center hover:bg-beige/60">
            <UploadCloud className="size-10 text-wine" strokeWidth={1.3} />
            <div className="mt-3 font-serif text-2xl text-wine">Drop your PPT here</div>
            <div className="text-sm text-muted-foreground">or click to browse · .ppt, .pptx up to 50 MB</div>
          </button>
          <div className="mt-5 grid grid-cols-3 gap-4">
            <Field label="Module no."><input className={inputCls} defaultValue="5" /></Field>
            <div className="col-span-2"><Field label="Module title"><input className={inputCls} defaultValue="Query Optimisation" /></Field></div>
          </div>
          {prog !== null && (
            <div className="mt-5 rounded-xl bg-beige/50 p-4">
              <div className="mb-2 flex justify-between text-sm"><span className="flex items-center gap-2"><FileText className="size-4 text-wine" />M5_query_opt.pptx</span><span className="font-mono text-xs">{prog < 100 ? `Uploading ${prog}%` : "Processing chunks…"}</span></div>
              <Bar v={prog} />
            </div>
          )}
          <div className="mt-5 flex justify-end"><Btn onClick={start}>Upload & process</Btn></div>
        </Card>

        <Card className="col-span-5" title="CO coverage">
          {COV.map((v, i) => (
            <div key={i} className="mb-3 flex items-center gap-3"><CO n={i + 1} /><div className="flex-1"><Bar v={Math.max(v, 1) * 1.6} tone={v < 15 ? "wine" : "blue"} /></div><span className="w-16 text-right font-mono text-xs">{v} chunks</span></div>
          ))}
          <div className="mt-4 flex gap-3 rounded-xl border border-wine bg-wine/5 p-4">
            <AlertTriangle className="size-5 shrink-0 text-wine" />
            <div className="text-sm"><b className="text-wine">CO6 has no mapped slides.</b> Questions and study plans cannot cover it until slides are uploaded.</div>
          </div>
        </Card>

        <Card className="col-span-5" title="Modules">
          {MODS.map(([n, t, s, c]) => (
            <button key={n} onClick={() => setSel(n)} className={`mb-2 flex w-full items-center gap-3 rounded-xl px-3 py-3 text-left ${sel === n ? "bg-beige" : "hover:bg-beige/50"}`}>
              <span className="font-mono text-xs text-wine">M{n}</span><span className="flex-1 text-sm font-medium">{t}</span>
              <span className="font-mono text-[11px] text-muted-foreground">{c || "—"}</span><Chip s={s} />
            </button>
          ))}
        </Card>

        <Card className="col-span-7" title={`Module ${sel} · Slide chunks`}>
          <div className="divide-y divide-dashed divide-wine/20">
            {[[12, "Functional dependencies define how attributes relate…", [3]], [14, "Third normal form removes transitive dependency…", [3, 2]], [17, "Boyce–Codd normal form strengthens 3NF…", [3]], [21, "Decomposition must be lossless and preserve…", [2, 3]]].map(([s, t, cos]: any) => (
              <div key={s} className="flex items-start gap-4 py-3">
                <span className="stamp bg-dusty px-2 py-1 font-mono text-[11px] text-oxblood">#{s}</span>
                <p className="flex-1 text-sm">{t}</p>
                <div className="flex gap-1">{cos.map((c: number) => <CO key={c} n={c} />)}</div>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </Shell>
  );
}
