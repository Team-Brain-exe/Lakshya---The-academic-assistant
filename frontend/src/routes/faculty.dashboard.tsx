import { useQuery } from "@tanstack/react-query";
import { createFileRoute, Link } from "@tanstack/react-router";
import { format, formatDistanceToNow } from "date-fns";
import { AlertTriangle, ClipboardCheck, FileUp, PenLine, Star } from "lucide-react";
import { useState } from "react";
import { Shell } from "@/components/lk/Shell";
import { Bar, Card, CO, PageHead } from "@/components/lk/ui";
import { coSheet, questions, quizzes, subjects, calendarApi } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { getStoredSubjectId, storeSubjectId } from "@/lib/subject-context";

export const Route = createFileRoute("/faculty/dashboard")({
  head: () => ({
    meta: [
      { title: "Faculty Dashboard · LAKSHYA" },
      { name: "description", content: "Course outcomes, questions and quizzes at a glance." },
      { property: "og:title", content: "Faculty Dashboard · LAKSHYA" },
      { property: "og:description", content: "Your academic journal for teaching." },
    ],
  }),
  component: Page,
});

function Page() {
  const { user: currentUser } = useAuth();
  const [subjectId, setSubjectId] = useState<string | null>(() => getStoredSubjectId());

  const { data: subjectList } = useQuery({
    queryKey: ["subjects"],
    queryFn: () => subjects.list(),
  });

  const activeSubject = subjectId ?? subjectList?.[0]?.id ?? null;

  const { data: detail } = useQuery({
    queryKey: ["subject-detail", activeSubject],
    queryFn: () => subjects.get(activeSubject!),
    enabled: !!activeSubject,
  });

  const { data: coSummary } = useQuery({
    queryKey: ["co-summary", activeSubject],
    queryFn: () => coSheet.getSummary(activeSubject!),
    enabled: !!activeSubject,
  });

  const { data: weakCOs } = useQuery({
    queryKey: ["weak-co", activeSubject],
    queryFn: () => coSheet.getWeakCOs(activeSubject!),
    enabled: !!activeSubject,
  });

  const { data: calendarEvents } = useQuery({
    queryKey: ["calendar", activeSubject],
    queryFn: () => calendarApi.list(activeSubject ? { subject_id: activeSubject } : undefined),
    enabled: !!activeSubject,
  });

  const { data: subjectQuizzes } = useQuery({
    queryKey: ["quizzes", activeSubject],
    queryFn: () => quizzes.list({ subject_id: activeSubject! }),
    enabled: !!activeSubject,
  });

  const { data: draftQuestions } = useQuery({
    queryKey: ["draft-questions", activeSubject],
    queryFn: async () => {
      if (!detail?.modules?.length) return [];
      const results = await Promise.all(
        detail.modules.map((m) =>
          questions.list({ module_id: m.id, status: "draft" }).catch(() => []),
        ),
      );
      return results.flat();
    },
    enabled: !!detail?.modules?.length,
  });

  // ── Derived values ──────────────────────────────────────────────────
  const targetPct = detail?.target_attainment_pct ?? 60;
  const coAttainment = (coSummary ?? []).map((s) => s.attainment_pct ?? 0);

  const weakOutcomes = (weakCOs ?? []).slice(0, 2).map((w) => {
    const co = detail?.cos?.find((c) => c.number === w.co_number);
    return {
      co: w.co_number,
      pct: w.attainment_pct ?? 0,
      desc: co?.description ?? `CO${w.co_number}`,
    };
  });

  const upcoming = (calendarEvents ?? [])
    .filter((e) => new Date(e.starts_at) > new Date())
    .sort((a, b) => new Date(a.starts_at).getTime() - new Date(b.starts_at).getTime())
    .slice(0, 3);

  const publishedQuizzes = (subjectQuizzes ?? []).filter((q) => q.published);
  const draftQuizzes = (subjectQuizzes ?? []).filter((q) => !q.published);

  const modulesDone = detail?.modules?.filter((m) => m.processing_status === "done").length ?? 0;
  const modulesTotal = detail?.modules?.length ?? 0;
  const avgAttainment = coSummary?.length
    ? Math.round(
        (coSummary ?? []).reduce((s, item) => s + (item.attainment_pct ?? 0), 0) / coSummary.length,
      )
    : 0;

  // ── Recent activity (derived from quizzes + modules) ────────────────
  const activity: Array<{ time: string; text: string }> = [
    ...publishedQuizzes.slice(0, 2).map((q) => ({
      time: q.published_at
        ? formatDistanceToNow(new Date(q.published_at), { addSuffix: true })
        : "recently",
      text: `"${q.title}" published · ${q.question_count} questions`,
    })),
    ...(detail?.modules
      ?.filter((m) => m.processing_status === "done")
      .slice(0, 2)
      .map((m) => ({
        time: m.processed_at
          ? formatDistanceToNow(new Date(m.processed_at), { addSuffix: true })
          : "recently",
        text: `Module ${m.number} processed · ${m.title}`,
      })) ?? []),
  ];

  if (!subjectList?.length) {
    return (
      <Shell role="faculty">
        <PageHead eyebrow="Faculty" title="Dashboard" sub="No subjects assigned to your account." />
      </Shell>
    );
  }

  return (
    <Shell role="faculty" subjectLabel={detail ? `${detail.code} · ${detail.name}` : undefined}>
      <PageHead
        eyebrow="Faculty Dashboard"
        title={
          <>
            Good morning, <em className="font-medium">{currentUser?.name || "Faculty"}</em>
          </>
        }
        sub={detail ? `${detail.code} · ${detail.name}` : "Select a subject to view details."}
        right={
          subjectList.length > 1 ? (
            <select
              value={activeSubject ?? ""}
              onChange={(e) => {
                const val = e.target.value || null;
                setSubjectId(val);
                if (val) storeSubjectId(val);
              }}
              className="h-10 rounded-full border border-wine/30 bg-ivory px-4 text-sm text-wine"
            >
              {subjectList.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.code} — {s.name}
                </option>
              ))}
            </select>
          ) : undefined
        }
      />
      <div className="grid grid-cols-12 gap-5">
        {/* Stats cards */}
        <div className="paper col-span-3 p-5">
          <div className="eyebrow">Modules uploaded</div>
          <div className="display mt-2 text-5xl text-wine">
            {modulesDone}/{modulesTotal}
          </div>
          <div className="mt-1 font-mono text-[11px] text-muted-foreground">
            {modulesTotal - modulesDone} pending
          </div>
        </div>
        <div className="paper-wine col-span-3 p-5">
          <div className="eyebrow !text-beige/70">Awaiting review</div>
          <div className="display mt-2 text-5xl text-ivory">{draftQuestions?.length ?? 0}</div>
          <div className="mt-1 font-mono text-[11px] text-beige/80">
            draft questions across modules
          </div>
        </div>
        <div className="paper col-span-3 p-5">
          <div className="eyebrow">Published quizzes</div>
          <div className="display mt-2 text-5xl text-wine">{publishedQuizzes.length}</div>
          <div className="mt-1 font-mono text-[11px] text-muted-foreground">
            {draftQuizzes.length} drafts
          </div>
        </div>
        <div className="paper col-span-3 p-5">
          <div className="eyebrow">Class CO attainment</div>
          <div className="display mt-2 text-5xl text-wine">{avgAttainment}%</div>
          <div className="mt-1 font-mono text-[11px] text-muted-foreground">
            Target {targetPct}%
          </div>
        </div>

        {/* CO attainment chart */}
        <Card
          className="col-span-8"
          title="Course outcome attainment"
          action={
            <span className="font-mono text-[11px] text-muted-foreground">
              — target {targetPct}%
            </span>
          }
        >
          {coAttainment.length === 0 ? (
            <p className="py-8 text-center text-sm text-muted-foreground">
              No CO data yet. Publish a quiz to start.
            </p>
          ) : (
            <>
              <div className="relative flex h-56 items-end gap-6 border-b border-wine/20 px-2">
                <div
                  className="absolute inset-x-0 border-t border-dashed border-oxblood"
                  style={{ bottom: `${targetPct}%` }}
                />
                {coAttainment.map((v, i) => (
                  <div key={i} className="flex flex-1 flex-col items-center gap-2">
                    <span className="font-mono text-xs">{v}%</span>
                    <div
                      className={`w-full rounded-t-xl ${
                        v < targetPct ? "bg-wine" : "stripes-blue border border-dusty"
                      }`}
                      style={{ height: `${Math.max(v * 1.8, 2)}px` }}
                    />
                  </div>
                ))}
              </div>
              <div className="mt-3 flex gap-6 px-2">
                {coAttainment.map((_, i) => (
                  <div key={i} className="flex flex-1 justify-center">
                    <CO n={i + 1} />
                  </div>
                ))}
              </div>
            </>
          )}
        </Card>

        {/* Weak outcomes + quick actions */}
        <div className="col-span-4 space-y-5">
          <div className="paper-wine p-6">
            <div className="flex items-center gap-2">
              <AlertTriangle className="size-4" />
              <span className="eyebrow !text-beige/80">Weak outcomes</span>
            </div>
            {weakOutcomes.length ? (
              weakOutcomes.map((w) => (
                <div key={w.co} className="mt-4 rounded-xl bg-oxblood/60 p-3">
                  <div className="flex items-center justify-between">
                    <CO n={w.co} className="!bg-ivory !text-wine" />
                    <span className="font-mono text-sm">{w.pct}%</span>
                  </div>
                  <div className="mt-1 font-serif text-lg">{w.desc}</div>
                </div>
              ))
            ) : (
              <p className="mt-4 text-sm text-beige/80">All course outcomes meet target. 🎉</p>
            )}
          </div>
          <div className="grid gap-2">
            {[
              { label: "Upload slides", to: "/faculty/upload", Icon: FileUp },
              {
                label: "Review questions",
                to: "/faculty/review",
                Icon: ClipboardCheck,
              },
              { label: "Create quiz", to: "/faculty/quiz-builder", Icon: PenLine },
            ].map(({ label, to, Icon }) => (
              <Link
                key={label}
                to={to}
                className="paper flex items-center gap-3 !rounded-full px-5 py-3 font-medium text-wine hover:bg-beige"
              >
                <Icon className="size-4" />
                {label}
                <Star className="ml-auto size-3 fill-wine text-wine" />
              </Link>
            ))}
          </div>
        </div>

        {/* Upcoming events */}
        <Card className="col-span-4" title="Upcoming events">
          {upcoming.length ? (
            upcoming.map((e) => (
              <div
                key={e.id}
                className="flex items-center gap-4 border-b border-dashed border-wine/20 py-3 last:border-0"
              >
                <div className="stamp bg-beige px-3 py-2 text-center font-mono text-xs text-wine">
                  {format(new Date(e.starts_at), "d MMM")}
                </div>
                <div>
                  <div className="font-medium">{e.title}</div>
                  <div className="text-xs text-muted-foreground">{e.type}</div>
                </div>
              </div>
            ))
          ) : (
            <p className="py-6 text-center text-sm text-muted-foreground">No upcoming events.</p>
          )}
        </Card>

        {/* Quiz deadlines */}
        <Card className="col-span-4" title="Quiz deadlines">
          {!subjectQuizzes?.length ? (
            <p className="py-6 text-center text-sm text-muted-foreground">No quizzes yet.</p>
          ) : (
            subjectQuizzes.slice(0, 4).map((q) => {
              const maxQ = Math.max(...subjectQuizzes.map((x) => x.question_count), 1);
              return (
                <div key={q.id} className="mb-4">
                  <div className="mb-1.5 flex justify-between text-sm">
                    <span>{q.title}</span>
                    <span className="font-mono text-xs">
                      {q.question_count}Q · {q.published ? "Published" : "Draft"}
                    </span>
                  </div>
                  <Bar v={(q.question_count / maxQ) * 100} tone={q.published ? "blue" : "wine"} />
                </div>
              );
            })
          )}
        </Card>

        {/* Recent activity */}
        <Card className="col-span-4" title="Recent activity">
          <ul className="space-y-3 text-sm">
            {activity.length ? (
              activity.map((a, i) => (
                <li key={i} className="flex gap-3">
                  <span className="font-mono text-[10px] text-muted-foreground">{a.time}</span>
                  {a.text}
                </li>
              ))
            ) : (
              <p className="py-6 text-center text-sm text-muted-foreground">No recent activity.</p>
            )}
          </ul>
        </Card>
      </div>
    </Shell>
  );
}
