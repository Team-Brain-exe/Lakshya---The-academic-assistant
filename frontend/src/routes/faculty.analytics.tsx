import { useQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { Download } from "lucide-react";
import { useState } from "react";
import { Shell } from "@/components/lk/Shell";
import { Bar, Btn, Card, CO, PageHead } from "@/components/lk/ui";
import { cn } from "@/lib/utils";
import { ApiError, coSheet, subjects } from "@/lib/api";
import { getStoredSubjectId, storeSubjectId } from "@/lib/subject-context";
import type { COSheet, COSummaryItem, WeakCO } from "@/lib/api";

export const Route = createFileRoute("/faculty/analytics")({
  head: () => ({
    meta: [
      { title: "CO Sheet & Analytics · LAKSHYA" },
      {
        name: "description",
        content: "Course outcome attainment per student, with charts and exports.",
      },
      { property: "og:title", content: "CO Sheet & Analytics · LAKSHYA" },
      { property: "og:description", content: "Professional CO attainment reporting." },
    ],
  }),
  component: Page,
});

function Page() {
  const [subjectId, setSubjectId] = useState<string | null>(() => getStoredSubjectId());
  const [scope, setScope] = useState<"semester" | "module">("semester");
  const [moduleId, setModuleId] = useState<string | null>(null);
  const [section, setSection] = useState<string>("");
  const [error, setError] = useState<string | null>(null);

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

  const { data: sheets } = useQuery<COSheet>({
    queryKey: ["co-sheet", activeSubject, scope, moduleId, section],
    queryFn: () =>
      coSheet.getSheet(activeSubject!, {
        scope,
        module_id: moduleId ?? undefined,
        section: section || undefined,
      }),
    enabled: !!activeSubject,
  });

  const { data: coSummary } = useQuery<COSummaryItem[]>({
    queryKey: ["co-summary", activeSubject, section],
    queryFn: () => coSheet.getSummary(activeSubject!, section || undefined),
    enabled: !!activeSubject,
  });

  const { data: weakCOs } = useQuery<WeakCO[]>({
    queryKey: ["weak-co", activeSubject, section],
    queryFn: () => coSheet.getWeakCOs(activeSubject!, section || undefined),
    enabled: !!activeSubject,
  });

  // ── Derived values ──────────────────────────────────────────────────
  const cols = sheets?.columns ?? [];
  const sheetRows = sheets?.rows ?? [];

  const AVG = cols.map((col) => Math.round(sheets?.averages[col] ?? 0));

  // Score distribution: [0-40, 40-50, 50-60, 60-70, 70-80, 80+]
  const DIST = [
    sheetRows.filter((r) => r.total_pct < 40).length,
    sheetRows.filter((r) => r.total_pct >= 40 && r.total_pct < 50).length,
    sheetRows.filter((r) => r.total_pct >= 50 && r.total_pct < 60).length,
    sheetRows.filter((r) => r.total_pct >= 60 && r.total_pct < 70).length,
    sheetRows.filter((r) => r.total_pct >= 70 && r.total_pct < 80).length,
    sheetRows.filter((r) => r.total_pct >= 80).length,
  ];

  const targetPct = detail?.target_attainment_pct ?? 60;
  const avgOverall =
    AVG.length && AVG.every((v) => v === 0)
      ? 0
      : Math.round(AVG.reduce((s, v) => s + v, 0) / (AVG.length || 1));

  const weakInsights = (weakCOs ?? []).slice(0, 2).map((w) => {
    const co = detail?.cos?.find((c) => c.number === w.co_number);
    const summary = coSummary?.find((s) => s.co_number === w.co_number);
    return {
      co: w.co_number,
      pct: w.attainment_pct ?? 0,
      desc: co?.description ?? `CO${w.co_number}`,
      insight: summary
        ? `${summary.below} of ${summary.enrolled} students below ${summary.threshold_pct}% threshold`
        : `${Math.round(w.gap ?? 0)}% below target`,
    };
  });

  const handleExport = async () => {
    if (!activeSubject) return;
    try {
      const blob = await coSheet.exportSheet(activeSubject, {
        scope,
        module_id: moduleId ?? undefined,
        section: section || undefined,
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `co_sheet.xlsx`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      if (e instanceof ApiError) setError(e.message);
      else setError("Export failed.");
    }
  };

  if (!subjectList?.length) {
    return (
      <Shell role="faculty">
        <PageHead eyebrow="Faculty" title="Analytics" sub="No subjects assigned." />
      </Shell>
    );
  }

  if (error) {
    return (
      <Shell role="faculty">
        <PageHead eyebrow="Analytics" title="CO sheet" />
        <div className="py-12 text-center">
          <p className="text-wine">{error}</p>
        </div>
      </Shell>
    );
  }

  return (
    <Shell role="faculty" subjectLabel={detail ? `${detail.code} · ${detail.name}` : undefined}>
      <PageHead
        eyebrow="Reports · Attainment"
        title="CO sheet"
        right={
          <div className="flex items-center gap-3">
            {subjectList.length > 1 && (
              <select
                value={activeSubject ?? ""}
                onChange={(e) => {
                  const val = e.target.value || null;
                  setSubjectId(val);
                  if (val) storeSubjectId(val);
                  setModuleId(null);
                }}
                className="h-10 rounded-full border border-wine/30 bg-ivory px-4 text-sm text-wine"
              >
                {subjectList.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.code} — {s.name}
                  </option>
                ))}
              </select>
            )}
            <div className="flex rounded-full bg-ivory p-1">
              {(
                [
                  ["Semester", "semester"],
                  ["Module", "module"],
                ] as const
              ).map(([label, val]) => (
                <button
                  key={val}
                  onClick={() => {
                    setScope(val);
                    setModuleId(null);
                  }}
                  className={cn(
                    "rounded-full px-4 py-1.5 text-sm",
                    scope === val ? "bg-wine text-ivory" : "text-wine hover:bg-beige/50",
                  )}
                >
                  {label}
                </button>
              ))}
            </div>
            {scope === "module" && (
              <select
                value={moduleId ?? ""}
                onChange={(e) => setModuleId(e.target.value || null)}
                className="h-10 rounded-full border border-wine/30 bg-ivory px-4 text-sm text-wine"
              >
                <option value="">Select module</option>
                {detail?.modules?.map((m) => (
                  <option key={m.id} value={m.id}>
                    M{m.number} — {m.title}
                  </option>
                ))}
              </select>
            )}
            <select
              value={section}
              onChange={(e) => setSection(e.target.value)}
              className="h-10 rounded-full border border-wine/30 bg-ivory px-4 text-sm text-wine"
            >
              <option value="">All sections</option>
            </select>
            <Btn variant="secondary" onClick={handleExport}>
              <Download className="size-4" />
              Export to Excel
            </Btn>
          </div>
        }
      />
      <div className="grid grid-cols-12 gap-5">
        <Card className="col-span-7" title="Average score by CO">
          {cols.length === 0 ? (
            <p className="py-8 text-center text-sm text-muted-foreground">
              No data available for this scope.
            </p>
          ) : (
            <>
              <div className="relative flex h-56 items-end gap-5 border-b border-wine/20 pl-3">
                <div
                  className="absolute inset-x-0 border-t-2 border-dashed border-oxblood/70"
                  style={{ bottom: `${targetPct}%` }}
                />
                {AVG.map((v, i) => (
                  <div
                    key={i}
                    className="relative flex flex-1 flex-col items-center justify-end"
                    style={{ height: "100%" }}
                  >
                    <div className="absolute -top-2 rounded-md bg-oxblood px-2 py-1 font-mono text-[11px] text-ivory">
                      {v}%
                    </div>
                    <div
                      className={cn(
                        "w-full rounded-t-lg transition",
                        v < targetPct ? "bg-wine" : "bg-dusty",
                      )}
                      style={{ height: `${Math.max(v, 1)}%` }}
                    />
                  </div>
                ))}
              </div>
              <div className="mt-3 flex gap-5 pl-3">
                {AVG.map((_, i) => (
                  <div key={i} className="flex flex-1 justify-center">
                    <CO n={i + 1} />
                  </div>
                ))}
              </div>
            </>
          )}
          <div className="mt-3 flex gap-4 text-xs text-muted-foreground">
            <span className="flex items-center gap-1.5">
              <span className="size-2.5 rounded-sm bg-dusty" />
              Meets target
            </span>
            <span className="flex items-center gap-1.5">
              <span className="size-2.5 rounded-sm bg-wine" />
              Below target
            </span>
            <span className="flex items-center gap-1.5">
              <span className="h-0 w-4 border-t-2 border-dashed border-oxblood" />
              Target {targetPct}%
            </span>
          </div>
        </Card>

        <Card className="col-span-5" title="Score distribution">
          {sheetRows.length === 0 ? (
            <p className="py-8 text-center text-sm text-muted-foreground">
              No student data for this scope.
            </p>
          ) : (
            <>
              <div className="flex h-56 items-end gap-2">
                {DIST.map((d, i) => (
                  <div key={i} className="flex flex-1 flex-col items-center gap-1">
                    <span className="font-mono text-[10px]">{d}</span>
                    <div
                      className="stripes-blue w-full rounded-t-md border border-dusty"
                      style={{ height: `${d * 10}px` }}
                    />
                  </div>
                ))}
              </div>
              <div className="mt-2 flex gap-2 font-mono text-[10px] text-muted-foreground">
                {["0-40", "40-50", "50-60", "60-70", "70-80", "80+"].map((l) => (
                  <span key={l} className="flex-1 text-center">
                    {l}
                  </span>
                ))}
              </div>
            </>
          )}
        </Card>

        <Card className="col-span-12 !p-0 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-wine text-ivory">
              <tr>
                {["USN", "Name", ...cols, "Total"].map((h, i) => (
                  <th
                    key={h}
                    className={cn("px-4 py-3 font-medium", i < 2 ? "text-left" : "text-right")}
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {sheetRows.map((r) => (
                <tr key={r.usn} className="border-b border-wine/10 even:bg-beige/30">
                  <td className="px-4 py-3 font-mono text-xs">{r.usn}</td>
                  <td className="px-4 py-3">{r.name}</td>
                  {cols.map((col) => {
                    const score = r.co_scores[col];
                    const isNull = score === null || score === undefined;
                    return (
                      <td key={col} className="px-4 py-3 text-right font-mono">
                        <span
                          className={cn(
                            "rounded px-1.5 py-0.5",
                            !isNull && score < targetPct && "bg-wine/10 font-semibold text-wine",
                          )}
                        >
                          {isNull ? "—" : score}
                        </span>
                      </td>
                    );
                  })}
                  <td className="px-4 py-3 text-right font-mono font-semibold">
                    {Math.round(r.total_pct)}
                  </td>
                </tr>
              ))}
              <tr className="bg-dusty/40 font-medium">
                <td className="px-4 py-3 eyebrow !text-oxblood" colSpan={2}>
                  Average attainment
                </td>
                {AVG.map((v, i) => (
                  <td
                    key={i}
                    className={cn("px-4 py-3 text-right font-mono", v < targetPct && "text-wine")}
                  >
                    {v}
                  </td>
                ))}
                <td className="px-4 py-3 text-right font-mono">{avgOverall}</td>
              </tr>
            </tbody>
          </table>
        </Card>

        {weakInsights.map((w) => (
          <div key={w.co} className="paper-wine col-span-6 p-6">
            <div className="flex items-center gap-3">
              <CO n={w.co} className="!bg-ivory !text-wine" />
              <span className="font-serif text-2xl">{w.desc}</span>
              <span className="ml-auto font-mono">{w.pct}%</span>
            </div>
            <p className="mt-2 text-sm text-beige/90">{w.insight}.</p>
          </div>
        ))}
      </div>
    </Shell>
  );
}
