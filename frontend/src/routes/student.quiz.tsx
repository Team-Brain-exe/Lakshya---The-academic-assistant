import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { formatDistanceToNow } from "date-fns";
import { Check, Clock, RotateCcw } from "lucide-react";
import { useEffect, useState } from "react";
import { Shell } from "@/components/lk/Shell";
import { Bar, Btn, Card, CO, PageHead } from "@/components/lk/ui";
import {
  attempts,
  quizzes,
  subjects,
  ApiError,
  type AttemptStart,
  type SubmitResult,
  type ReviewItem,
  type AttemptState,
} from "@/lib/api";
import { getStoredSubjectId } from "@/lib/subject-context";
import { cn } from "@/lib/utils";

/** sessionStorage key for the active attempt so a refresh resumes it. */
const ATTEMPT_STORAGE_KEY = "lakshya_active_attempt";

export const Route = createFileRoute("/student/quiz")({
  head: () => ({
    meta: [
      { title: "Quiz Attempt · LAKSHYA" },
      { name: "description", content: "Attempt your quiz and view your course outcome results." },
      { property: "og:title", content: "Quiz Attempt · LAKSHYA" },
      {
        property: "og:description",
        content: "Take your quiz and check your course outcome results.",
      },
    ],
  }),
  component: Page,
});

