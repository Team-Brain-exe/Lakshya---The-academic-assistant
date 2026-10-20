import { createFileRoute } from "@tanstack/react-router";
import { Download } from "lucide-react";
import { useState } from "react";
import { Shell } from "@/components/lk/Shell";
import { Btn, Card, CO, PageHead } from "@/components/lk/ui";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/faculty/analytics")({
  head: () => ({ meta: [
    { title: "CO Sheet & Analytics · LAKSHYA" },
    { name: "description", content: "Course outcome attainment per student, with charts and exports." },
    { property: "og:title", content: "CO Sheet & Analytics · LAKSHYA" },
    { property: "og:description", content: "Professional CO attainment reporting." },
  ] }),
  component: Page,
});

const T = 60;
const ROWS: [string, string, number[]][] = [
  ["1RV22CS001", "Aarav Mehta", [78, 64, 82, 51, 70, 40]],
  ["1RV22CS007", "Diya Nair", [85, 72, 90, 66, 74, 58]],
  ["1RV22CS012", "Kabir Shah", [55, 48, 61, 32, 59, 22]],
  ["1RV22CS018", "Ananya S", [72, 66, 80, 44, 68, 39]],
  ["1RV22CS023", "Rohan Iyer", [68, 52, 77, 38, 62, 35]],
  ["1RV22CS031", "Meghna Pillai", [90, 81, 88, 72, 80, 61]],
];
const AVG = [0, 1, 2, 3, 4, 5].map((i) => Math.round(ROWS.reduce((s, r) => s + r[2][i]!, 0) / ROWS.length));
const DIST = [2, 5, 11, 18, 14, 6];

function Page() {
  const [scope, setScope] = useState<"Module" | "Semester">("Module");
  const [hover, setHover] = useState<number | null>(null);
  return (
    <Shell role="faculty">
      <PageHead eyebrow="Reports · Attainment" title="CO sheet" right={
        <div className="flex items-center gap-3">
          <div className="flex rounded-full bg-ivory p-1">{(["Module", "Semester"] as const).map((s) => <button key={s} onClick={() => setScope(s)} className={cn("rounded-full px-4 py-1.5 text-sm", scope === s ? "bg-wine text-ivory" : "text-wine")}>{s}</button>)}</div>
          <select className="h-10 rounded-full border border-wine/30 bg-ivory px-4 text-sm text-wine"><option>All sections</option><option>Section A</option></select>
          <Btn variant="secondary"><Download className="size-4" />Export to Excel</Btn>
        </div>
      } />
      <div className="grid grid-cols-12 gap-5">
        <Card className="col-span-7" title="Average score by CO">
          <div className="relative flex h-56 items-end gap-5 border-b border-l border-wine/20 pl-3">
            {AVG.map((v, i) => (
              <div key={i} onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(null)} className="relative flex flex-1 flex-col items-center justify-end" style={{ height: "100%" }}>
                {hover === i && <div className="absolute -top-2 rounded-md bg-oxblood px-2 py-1 font-mono text-[11px] text-ivory">{v}% avg</div>}
                <div className="absolute inset-x-0 border-t-2 border-dashed border-oxblood/70" style={{ bottom: `${T}%` }} />
                <div className={cn("w-full rounded-t-lg transition", v < T ? "bg-wine" : "bg-dusty", hover === i && "opacity-80")} style={{ height: `${v}%` }} />
              </div>
            ))}
          </div>
          <div className="mt-3 flex gap-5 pl-3">{AVG.map((_, i) => <div key={i} className="flex flex-1 justify-center"><CO n={i + 1} /></div>)}</div>
          <div className="mt-3 flex gap-4 text-xs text-muted-foreground"><span className="flex items-center gap-1.5"><span className="size-2.5 rounded-sm bg-dusty" />Meets target</span><span className="flex items-center gap-1.5"><span className="size-2.5 rounded-sm bg-wine" />Below target</span><span className="flex items-center gap-1.5"><span className="h-0 w-4 border-t-2 border-dashed border-oxblood" />Target {T}%</span></div>
        </Card>
        <Card className="col-span-5" title="Score distribution">
          <div className="flex h-56 items-end gap-2">{DIST.map((d, i) => <div key={i} className="flex flex-1 flex-col items-center gap-1"><span className="font-mono text-[10px]">{d}</span><div className="stripes-blue w-full rounded-t-md border border-dusty" style={{ height: `${d * 10}px` }} /></div>)}</div>
          <div className="mt-2 flex gap-2 font-mono text-[10px] text-muted-foreground">{["0-40", "40-50", "50-60", "60-70", "70-80", "80+"].map((l) => <span key={l} className="flex-1 text-center">{l}</span>)}</div>
        </Card>

        <Card className="col-span-12 !p-0 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-wine text-ivory"><tr>{["USN", "Name", "CO1", "CO2", "CO3", "CO4", "CO5", "CO6", "Total"].map((h, i) => <th key={h} className={cn("px-4 py-3 font-medium", i < 2 ? "text-left" : "text-right")}>{h}</th>)}</tr></thead>
            <tbody>
              {ROWS.map(([u, n, s]) => (
                <tr key={u} className="border-b border-wine/10 even:bg-beige/30">
                  <td className="px-4 py-3 font-mono text-xs">{u}</td><td className="px-4 py-3">{n}</td>
                  {s.map((v, i) => <td key={i} className="px-4 py-3 text-right font-mono"><span className={cn("rounded px-1.5 py-0.5", v < T && "bg-wine/10 font-semibold text-wine")}>{v}</span></td>)}
                  <td className="px-4 py-3 text-right font-mono font-semibold">{Math.round(s.reduce((a, b) => a + b) / 6)}</td>
                </tr>
              ))}
              <tr className="bg-dusty/40 font-medium"><td className="px-4 py-3 eyebrow !text-oxblood" colSpan={2}>Average attainment</td>{AVG.map((v, i) => <td key={i} className={cn("px-4 py-3 text-right font-mono", v < T && "text-wine")}>{v}</td>)}<td className="px-4 py-3 text-right font-mono">{Math.round(AVG.reduce((a, b) => a + b) / 6)}</td></tr>
            </tbody>
          </table>
        </Card>

        {[[4, "Concurrency control", "4 of 6 students below threshold. Weakest on lock-based protocols (M4 slides 8–15)."], [6, "Query optimisation", "No slides mapped yet. Upload Module 5 to enable practice questions."]].map(([n, t, d]) => (
          <div key={n as number} className="paper-wine col-span-6 p-6"><div className="flex items-center gap-3"><CO n={n as number} className="!bg-ivory !text-wine" /><span className="font-serif text-2xl">{t}</span><span className="ml-auto font-mono">{AVG[(n as number) - 1]}%</span></div><p className="mt-2 text-sm text-beige/90">{d}</p></div>
        ))}
      </div>
    </Shell>
  );
}
