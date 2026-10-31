import { useQuery } from "@tanstack/react-query";
import { createFileRoute, Link } from "@tanstack/react-router";
import { format, formatDistanceToNow } from "date-fns";
import type { ElementType } from "react";
import {
  CalendarDays,
  ClipboardCheck,
  Layers,
  MessageCircle,
  NotebookPen,
  Paperclip,
  TrendingUp,
} from "lucide-react";
import { Shell } from "@/components/lk/Shell";
import { Bar, Btn, Card, CO, PageHead } from "@/components/lk/ui";
import {
  auth,
  calendarApi,
  coSheet,
  quizzes,
  subjects,
  type CalendarEvent,
  type Subject,
} from "@/lib/api";
import { getStoredSubjectId } from "@/lib/subject-context";

export const Route = createFileRoute("/student/home")({
  head: () => ({
    meta: [
      { title: "Student Home · LAKSHYA" },
      { name: "description", content: "Your quizzes, deadlines and course outcome progress." },
      { property: "og:title", content: "Student Home · LAKSHYA" },
      { property: "og:description", content: "Your student planner, thoughtfully organised." },
    ],
  }),
  component: Page,
});

const QUICK_LINKS: Array<[string, ElementType, string, boolean]> = [
  ["Quizzes", ClipboardCheck, "/student/quiz", false],
  ["My Progress", TrendingUp, "/student/home", false],
  ["Study Plan", NotebookPen, "/student/study-plan", true],
  ["Flashcards", Layers, "/student/flashcards", true],
  ["Ask the Course", MessageCircle, "/student/qa", true],
  ["Calendar", CalendarDays, "/student/calendar", true],
];

