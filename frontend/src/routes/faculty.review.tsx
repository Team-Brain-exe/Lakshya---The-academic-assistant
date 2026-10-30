import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { Check, Pencil, Sparkle, X } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { Toaster } from "@/components/ui/sonner";
import { Shell } from "@/components/lk/Shell";
import { Btn, Card, Chip, CO, Field, inputCls, PageHead, type Status } from "@/components/lk/ui";
import { cn } from "@/lib/utils";
import { ApiError, questions, subjects } from "@/lib/api";
import { getStoredSubjectId, storeSubjectId } from "@/lib/subject-context";
import type { Question, SubjectDetail } from "@/lib/api";

export const Route = createFileRoute("/faculty/review")({
  head: () => ({
    meta: [
      { title: "Question Review · LAKSHYA" },
      { name: "description", content: "Moderate AI-generated and faculty questions." },
      { property: "og:title", content: "Question Review · LAKSHYA" },
      {
        property: "og:description",
        content: "Approve, edit or reject questions before they reach students.",
      },
    ],
  }),
  component: Page,
});

function Page() {
  const queryClient = useQueryClient();
  const [subjectId, setSubjectId] = useState<string | null>(() => getStoredSubjectId());
  const [filter, setFilter] = useState<Status | "All">("All");
  const [sourceFilter, setSourceFilter] = useState<"All" | "AI" | "Faculty">("All");
  const [coFilter, setCoFilter] = useState<number | null>(null);
  const [genModule, setGenModule] = useState<string>("");
  const [genCO, setGenCO] = useState<number | null>(null);
  const [genCount, setGenCount] = useState("10");

  const { data: subjectList } = useQuery({
    queryKey: ["subjects"],
    queryFn: () => subjects.list(),
  });

  const activeSubject = subjectId ?? subjectList?.[0]?.id ?? null;

  const { data: detail } = useQuery<SubjectDetail>({
    queryKey: ["subject-detail", activeSubject],
    queryFn: () => subjects.get(activeSubject!),
    enabled: !!activeSubject,
  });

  const availableModules = detail?.modules ?? [];
  const allCOs = detail?.cos ?? [];

  const { data: allQuestions } = useQuery<Question[]>({
    queryKey: ["review-questions", activeSubject],
    queryFn: async () => {
      if (!availableModules.length) return [];
      const results = await Promise.all(
        availableModules.map((m) => questions.list({ module_id: m.id }).catch(() => [])),
      );
      return results.flat();
    },
    enabled: !!activeSubject && availableModules.length > 0,
  });

  const approveMutation = useMutation({
    mutationFn: (id: string) => questions.approve(id),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["review-questions", activeSubject],
      });
      toast.success("Question approved");
    },
    onError: (e) => {
      if (e instanceof ApiError) toast.error(e.message);
      else toast.error("Approval failed.");
    },
  });

  const rejectMutation = useMutation({
    mutationFn: (id: string) => questions.reject(id),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["review-questions", activeSubject],
      });
      toast.success("Question rejected");
    },
    onError: (e) => {
      if (e instanceof ApiError) toast.error(e.message);
      else toast.error("Rejection failed.");
    },
  });

  const set = (id: string, s: Status) => {
    if (s === "Approved") approveMutation.mutate(id);
    else if (s === "Rejected") rejectMutation.mutate(id);
  };

  const visible = (allQuestions ?? []).filter((q) => {
    const matchesStatus = filter === "All" || q.status === filter;
    const matchesSource =
      sourceFilter === "All" ||
      (sourceFilter === "AI" && q.source === "AI") ||
      (sourceFilter === "Faculty" && q.source === "Faculty");
    const matchesCO = coFilter === null || q.co_number === coFilter;
    return matchesStatus && matchesSource && matchesCO;
  });

  const count = (s: Status) => (allQuestions ?? []).filter((q) => q.status === s).length;

  if (!subjectList?.length) {
    return (
      <Shell role="faculty" subjectLabel={detail ? `${detail.code} · ${detail.name}` : undefined}>
        <PageHead eyebrow="Faculty" title="Question Review" sub="No subjects assigned." />
      </Shell>
    );
  }

  return (
    <Shell role="faculty" subjectLabel={detail ? `${detail.code} · ${detail.name}` : undefined}>
      <Toaster />
      <PageHead
        eyebrow="Teaching · Moderation"
        title="Question review"
        right={
          <Btn
            onClick={() => {
              const draftIds = visible.filter((q) => q.status === "Draft").map((q) => q.id);
              draftIds.forEach((id) => approveMutation.mutate(id));
              toast(`Approved ${draftIds.length} questions`);
            }}
          >
            <Check className="size-4" />
            Approve all visible
          </Btn>
        }
      />
      <div className="grid grid-cols-12 gap-5">
        <div className="col-span-8 space-y-4">
          {/* Filters */}
          <div className="flex flex-wrap items-center gap-2">
            {(["All", "Draft", "Approved", "Rejected"] as const).map((s) => (
              <button
                key={s}
                onClick={() => setFilter(s)}
                className={cn(
                  "rounded-full border px-4 py-1.5 text-sm",
                  filter === s ? "border-wine bg-wine text-ivory" : "border-wine/30 text-wine",
                )}
              >
                {s}{" "}
                {s !== "All" && (
                  <span className="ml-1 font-mono text-[11px] opacity-70">
                    {count(s as Status)}
                  </span>
                )}
              </button>
            ))}
            <div className="flex-1" />
            <select
              value={sourceFilter}
              onChange={(e) => setSourceFilter(e.target.value as "All" | "AI" | "Faculty")}
              className="h-9 rounded-full border border-wine/30 bg-ivory px-3 text-xs text-wine"
            >
              <option value="All">Source: All</option>
              <option value="AI">AI</option>
              <option value="Faculty">Faculty</option>
            </select>
            <select
              value={coFilter ?? ""}
              onChange={(e) => setCoFilter(e.target.value ? Number(e.target.value) : null)}
              className="h-9 rounded-full border border-wine/30 bg-ivory px-3 text-xs text-wine"
            >
              <option value="">CO: All</option>
              {allCOs.map((co) => (
                <option key={co.id} value={co.number}>
                  CO{co.number}
                </option>
              ))}
            </select>
            <select
              className="h-9 rounded-full border border-wine/30 bg-ivory px-3 text-xs text-wine"
              defaultValue=""
            >
              <option value="">Difficulty: All</option>
            </select>
          </div>

          {/* Question list */}
          {visible.length === 0 ? (
            <p className="py-8 text-center text-sm text-muted-foreground">
              No questions match your filters.
            </p>
          ) : (
            visible.map((q) => {
              const mod = availableModules.find((m) => m.id === q.module_id);
              return (
                <article key={q.id} className="paper p-5">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-mono text-[11px] text-muted-foreground">
                      Q{q.id.substring(0, 8)} · M{mod?.number ?? "?"}
                    </span>
                    <CO n={q.co_number} />
                    <span
                      className={cn(
                        "rounded-full px-2 py-0.5 text-[11px]",
                        q.source === "AI" ? "bg-dusty text-oxblood" : "bg-beige text-wine",
                      )}
                    >
                      {q.source === "AI" ? "✦ AI" : "Faculty"}
                    </span>
                    {q.difficulty && (
                      <span className="text-[11px] text-muted-foreground">{q.difficulty}</span>
                    )}
                    <div className="flex-1" />
                    <Chip s={q.status as Status} />
                  </div>
                  <p className="mt-3 font-serif text-xl font-semibold text-espresso">{q.stem}</p>
                  <div className="mt-3 grid grid-cols-2 gap-2">
                    {q.options.map((o, i) => (
                      <div
                        key={i}
                        className={cn(
                          "flex items-center gap-2 rounded-xl border px-3 py-2 text-sm",
                          i === q.correct_option
                            ? "border-success bg-success/10"
                            : "border-wine/15",
                        )}
                      >
                        <span className="font-mono text-xs text-muted-foreground">{"ABCD"[i]}</span>
                        {o}
                        {i === q.correct_option && (
                          <Check className="ml-auto size-4 text-success" />
                        )}
                      </div>
                    ))}
                  </div>
                  {q.explanation && (
                    <p className="mt-3 border-l-2 border-dusty pl-3 text-sm text-muted-foreground">
                      <b className="text-espresso">Why:</b> {q.explanation}
                    </p>
                  )}
                  <div className="mt-4 flex justify-end gap-2">
                    <Btn variant="ghost" size="sm">
                      <Pencil className="size-3.5" />
                      Edit
                    </Btn>
                    <Btn
                      variant="secondary"
                      size="sm"
                      onClick={() => set(q.id, "Rejected")}
                      disabled={q.status === "Rejected"}
                    >
                      <X className="size-3.5" />
                      Reject
                    </Btn>
                    <Btn
                      size="sm"
                      onClick={() => set(q.id, "Approved")}
                      disabled={q.status === "Approved"}
                    >
                      <Check className="size-3.5" />
                      Approve
                    </Btn>
                  </div>
                </article>
              );
            })
          )}
        </div>

        {/* Sidebar */}
        <div className="col-span-4">
          <div className="sticky top-24 space-y-5">
            <div className="grid grid-cols-3 gap-3">
              {(["Draft", "Approved", "Rejected"] as const).map((s) => (
                <div key={s} className="paper p-4 text-center">
                  <div className="display text-4xl text-wine">{count(s)}</div>
                  <div className="eyebrow">{s}</div>
                </div>
              ))}
            </div>

            <div className="stripes-blue rounded-[1.25rem] p-2">
              <Card className="!shadow-none" title="Generate questions">
                <div className="space-y-3">
                  <Field label="Module">
                    <select
                      className={inputCls}
                      value={genModule}
                      onChange={(e) => setGenModule(e.target.value)}
                    >
                      <option value="">Select module</option>
                      {availableModules.map((m) => (
                        <option key={m.id} value={m.id}>
                          M{m.number} — {m.title}
                        </option>
                      ))}
                    </select>
                  </Field>
                  <Field label="Course outcome">
                    <select
                      className={inputCls}
                      value={genCO ?? ""}
                      onChange={(e) => setGenCO(e.target.value ? Number(e.target.value) : null)}
                    >
                      <option value="">Select CO</option>
                      {allCOs.map((co) => (
                        <option key={co.id} value={co.number}>
                          CO{co.number} — {co.description}
                        </option>
                      ))}
                    </select>
                  </Field>
                  <Field label="Count">
                    <input
                      type="number"
                      defaultValue={10}
                      value={genCount}
                      onChange={(e) => setGenCount(e.target.value)}
                      className={inputCls}
                    />
                  </Field>
                  <Btn
                    className="w-full"
                    onClick={() =>
                      toast(
                        `AI generation coming soon — selected ${genCount} questions for ${genModule ? "module" : "subject"}`,
                      )
                    }
                  >
                    <Sparkle className="size-4" />
                    Generate
                  </Btn>
                </div>
              </Card>
            </div>
          </div>
        </div>
      </div>
    </Shell>
  );
}
