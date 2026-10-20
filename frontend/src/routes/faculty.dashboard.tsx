import { createFileRoute, Link } from "@tanstack/react-router";
import { AlertTriangle, ClipboardCheck, FileUp, PenLine, Star } from "lucide-react";
import { Shell } from "@/components/lk/Shell";
import { Bar, Card, CO, PageHead } from "@/components/lk/ui";

export const Route = createFileRoute("/faculty/dashboard")({
  head: () => ({ meta: [
    { title: "Faculty Dashboard · LAKSHYA" },
    { name: "description", content: "Course outcomes, questions and quizzes at a glance." },
    { property: "og:title", content: "Faculty Dashboard · LAKSHYA" },
    { property: "og:description", content: "Your academic journal for teaching." },
  ] }),
  component: Page,
});

const CO_ATT = [72, 58, 81, 44, 66, 38];

function Page() {
  return (
    <Shell role="faculty">
      <PageHead eyebrow="Monday · 19 October 2026" title={<>Good evening, <em className="font-medium">Dr. Rao</em></>} sub="Two course outcomes need attention before Quiz 3 opens on Friday." />

      <div className="grid grid-cols-12 gap-5">
        {[
          ["Modules uploaded", "4/5", "Module 5 pending"],
          ["Awaiting review", "23", "AI drafts this week"],
          ["Published quizzes", "3", "1 closes Thursday"],
          ["Class CO attainment", "60%", "Target 60%"],
        ].map(([l, v, s], i) => (
          <div key={l} className={i === 1 ? "paper-wine col-span-3 p-5" : "paper col-span-3 p-5"}>
            <div className={i === 1 ? "eyebrow !text-beige/70" : "eyebrow"}>{l}</div>
            <div className={`display mt-2 text-5xl ${i === 1 ? "text-ivory" : "text-wine"}`}>{v}</div>
            <div className={`mt-1 font-mono text-[11px] ${i === 1 ? "text-beige/80" : "text-muted-foreground"}`}>{s}</div>
          </div>
        ))}

        <Card className="col-span-8" title="Course outcome attainment" action={<span className="font-mono text-[11px] text-muted-foreground">— target 60%</span>}>
          <div className="relative flex h-56 items-end gap-6 border-b border-wine/20 px-2">
            <div className="absolute inset-x-0 border-t border-dashed border-oxblood" style={{ bottom: "60%" }} />
            {CO_ATT.map((v, i) => (
              <div key={i} className="flex flex-1 flex-col items-center gap-2">
                <span className="font-mono text-xs">{v}%</span>
                <div className={`w-full rounded-t-xl ${v < 60 ? "bg-wine" : "stripes-blue border border-dusty"}`} style={{ height: `${v * 1.8}px` }} />
              </div>
            ))}
          </div>
          <div className="mt-3 flex gap-6 px-2">{CO_ATT.map((_, i) => <div key={i} className="flex flex-1 justify-center"><CO n={i + 1} /></div>)}</div>
        </Card>

        <div className="col-span-4 space-y-5">
          <div className="paper-wine p-6">
            <div className="flex items-center gap-2"><AlertTriangle className="size-4" /><span className="eyebrow !text-beige/80">Weak outcomes</span></div>
            {[[4, 44, "Transaction concurrency"], [6, 38, "Query optimisation"]].map(([n, v, t]) => (
              <div key={n} className="mt-4 rounded-xl bg-oxblood/60 p-3">
                <div className="flex items-center justify-between"><CO n={n as number} className="!bg-ivory !text-wine" /><span className="font-mono text-sm">{v}%</span></div>
                <div className="mt-1 font-serif text-lg">{t}</div>
              </div>
            ))}
          </div>
          <div className="grid gap-2">
            {[["/faculty/upload", "Upload slides", FileUp], ["/faculty/review", "Review questions", ClipboardCheck], ["/faculty/quiz-builder", "Create quiz", PenLine]].map(([to, t, I]: any) => (
              <Link key={t} to={to} className="paper flex items-center gap-3 !rounded-full px-5 py-3 font-medium text-wine hover:bg-beige"><I className="size-4" />{t}<Star className="ml-auto size-3 fill-wine" /></Link>
            ))}
          </div>
        </div>

        <Card className="col-span-4" title="Upcoming events">
          {[["21 Oct", "Quiz 3 opens", "Module 3"], ["24 Oct", "Internal Assessment 2", "Exam"], ["28 Oct", "Lab record due", "Assignment"]].map(([d, t, k]) => (
            <div key={t} className="flex items-center gap-4 border-b border-dashed border-wine/20 py-3 last:border-0">
              <div className="stamp bg-beige px-3 py-2 text-center font-mono text-xs text-wine">{d}</div>
              <div><div className="font-medium">{t}</div><div className="text-xs text-muted-foreground">{k}</div></div>
            </div>
          ))}
        </Card>
        <Card className="col-span-4" title="Quiz deadlines">
          {[["Quiz 2 · Normalisation", 82], ["Quiz 3 · Transactions", 12]].map(([t, v]) => (
            <div key={t as string} className="mb-4"><div className="mb-1.5 flex justify-between text-sm"><span>{t}</span><span className="font-mono text-xs">{v}% submitted</span></div><Bar v={v as number} tone="blue" /></div>
          ))}
        </Card>
        <Card className="col-span-4" title="Recent activity">
          <ul className="space-y-3 text-sm">
            {["Approved 12 questions for CO3", "Module 4 processed · 48 chunks", "Quiz 2 published to Sec A, B", "Exported CO sheet · Module 2"].map((a, i) => (
              <li key={a} className="flex gap-3"><span className="font-mono text-[10px] text-muted-foreground">{["2h", "5h", "1d", "2d"][i]}</span>{a}</li>
            ))}
          </ul>
        </Card>
      </div>
    </Shell>
  );
}
