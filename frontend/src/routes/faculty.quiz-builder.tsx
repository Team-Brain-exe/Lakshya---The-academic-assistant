import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { GripVertical, Plus, Search, Send, X } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { Toaster } from "@/components/ui/sonner";
import { Shell } from "@/components/lk/Shell";
import { Btn, Card, Chip, CO, Field, inputCls, PageHead, type Status } from "@/components/lk/ui";
import { cn } from "@/lib/utils";
import { ApiError, questions, quizzes, subjects } from "@/lib/api";
import { getStoredSubjectId, storeSubjectId } from "@/lib/subject-context";
import type { Question, Quiz } from "@/lib/api";

export const Route = createFileRoute("/faculty/quiz-builder")({
  head: () => ({
    meta: [
      { title: "Quiz Builder · LAKSHYA" },
      { name: "description", content: "Build and publish quizzes from approved questions." },
      { property: "og:title", content: "Quiz Builder · LAKSHYA" },
      { property: "og:description", content: "A paper-planner for composing quizzes." },
    ],
  }),
  component: Page,
});

function Page() {
  const queryClient = useQueryClient();
  const [subjectId, setSubjectId] = useState<string | null>(() => getStoredSubjectId());
  const [quizTitle, setQuizTitle] = useState("Quiz 4 · Normalisation & SQL");
  const [quizModule, setQuizModule] = useState<string>("");
  const [opensAt, setOpensAt] = useState("2026-10-23T09:00");
  const [closesAt, setClosesAt] = useState("2026-10-25T23:59");
  const [sel, setSel] = useState<string[]>([]);
  const [term, setTerm] = useState("");
  const [activeCO, setActiveCO] = useState<number | null>(null);
  const [drag, setDrag] = useState<number | null>(null);
  const [savedQuiz, setSavedQuiz] = useState<Quiz | null>(null);

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

  const availableModules = detail?.modules ?? [];
  const allCOs = detail?.cos ?? [];

  const { data: questionBank } = useQuery<Question[]>({
    queryKey: ["question-bank", activeSubject],
    queryFn: async () => {
      if (!availableModules.length) return [];
      const results = await Promise.all(
        availableModules.map((m) =>
          questions.list({ module_id: m.id, status: "approved" }).catch(() => []),
        ),
      );
      return results.flat();
    },
    enabled: !!activeSubject && availableModules.length > 0,
  });

  const { data: existingQuizzes } = useQuery<Quiz[]>({
    queryKey: ["quizzes", activeSubject],
    queryFn: () => quizzes.list({ subject_id: activeSubject! }),
    enabled: !!activeSubject,
  });

  // Validates that closing time is after opening time.
  const validateTimes = (): string | null => {
    if (!opensAt || !closesAt) return null;
    const o = new Date(opensAt);
    const c = new Date(closesAt);
    if (c <= o) return "Closing time must be after opening time.";
    return null;
  };

  const createMutation = useMutation({
    mutationFn: async () => {
      const moduleId = quizModule || availableModules[0]?.id;
      if (!moduleId) throw new Error("Select a module first.");
      return quizzes.create({
        module_id: moduleId,
        title: quizTitle,
        question_ids: sel,
        opens_at: opensAt ? new Date(opensAt).toISOString() : undefined,
        closes_at: closesAt ? new Date(closesAt).toISOString() : undefined,
      });
    },
    onSuccess: (quiz) => {
      queryClient.invalidateQueries({ queryKey: ["quizzes", activeSubject] });
      setSavedQuiz(quiz);
    },
    onError: (e) => {
      if (e instanceof ApiError) toast.error(e.message);
      else toast.error("Failed to save quiz.");
    },
  });

  const publishMutation = useMutation({
    mutationFn: async () => {
      const timeErr = validateTimes();
      if (timeErr) throw new Error(timeErr);
      const quiz = await createMutation.mutateAsync();
      await quizzes.publish(quiz.id);
      return quiz;
    },
    onSuccess: (quiz) => {
      queryClient.invalidateQueries({ queryKey: ["quizzes", activeSubject] });
      toast.success(`Quiz "${quiz.title}" published`);
    },
    onError: (e) => {
      if (e instanceof ApiError) toast.error(e.message);
      else toast.error("Failed to publish quiz.");
    },
  });

  const handlePublish = () => {
    const timeErr = validateTimes();
    if (timeErr) {
      toast.error(timeErr);
      return;
    }
    if (sel.length === 0) {
      toast.error("Add at least one question to the quiz.");
      return;
    }
    publishMutation.mutate();
  };

  const handleSaveDraft = () => {
    if (sel.length === 0) {
      toast.error("Add at least one question to the quiz.");
      return;
    }
    createMutation.mutate();
  };

  const picked = sel
    .map((id) => questionBank?.find((b) => b.id === id))
    .filter((q): q is Question => q !== undefined);

  const perCO = allCOs.map((co) => picked.filter((p) => p.co_number === co.number).length);

  const filteredBank = (questionBank ?? []).filter((b) => {
    const matchesSearch = b.stem.toLowerCase().includes(term.toLowerCase());
    const matchesCO = activeCO === null || b.co_number === activeCO;
    return matchesSearch && matchesCO;
  });

  if (!subjectList?.length) {
    return (
      <Shell role="faculty">
        <PageHead eyebrow="Faculty" title="Quiz Builder" sub="No subjects assigned." />
      </Shell>
    );
  }

  return (
      <Shell role="faculty" subjectLabel={detail ? `${detail.code} · ${detail.name}` : undefined}>
      <Toaster />
      <PageHead
        eyebrow="Teaching · Planner"
        title="Compose a quiz"
        right={
          <div className="flex items-center gap-2">
            {savedQuiz && (
              <span className="font-mono text-xs text-success">
                Draft saved (ID: {savedQuiz.id.substring(0, 8)}...)
              </span>
            )}
            <Btn
              variant="secondary"
              onClick={handleSaveDraft}
              disabled={createMutation.isPending || sel.length === 0}
              size="sm"
            >
              Save as draft
            </Btn>
            <Btn
              size="lg"
              onClick={handlePublish}
              disabled={publishMutation.isPending || sel.length === 0}
            >
              <Send className="size-4" />
              {publishMutation.isPending ? "Publishing…" : "Publish quiz"}
            </Btn>
          </div>
        }
      />
      <div className="grid grid-cols-12 gap-5">
        <Card className="col-span-12">
          <div className="grid grid-cols-4 gap-4">
            <Field label="Quiz title">
              <input
                className={inputCls}
                value={quizTitle}
                onChange={(e) => setQuizTitle(e.target.value)}
              />
            </Field>
            <Field label="Module">
              <select
                className={inputCls}
                value={quizModule}
                onChange={(e) => setQuizModule(e.target.value)}
              >
                <option value="">Select a module</option>
                {availableModules.map((m) => (
                  <option key={m.id} value={m.id}>
                    M{m.number} — {m.title}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Opens">
              <input
                type="datetime-local"
                className={inputCls}
                value={opensAt}
                onChange={(e) => setOpensAt(e.target.value)}
              />
            </Field>
            <Field label="Closes">
              <input
                type="datetime-local"
                className={inputCls}
                value={closesAt}
                onChange={(e) => setClosesAt(e.target.value)}
              />
            </Field>
          </div>
        </Card>

        <Card
          className="col-span-6"
          title="Question bank"
          action={
            <span className="font-mono text-[11px] text-muted-foreground">approved only</span>
          }
        >
          <div className="relative mb-3">
            <Search className="absolute left-4 top-3.5 size-4 text-muted-foreground" />
            <input
              value={term}
              onChange={(e) => setTerm(e.target.value)}
              placeholder="Search questions"
              className={`${inputCls} pl-10`}
            />
          </div>
          <div className="mb-3 flex flex-wrap gap-1.5">
            {allCOs.map((co) => (
              <button
                key={co.number}
                type="button"
                onClick={() => setActiveCO(activeCO === co.number ? null : co.number)}
                className={cn(
                  "cursor-pointer rounded-full p-0.5",
                  activeCO === co.number && "ring-2 ring-wine",
                )}
              >
                <CO n={co.number} />
              </button>
            ))}
          </div>
          {filteredBank.length === 0 ? (
            <p className="py-8 text-center text-sm text-muted-foreground">
              No questions match your filters.
            </p>
          ) : (
            filteredBank.map((b) => (
              <div
                key={b.id}
                className="flex items-center gap-3 border-b border-dashed border-wine/20 py-3 last:border-0"
              >
                <CO n={b.co_number} />
                <span className="flex-1 text-sm">{b.stem}</span>
                <Btn
                  size="sm"
                  variant={sel.includes(b.id) ? "ghost" : "secondary"}
                  disabled={sel.includes(b.id)}
                  onClick={() =>
                    sel.includes(b.id)
                      ? setSel(sel.filter((x) => x !== b.id))
                      : setSel([...sel, b.id])
                  }
                >
                  <Plus className="size-3.5" />
                  {sel.includes(b.id) ? "Added" : "Add"}
                </Btn>
              </div>
            ))
          )}
        </Card>

        <div className="col-span-6 space-y-5">
          <div className="paper-wine p-5">
            <div className="flex items-end justify-between">
              <div>
                <div className="eyebrow !text-beige/70">Total questions</div>
                <div className="display text-5xl text-ivory">{picked.length}</div>
              </div>
              <div className="flex gap-3">
                {perCO.map((c, i) => (
                  <div key={i} className="text-center">
                    <div className="font-mono text-lg">{c}</div>
                    <div className="font-mono text-[10px] text-beige/70">CO{i + 1}</div>
                  </div>
                ))}
              </div>
            </div>
          </div>
          <Card title={`Selected · ${picked.length}`}>
            {picked.length === 0 && (
              <p className="py-8 text-center font-serif text-lg text-muted-foreground">
                Nothing pinned yet — add from the bank.
              </p>
            )}
            {picked.map((p, i) => (
              <div
                key={p.id}
                draggable
                onDragStart={() => setDrag(i)}
                onDragOver={(e) => {
                  e.preventDefault();
                  if (drag !== null && drag !== i) {
                    const n = [...sel];
                    const [x] = n.splice(drag, 1);
                    n.splice(i, 0, x!);
                    setSel(n);
                    setDrag(i);
                  }
                }}
                onDragEnd={() => setDrag(null)}
                className={cn(
                  "mb-2 flex cursor-grab items-center gap-3 rounded-xl border border-wine/15 bg-beige/40 px-3 py-2.5",
                  drag === i && "opacity-50",
                )}
              >
                <GripVertical className="size-4 text-wine/50" />
                <span className="font-mono text-xs text-wine">{i + 1}.</span>
                <span className="flex-1 text-sm">{p.stem}</span>
                <CO n={p.co_number} />
                <button onClick={() => setSel(sel.filter((x) => x !== p.id))} aria-label="Remove">
                  <X className="size-4 text-wine" />
                </button>
              </div>
            ))}
          </Card>
        </div>

        <Card className="col-span-12" title="Existing quizzes">
          {!existingQuizzes?.length ? (
            <p className="py-6 text-center text-sm text-muted-foreground">
              No quizzes created yet.
            </p>
          ) : (
            <div className="grid grid-cols-4 gap-4">
              {existingQuizzes.map((q) => (
                <div key={q.id} className="rounded-xl border border-wine/15 p-4">
                  <Chip s={q.published ? "Published" : "Draft"} />
                  <div className="mt-2 font-serif text-lg text-wine">{q.title}</div>
                  <div className="mt-1 font-mono text-[11px] text-muted-foreground">
                    opens{" "}
                    {q.opens_at
                      ? new Date(q.opens_at).toLocaleDateString("en-US", {
                          month: "short",
                          day: "numeric",
                        })
                      : "—"}
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>
    </Shell>
  );
}