function Page() {
  const {
    data: me,
    isLoading: meLoading,
    isError: meError,
  } = useQuery({ queryKey: ["me"], queryFn: auth.getMe });

  const { data: subjectList = [] } = useQuery({
    queryKey: ["subjects"],
    queryFn: subjects.list,
    enabled: !!me,
  });

  // Use stored subject selection, falling back to the first enrolled subject.
  const storedSubjectId = getStoredSubjectId();
  const primarySubjectId =
    (storedSubjectId && subjectList.find((s) => s.id === storedSubjectId)?.id) ||
    subjectList[0]?.id;

  const { data: allQuizzes = [] } = useQuery({
    queryKey: ["quizzes", primarySubjectId],
    queryFn: () => quizzes.list(primarySubjectId ? { subject_id: primarySubjectId } : undefined),
    enabled: !!me && !!primarySubjectId,
  });


  const { data: progress } = useQuery({
    queryKey: ["progress", primarySubjectId],
    queryFn: () => coSheet.getMyProgress(primarySubjectId as string),
    enabled: !!primarySubjectId,
  });

  const { data: events = [] } = useQuery({
    queryKey: ["events"],
    queryFn: () => calendarApi.list(),
    enabled: !!me,
  });

  if (meLoading) {
    return (
      <Shell role="student">
        <div className="py-12 text-center">
          <div className="text-muted-foreground">Loading your dashboard…</div>
        </div>
      </Shell>
    );
  }

  if (meError) {
    return (
      <Shell role="student">
        <div className="py-12 text-center">
          <div className="text-wine">Unable to load dashboard. Please try again later.</div>
        </div>
      </Shell>
    );
  }

  const now = new Date();
  const subjectMap: Record<string, Subject> = {};
  for (const s of subjectList) {
    subjectMap[s.id] = s;
  }

  const openQuiz = allQuizzes.find(
    (q) =>
      q.published &&
      q.opens_at &&
      new Date(q.opens_at) <= now &&
      q.closes_at &&
      new Date(q.closes_at) >= now,
  );

  const coProgress = (progress?.co_scores ?? [])
    .filter((c) => c.percentage !== null)
    .sort((a, b) => a.co_number - b.co_number)
    .map((c) => ({ n: c.co_number, v: c.percentage as number }));

  const weakest =
    coProgress.length > 0 ? coProgress.reduce((min, c) => (c.v < min.v ? c : min)) : null;

  const target = 60;

  const upcomingEvents = events
    .filter((e) => e.starts_at && new Date(e.starts_at) >= now)
    .sort((a, b) => new Date(a.starts_at).getTime() - new Date(b.starts_at).getTime());

  const nextEvent = upcomingEvents[0];

  const semLabel = subjectList.find((s) => s.id === primarySubjectId)?.semester
    ? `Semester ${subjectList.find((s) => s.id === primarySubjectId)!.semester}`
    : "";
  const subjectObj = subjectList.find((s) => s.id === primarySubjectId);
  const subjectLabel = subjectObj ? `${subjectObj.code} · ${subjectObj.name}` : undefined;
  const usnLabel = me?.usn ?? "";
  const headerEyebrow = [usnLabel, semLabel].filter(Boolean).join(" · ") || "—";

  return (
    <Shell role="student" subjectLabel={subjectLabel}>
      <PageHead
        eyebrow={headerEyebrow}
        title={
          <>
            Hello, <em className="font-medium">{me?.name?.split(" ")[0] ?? "…"}</em>
          </>
        }
        sub={
          weakest
            ? `Weakest outcome: CO${weakest.n} at ${weakest.v}% (target ${target}%)`
            : "All course outcomes on track"
        }
      />
      <div className="grid grid-cols-12 gap-5">
        {/* ── Open quiz ── */}
        {openQuiz ? (
          <div className="paper-wine col-span-5 p-6">
            <div className="eyebrow !text-beige/70">Open now</div>
            <div className="display mt-2 text-4xl text-ivory">{openQuiz.title}</div>
            <div className="mt-2 font-mono text-xs text-beige/80">
              {openQuiz.question_count} questions · closes{" "}
              {openQuiz.closes_at ? format(new Date(openQuiz.closes_at), "EEE h:mm a") : "—"} ·{" "}
              {openQuiz.attempts_left ?? "?"} attempt
              {(openQuiz.attempts_left ?? 0) === 1 ? "" : "s"} left
            </div>
            <Link to="/student/quiz">
              <Btn variant="onWine" className="mt-6" disabled={openQuiz.attempts_left === 0}>
                {openQuiz.attempts_left === 0 ? "No attempts left" : "Start attempt"}
              </Btn>
            </Link>
          </div>
        ) : (
          <div className="paper-wine col-span-5 p-6">
            <div className="eyebrow !text-beige/70">Open now</div>
            <div className="display mt-2 text-4xl text-ivory">No open quizzes</div>
            <div className="mt-2 font-mono text-xs text-beige/80">
              Check back later for new quizzes.
            </div>
          </div>
        )}

        {/* ── Next deadline ── */}
        {nextEvent ? (
          <div className="paper relative col-span-3 rotate-[-1deg] p-6">
            <Paperclip className="absolute -top-3 right-6 size-7 text-wine" />
            <div className="eyebrow">Next deadline</div>
            <div className="display mt-2 text-5xl text-wine">
              {formatDistanceToNow(new Date(nextEvent.starts_at), { addSuffix: false })}
            </div>
            <div className="text-sm">
              {nextEvent.title} · {subjectMap[nextEvent.subject_id]?.name ?? ""}
            </div>
          </div>
        ) : (
          <div className="paper relative col-span-3 rotate-[-1deg] p-6">
            <Paperclip className="absolute -top-3 right-6 size-7 text-wine" />
            <div className="eyebrow">Next deadline</div>
            <div className="display mt-2 text-5xl text-wine">—</div>
            <div className="text-sm text-muted-foreground">No upcoming deadlines</div>
          </div>
        )}

        {/* ── Weakest outcome ── */}
        {weakest ? (
          <div className="stripes-blue col-span-4 rounded-[1.25rem] p-2">
            <div className="paper h-full p-5 !shadow-none">
              <div className="eyebrow">Weakest outcome</div>
              <div className="mt-2 flex items-center gap-3">
                <CO n={weakest.n} />
                <span className="font-serif text-2xl text-wine">CO{weakest.n}</span>
              </div>
              <div className="mt-3">
                <Bar v={weakest.v} target={target} />
              </div>
              <div className="mt-1 font-mono text-[11px] text-muted-foreground">
                {weakest.v}% · target {target}%
              </div>
            </div>
          </div>
        ) : (
          <div className="stripes-blue col-span-4 rounded-[1.25rem] p-2">
            <div className="paper h-full p-5 !shadow-none">
              <div className="eyebrow">Weakest outcome</div>
              <div className="mt-2 font-serif text-2xl text-wine">All caught up</div>
            </div>
          </div>
        )}

        {/* ── CO progress ── */}
        <Card className="col-span-5" title="CO progress">
          {coProgress.length > 0 ? (
            coProgress.map((c) => (
              <div key={c.n} className="mb-3 flex items-center gap-3">
                <CO n={c.n} />
                <div className="flex-1">
                  <Bar v={c.v} target={target} tone={c.v < target ? "wine" : "blue"} />
                </div>
                <span className="w-10 text-right font-mono text-xs">{c.v}%</span>
              </div>
            ))
          ) : (
            <div className="text-sm text-muted-foreground">No CO progress data available yet.</div>
          )}
        </Card>

        {/* ── Quick links ── */}
        <div className="col-span-7 grid grid-cols-3 gap-4">
          {QUICK_LINKS.map(([t, I, to, disabled], i) =>
            disabled ? (
              <div
                key={t}
                className={`${i % 3 === 1 ? "bg-dusty" : "bg-ivory"} stamp flex flex-col justify-between p-5 opacity-50`}
                style={{ minHeight: 120 }}
              >
                <I className="size-6 text-wine" strokeWidth={1.4} />
                <span className="font-serif text-xl font-semibold text-wine">{t}</span>
                <span className="font-mono text-[10px] text-muted-foreground">Coming soon</span>
              </div>
            ) : (
              <Link
                key={t}
                to={to}
                className={`${i % 3 === 1 ? "bg-dusty" : "bg-ivory"} stamp flex flex-col justify-between p-5 transition hover:-translate-y-0.5`}
                style={{ minHeight: 120 }}
              >
                <I className="size-6 text-wine" strokeWidth={1.4} />
                <span className="font-serif text-xl font-semibold text-wine">{t}</span>
              </Link>
            ),
          )}
        </div>

        {/* ── Upcoming ── */}
        <Card className="col-span-12" title="Upcoming">
          <div className="grid grid-cols-4 gap-4">
            {upcomingEvents.slice(0, 4).map((e: CalendarEvent) => (
              <div
                key={e.id}
                className="flex items-center gap-3 rounded-xl border border-dashed border-wine/30 p-3"
              >
                <span className="font-mono text-xs text-wine">
                  {format(new Date(e.starts_at), "dd MMM").toUpperCase()}
                </span>
                <span className="text-sm">{e.title}</span>
              </div>
            ))}
            {upcomingEvents.length === 0 && (
              <div className="col-span-4 text-sm text-muted-foreground">No upcoming events.</div>
            )}
          </div>
        </Card>
      </div>
    </Shell>
  );
}
