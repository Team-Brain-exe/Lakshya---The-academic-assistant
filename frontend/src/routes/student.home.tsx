import { createFileRoute, Link } from "@tanstack/react-router";
import { CalendarDays, ClipboardCheck, Layers, MessageCircle, NotebookPen, Paperclip, TrendingUp } from "lucide-react";
import { Shell } from "@/components/lk/Shell";
import { Bar, Btn, Card, CO, PageHead } from "@/components/lk/ui";

export const Route = createFileRoute("/student/home")({
  head: () => ({ meta: [
    { title: "Student Home · LAKSHYA" },
    { name: "description", content: "Your quizzes, deadlines and course outcome progress." },
    { property: "og:title", content: "Student Home · LAKSHYA" },
    { property: "og:description", content: "Your student planner, thoughtfully organised." },
  ] }),
  component: Page,
});

const P = [72, 66, 80, 44, 68, 39];

function Page() {
  return (
    <Shell role="student">
      <PageHead eyebrow="1RV22CS018 · Semester 5" title={<>Hello, <em className="font-medium">Ananya</em></>} sub="One quiz is open and your weakest outcome is CO6." />
      <div className="grid grid-cols-12 gap-5">
        <div className="paper-wine col-span-5 p-6">
          <div className="eyebrow !text-beige/70">Open now</div>
          <div className="display mt-2 text-4xl text-ivory">Quiz 3 · Transactions</div>
          <div className="mt-2 font-mono text-xs text-beige/80">10 questions · closes Thu 23:59 · 2 attempts</div>
          <Link to="/student/quiz"><Btn variant="onWine" className="mt-6">Start attempt</Btn></Link>
        </div>
        <div className="paper relative col-span-3 rotate-[-1deg] p-6">
          <Paperclip className="absolute -top-3 right-6 size-7 text-wine" />
          <div className="eyebrow">Next deadline</div>
          <div className="display mt-2 text-5xl text-wine">2d 6h</div>
          <div className="text-sm">Lab record · DBMS</div>
        </div>
        <div className="stripes-blue col-span-4 rounded-[1.25rem] p-2">
          <div className="paper h-full p-5 !shadow-none">
            <div className="eyebrow">Weakest outcome</div>
            <div className="mt-2 flex items-center gap-3"><CO n={6} /><span className="font-serif text-2xl text-wine">Query optimisation</span></div>
            <div className="mt-3"><Bar v={39} target={60} /></div>
            <div className="mt-1 font-mono text-[11px] text-muted-foreground">39% · target 60%</div>
          </div>
        </div>

        <Card className="col-span-5" title="CO progress">
          {P.map((v, i) => <div key={i} className="mb-3 flex items-center gap-3"><CO n={i + 1} /><div className="flex-1"><Bar v={v} target={60} tone={v < 60 ? "wine" : "blue"} /></div><span className="w-10 text-right font-mono text-xs">{v}%</span></div>)}
        </Card>
        <div className="col-span-7 grid grid-cols-3 gap-4">
          {[["Quizzes", ClipboardCheck, "/student/quiz"], ["My Progress", TrendingUp, "/student/home"], ["Study Plan", NotebookPen, "/student/home"], ["Flashcards", Layers, "/student/home"], ["Ask the Course", MessageCircle, "/student/home"], ["Calendar", CalendarDays, "/student/home"]].map(([t, I, to]: any, i) => (
            <Link key={t} to={to} className={`${i % 3 === 1 ? "bg-dusty" : "bg-ivory"} stamp flex flex-col justify-between p-5 transition hover:-translate-y-0.5`} style={{ minHeight: 120 }}>
              <I className="size-6 text-wine" strokeWidth={1.4} /><span className="font-serif text-xl font-semibold text-wine">{t}</span>
            </Link>
          ))}
        </div>
        <Card className="col-span-12" title="Upcoming">
          <div className="grid grid-cols-4 gap-4">
            {[["21 OCT", "Quiz 3 closes"], ["24 OCT", "Internal Assessment 2"], ["28 OCT", "Lab record"], ["02 NOV", "Mini project review"]].map(([d, t]) => (
              <div key={t} className="flex items-center gap-3 rounded-xl border border-dashed border-wine/30 p-3"><span className="font-mono text-xs text-wine">{d}</span><span className="text-sm">{t}</span></div>
            ))}
          </div>
        </Card>
      </div>
    </Shell>
  );
}