function Page() {
  const queryClient = useQueryClient();
  const [attempt, setAttempt] = useState<AttemptStart | null>(null);
  const [answers, setAnswers] = useState<Record<string, number>>({});
  const [saved, setSaved] = useState(false);
  const [confirm, setConfirm] = useState(false);
  const [done, setDone] = useState(false);
  const [result, setResult] = useState<SubmitResult | null>(null);
  const [reviewItems, setReviewItems] = useState<ReviewItem[] | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [currentQuestion, setCurrentQuestion] = useState(0);

  // Load subjects and determine the primary subject.
  const { data: subjectList = [] } = useQuery({
    queryKey: ["subjects"],
    queryFn: subjects.list,
  });

  const storedSubjectId = getStoredSubjectId();
  const primarySubjectId =
    (storedSubjectId && subjectList.find((s) => s.id === storedSubjectId)?.id) ||
    subjectList[0]?.id;

  const subjectObj = subjectList.find((s) => s.id === primarySubjectId);
  const subjectLabel = subjectObj ? `${subjectObj.code} · ${subjectObj.name}` : undefined;

  // Load quizzes for the selected subject only.
  const { data: allQuizzes = [] } = useQuery({
    queryKey: ["quizzes", primarySubjectId],
    queryFn: () =>
      quizzes.list(primarySubjectId ? { subject_id: primarySubjectId } : undefined),
    enabled: !!primarySubjectId,
  });

  const now = new Date();
  const openQuiz = allQuizzes?.find(
    (q) =>
      q.published &&
      q.opens_at &&
      new Date(q.opens_at) <= now &&
      q.closes_at &&
      new Date(q.closes_at) >= now &&
      (q.attempts_left ?? 0) > 0,
  );

  // ── Attempt lifecycle: start, resume, persist ─────────────────────
  useEffect(() => {
    // On mount, try to resume a saved attempt from sessionStorage.
    if (typeof sessionStorage !== "undefined") {
      const savedId = sessionStorage.getItem(ATTEMPT_STORAGE_KEY);
      if (savedId) {
        setStarting(true);
        attempts
          .getState(savedId)
          .then((state) => {
            if (state.status === "in_progress") {
              setAttempt(state);
              setAnswers(state.answers ?? {});
            } else {
              sessionStorage.removeItem(ATTEMPT_STORAGE_KEY);
            }
          })
          .catch(() => {
            // Token may have expired — the apiRequest redirect handles it.
            sessionStorage.removeItem(ATTEMPT_STORAGE_KEY);
          })
          .finally(() => setStarting(false));
      }
    }
  }, []);

  // Auto-start an attempt for the currently open quiz.
  useEffect(() => {
    if (openQuiz && !attempt && !starting) {
      setStarting(true);
      attempts
        .start(openQuiz.id)
        .then((started) => {
          const state: AttemptState = {
            ...started,
            quiz_id: openQuiz.id,
            status: "in_progress",
            answers: {},
            closes_at: openQuiz.closes_at ?? null,
          };
          setAttempt(state);
          if (typeof sessionStorage !== "undefined") {
            sessionStorage.setItem(ATTEMPT_STORAGE_KEY, state.attempt_id);
          }
        })
        .catch((e: unknown) => {
          if (e instanceof ApiError) setError(e.message);
          else setError("Failed to start quiz.");
        })
        .finally(() => setStarting(false));
    }
  }, [openQuiz, attempt, starting]);

  // Persist answers to sessionStorage whenever they change.
  useEffect(() => {
    if (attempt && typeof sessionStorage !== "undefined") {
      sessionStorage.setItem(
        `lakshya_answers_${attempt.attempt_id}`,
        JSON.stringify(answers),
      );
    }
  }, [answers, attempt]);

  // Auto-save answers to the backend with a visible state.
  const saveAnswers = (newAnswers: Record<string, number>) => {
    if (!attempt) return;
    setAnswers(newAnswers);
    setSaved(true);
    setTimeout(() => setSaved(false), 1200);
    void attempts.saveAnswers(attempt.attempt_id, newAnswers).catch(() => {});
  };

  const handleSubmit = () => {
    if (submitting || !attempt || !openQuiz) return;
    setSubmitting(true);
    setConfirm(false);
    attempts
      .submit(attempt.attempt_id, answers)
      .then(setResult)
      .then(() => {
        setDone(true);
        if (typeof sessionStorage !== "undefined") {
          sessionStorage.removeItem(ATTEMPT_STORAGE_KEY);
          sessionStorage.removeItem(`lakshya_answers_${attempt.attempt_id}`);
        }
      })
      .catch((e: unknown) => {
        if (e instanceof ApiError) setError(e.message);
        else setError("Failed to submit quiz.");
      })
      .finally(() => setSubmitting(false));
  };

  const pick = (k: number) => {
    if (!attempt) return;
    const qid = attempt.questions[currentQuestion]!.id;
    saveAnswers({ ...answers, [qid]: k });
  };

  const handleReview = () => {
    if (!attempt) return;
    void attempts
      .review(attempt.attempt_id)
      .then(setReviewItems)
      .catch((e: unknown) => {
        if (e instanceof ApiError) setError(e.message);
      });
  };

  const retry = () => {
    setDone(false);
    setResult(null);
    setReviewItems(null);
    setAnswers({});
    setCurrentQuestion(0);
    setAttempt(null);
    if (typeof sessionStorage !== "undefined") {
      sessionStorage.removeItem(ATTEMPT_STORAGE_KEY);
    }
  };

  if (error) {
    return (
      <Shell role="student" subjectLabel={subjectLabel}>
        <div className="py-12 text-center">
          <div className="text-wine">{error}</div>
        </div>
      </Shell>
    );
  }

  if (!subjectList.length) {
    return (
      <Shell role="student">
        <div className="py-12 text-center">
          <div className="text-muted-foreground">You are not enrolled in any subjects.</div>
        </div>
      </Shell>
    );
  }

  if (starting || !attempt) {
    return (
      <Shell role="student" subjectLabel={subjectLabel}>
        <div className="py-12 text-center">
          <div className="text-muted-foreground">
            {starting
              ? "Starting your attempt…"
              : openQuiz
                ? "Starting your attempt…"
                : "No quizzes are currently open."}
          </div>
        </div>
      </Shell>
    );
  }

  const questions = attempt.questions;
  const totalAttempts = attempt.attempt_number + attempt.attempts_left;
  const unanswered = questions
    .map((q, k) => (answers[q.id] === undefined ? k + 1 : null))
    .filter((x): x is number => x !== null);

  if (done && result && !reviewItems) {
    return (
      <Shell role="student" subjectLabel={subjectLabel}>
        <PageHead
          eyebrow={`Quiz · Attempt ${attempt.attempt_number} of ${totalAttempts}`}
          title="Your result"
        />
        <div className="grid grid-cols-12 gap-5">
          <div className="paper-wine col-span-5 p-8">
            <div className="eyebrow !text-beige/70">Total score</div>
            <div className="display mt-2 text-8xl text-ivory">
              {result.total_score}
              <span className="text-4xl text-beige">/{result.max_score}</span>
            </div>
            <div className="font-mono text-beige">
              {Math.round((result.total_score / result.max_score) * 100)}% ·{" "}
              {attempt.attempts_left}{" "}
              attempt{attempt.attempts_left === 1 ? "" : "s"} remaining
            </div>
            <div className="mt-6 flex gap-3">
              <Btn variant="onWine" onClick={handleReview}>
                Review answers
              </Btn>
              {(openQuiz?.attempts_left ?? 0) > 0 && (
                <Btn
                  variant="ghost"
                  className="text-ivory hover:bg-ivory/10"
                  onClick={retry}
                >
                  <RotateCcw className="size-4" /> Retry
                </Btn>
              )}
            </div>
          </div>
          <Card className="col-span-7" title="By course outcome">
            {result.co_scores
              .filter((c) => c.percentage !== null)
              .map((c) => (
                <div key={c.co_number} className="mb-4 flex items-center gap-3">
                  <CO n={c.co_number} />
                  <div className="flex-1">
                    <Bar
                      v={c.percentage as number}
                      target={60}
                      tone={(c.percentage as number) < 60 ? "wine" : "blue"}
                    />
                  </div>
                  <span className="font-mono text-sm">{Math.round(c.percentage as number)}%</span>
                </div>
              ))}
          </Card>
        </div>
      </Shell>
    );
  }

  // Review view
  if (done && reviewItems) {
    return (
      <Shell role="student" subjectLabel={subjectLabel}>
        <PageHead
          eyebrow={`Quiz · Attempt ${attempt.attempt_number} of ${totalAttempts}`}
          title="Answer review"
        />
        <Card className="col-span-12">
          <div className="space-y-6">
            {reviewItems.map((item) => (
              <div key={item.question_id} className="border-b border-wine/10 py-4 last:border-0">
                <div className="mb-2 flex items-center gap-2">
                  <span className="font-mono text-xs text-wine">Q: CO{item.co_number}</span>
                  <CO n={item.co_number} />
                  {item.chosen === item.correct ? (
                    <span className="text-xs text-success">✓ Correct</span>
                  ) : (
                    <span className="text-xs text-wine">✗ Incorrect</span>
                  )}
                </div>
                <p className="font-serif text-lg font-semibold text-espresso">{item.question}</p>
                <div className="mt-2 grid grid-cols-2 gap-2">
                  {item.options.map((opt, i) => (
                    <div
                      key={i}
                      className={cn(
                        "flex items-center gap-2 rounded-xl border px-3 py-2 text-sm",
                        i === item.correct
                          ? "border-success bg-success/10"
                          : i === item.chosen
                            ? "border-wine bg-wine/10"
                            : "border-wine/15",
                      )}
                    >
                      <span className="font-mono text-xs text-muted-foreground">{"ABCD"[i]}</span>
                      {opt}
                      {i === item.correct && (
                        <Check className="ml-auto size-4 text-success" />
                      )}
                    </div>
                  ))}
                </div>
                {item.explanation && (
                  <p className="mt-2 border-l-2 border-dusty pl-3 text-sm text-muted-foreground">
                    <b className="text-espresso">Why:</b> {item.explanation}
                  </p>
                )}
              </div>
            ))}
          </div>
          <div className="mt-6">
            <Btn variant="secondary" onClick={retry}>
              <RotateCcw className="size-4" />
              New attempt
            </Btn>
          </div>
        </Card>
      </Shell>
    );
  }

  return (
    <Shell role="student" subjectLabel={subjectLabel}>
      <PageHead
        eyebrow={`Attempt ${attempt.attempt_number} of ${totalAttempts}`}
        title={openQuiz?.title ?? "Quiz"}
        right={
          openQuiz?.closes_at ? (
            <div className="flex items-center gap-2 rounded-full bg-wine px-4 py-2 font-mono text-sm text-ivory">
              <Clock className="size-4" /> Closes in{" "}
              {formatDistanceToNow(new Date(openQuiz.closes_at), { addSuffix: true })}
            </div>
          ) : undefined
        }
      />
      <div className="grid grid-cols-12 gap-5">
        <Card className="col-span-8">
          <div className="flex items-center justify-between text-sm">
            <span className="font-mono text-wine">
              Question {currentQuestion + 1} of {questions.length}
            </span>
            <span
              className={cn("text-xs text-success transition", saved ? "opacity-100" : "opacity-0")}
            >
              ✓ Progress saved
            </span>
          </div>
          <div className="mt-2">
            <Bar v={((currentQuestion + 1) / questions.length) * 100} />
          </div>
          <p className="mt-8 font-serif text-3xl font-semibold text-espresso">
            {questions[currentQuestion]!.stem}
          </p>
          <div className="mt-6 space-y-3">
            {questions[currentQuestion]!.options.map((o, k) => (
              <button
                key={o}
                onClick={() => pick(k)}
                className={cn(
                  "flex w-full items-center gap-4 rounded-2xl border px-5 py-4 text-left transition",
                  answers[questions[currentQuestion]!.id] === k
                    ? "border-wine bg-wine text-ivory"
                    : "border-wine/20 bg-ivory hover:border-wine/60",
                )}
              >
                <span
                  className={cn(
                    "grid size-7 place-items-center rounded-full border font-mono text-xs",
                    answers[questions[currentQuestion]!.id] === k
                      ? "border-ivory"
                      : "border-wine/40 text-wine",
                  )}
                >
                  {"ABCD"[k]}
                </span>
                {o}
              </button>
            ))}
          </div>
          <div className="mt-8 flex justify-between">
            <Btn
              variant="secondary"
              disabled={currentQuestion === 0}
              onClick={() => setCurrentQuestion(currentQuestion - 1)}
            >
              Previous
            </Btn>
            {currentQuestion < questions.length - 1 ? (
              <Btn onClick={() => setCurrentQuestion(currentQuestion + 1)}>Next</Btn>
            ) : (
              <Btn onClick={() => setConfirm(true)}>Submit quiz</Btn>
            )}
          </div>
        </Card>
        <Card className="col-span-4" title="Navigator">
          <div className="grid grid-cols-5 gap-2">
            {questions.map((q, k) => (
              <button
                key={q.id}
                onClick={() => setCurrentQuestion(k)}
                className={cn(
                  "aspect-square rounded-xl border font-mono text-sm",
                  answers[q.id] !== undefined
                    ? "border-wine bg-wine text-ivory"
                    : "border-wine/30 text-wine",
                  currentQuestion === k && "ring-2 ring-dusty ring-offset-2 ring-offset-ivory",
                )}
              >
                {k + 1}
              </button>
            ))}
          </div>
          <div className="mt-4 flex gap-4 text-xs text-muted-foreground">
            <span className="flex items-center gap-1.5">
              <span className="size-3 rounded bg-wine" />
              Answered
            </span>
            <span className="flex items-center gap-1.5">
              <span className="size-3 rounded border border-wine/30" />
              Unanswered
            </span>
          </div>
          <Btn variant="secondary" className="mt-6 w-full" onClick={() => setConfirm(true)}>
            Submit quiz
          </Btn>
        </Card>
      </div>
      {confirm && (
        <div className="fixed inset-0 z-50 grid place-items-center bg-oxblood/40 p-4">
          <div className="paper w-full max-w-md p-8">
            <h2 className="display text-3xl">Submit this attempt?</h2>
            <p className="mt-2 text-sm text-muted-foreground">
              {unanswered.length ? (
                <>
                  You have <b className="text-wine">{unanswered.length} unanswered</b>: Q
                  {unanswered.join(", Q")}.
                </>
              ) : (
                "All questions answered."
              )}{" "}
              You'll have {attempt.attempts_left} attempt{attempt.attempts_left === 1 ? "" : "s"}{" "}
              left.
            </p>
            <div className="mt-6 flex justify-end gap-2">
              <Btn variant="ghost" onClick={() => setConfirm(false)}>
                Keep working
              </Btn>
              <Btn
                disabled={submitting}
                onClick={() => {
                  setConfirm(false);
                  handleSubmit();
                }}
              >
                <Check className="size-4" /> {submitting ? "Submitting…" : "Submit"}
              </Btn>
            </div>
          </div>
        </div>
      )}
    </Shell>
  );
}
