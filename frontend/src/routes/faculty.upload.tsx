import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { AlertTriangle, FileText, UploadCloud } from "lucide-react";
import { useRef, useState } from "react";
import { toast } from "sonner";
import { Toaster } from "@/components/ui/sonner";
import { Shell } from "@/components/lk/Shell";
import { Bar, Btn, Card, Chip, CO, Field, inputCls, PageHead } from "@/components/lk/ui";
import { cn } from "@/lib/utils";
import { ApiError, modules, roster, subjects, upload } from "@/lib/api";
import { getStoredSubjectId, storeSubjectId } from "@/lib/subject-context";
import type { CoverageItem, ModuleStatus, ModuleSummary, RosterConfirm, RosterPreview, SubjectDetail } from "@/lib/api";

export const Route = createFileRoute("/faculty/upload")({
  head: () => ({
    meta: [
      { title: "Modules & CO Coverage · LAKSHYA" },
      { name: "description", content: "Upload module slides and check course outcome coverage." },
      { property: "og:title", content: "Modules & CO Coverage · LAKSHYA" },
      { property: "og:description", content: "Upload slides and map them to course outcomes." },
    ],
  }),
  component: Page,
});

function Page() {
  const queryClient = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [subjectId, setSubjectId] = useState<string | null>(() => getStoredSubjectId());
  const [selectedModule, setSelectedModule] = useState<string | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [newModNumber, setNewModNumber] = useState("5");
  const [newModTitle, setNewModTitle] = useState("Query Optimisation");

  // Roster upload
  const [rosterFile, setRosterFile] = useState<File | null>(null);
  const [rosterPreview, setRosterPreview] = useState<RosterPreview | null>(null);
  const [rosterConfirming, setRosterConfirming] = useState(false);
  const [rosterResult, setRosterResult] = useState<RosterConfirm | null>(null);

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

  const { data: coverage } = useQuery<CoverageItem[]>({
    queryKey: ["coverage", activeSubject],
    queryFn: () => upload.getCoverage(activeSubject!),
    enabled: !!activeSubject,
  });

  const { data: moduleStatus, refetch: refetchStatus } = useQuery<ModuleStatus>({
    queryKey: ["module-status", selectedModule],
    queryFn: () => upload.getModuleStatus(selectedModule!),
    enabled: !!selectedModule,
    refetchInterval: (query) =>
      query.state.data?.processing_status === "processing" ? 5000 : false,
  });

  const createMutation = useMutation({
    mutationFn: (body: { number: number; title: string }) => modules.create(activeSubject!, body),
    onSuccess: (mod) => {
      queryClient.invalidateQueries({ queryKey: ["subject-detail", activeSubject] });
      setSelectedModule(mod.id);
      toast.success(`Module ${mod.number} created`);
    },
    onError: (e) => {
      if (e instanceof ApiError) toast.error(e.message);
      else toast.error("Failed to create module.");
    },
  });

  const uploadMutation = useMutation({
    mutationFn: ({ moduleId, formData }: { moduleId: string; formData: FormData }) =>
      upload.uploadModule(moduleId, formData),
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey: ["module-status", res.module_id] });
      setIsUploading(false);
      toast.success("Slides uploaded — processing in background.");
    },
    onError: (e) => {
      setIsUploading(false);
      if (e instanceof ApiError) setUploadError(e.message);
      else setUploadError("Upload failed.");
    },
  });

  const handleUpload = async () => {
    if (!selectedFile) {
      toast.error("Please select a .pptx file first.");
      return;
    }
    if (!selectedFile.name.toLowerCase().endsWith(".pptx")) {
      toast.error("Only .pptx files are supported.");
      return;
    }

    setUploadError(null);
    let modId = selectedModule;

    // Create module if none selected
    if (!modId) {
      const num = parseInt(newModNumber, 10);
      if (isNaN(num)) {
        toast.error("Please enter a valid module number.");
        return;
      }
      try {
        const mod = await createMutation.mutateAsync({
          number: num,
          title: newModTitle || `Module ${num}`,
        });
        modId = mod.id;
      } catch {
        return; // error handled by mutation
      }
    }

    // Upload PPTX
    setIsUploading(true);
    const formData = new FormData();
    formData.append("file", selectedFile);
    try {
      await uploadMutation.mutateAsync({ moduleId: modId, formData });
    } catch {
      // Error handled by mutation onError
    }
  };

  const statusChip = (m: ModuleSummary["processing_status"] | undefined) => {
    if (!m || m === "pending") return "Draft" as const;
    if (m === "processing") return "Processing" as const;
    if (m === "done") return "Done" as const;
    return "Failed" as const;
  };

  const handleRosterPreview = async (file: File) => {
    setRosterFile(file);
    setRosterPreview(null);
    setRosterResult(null);
    const formData = new FormData();
    formData.append("file", file);
    try {
      const preview = await roster.preview(activeSubject!, formData);
      setRosterPreview(preview);
    } catch (e) {
      if (e instanceof ApiError) toast.error(e.message);
      else toast.error("Failed to preview roster.");
    }
  };

  const handleRosterConfirm = async () => {
    if (!rosterFile) return;
    setRosterConfirming(true);
    const formData = new FormData();
    formData.append("file", rosterFile);
    try {
      const result = await roster.confirm(activeSubject!, formData);
      setRosterResult(result);
      setRosterPreview(null);
      queryClient.invalidateQueries({ queryKey: ["subjects"] });
      toast.success(`${result.created_enrollments} students enrolled.`);
    } catch (e) {
      if (e instanceof ApiError) toast.error(e.message);
      else toast.error("Failed to confirm roster.");
    } finally {
      setRosterConfirming(false);
    }
  };

  if (!subjectList?.length) {
    return (
      <Shell role="faculty">
        <PageHead eyebrow="Faculty" title="Upload" sub="No subjects assigned." />
      </Shell>
    );
  }

  return (
    <Shell role="faculty" subjectLabel={detail ? `${detail.code} · ${detail.name}` : undefined}>
      <Toaster />
      <PageHead
        eyebrow="Teaching · Modules"
        title="Slides & CO coverage"
        sub="Upload a module deck. Lakshya splits it into chunks and maps each to course outcomes."
        right={
          <select
            value={activeSubject ?? ""}
            onChange={(e) => {
              const val = e.target.value || null;
              setSubjectId(val);
              if (val) storeSubjectId(val);
              setSelectedModule(null);
              setSelectedFile(null);
              setUploadError(null);
            }}
            className="h-10 rounded-full border border-wine/30 bg-ivory px-4 text-sm text-wine"
          >
            {subjectList.map((s) => (
              <option key={s.id} value={s.id}>
                {s.code} — {s.name}
              </option>
            ))}
          </select>
        }
      />
      <div className="grid grid-cols-12 gap-5">
        {/* Upload form */}
        <Card className="col-span-7">
          <div className="space-y-4">
            <Field label="Module">
              <select
                value={selectedModule ?? ""}
                onChange={(e) => {
                  setSelectedModule(e.target.value || null);
                  setSelectedFile(null);
                  setUploadError(null);
                }}
                className={cn(inputCls, "w-full")}
              >
                <option value="">Create new module</option>
                {detail?.modules?.map((m) => (
                  <option key={m.id} value={m.id}>
                    M{m.number} — {m.title} ({m.processing_status})
                  </option>
                ))}
              </select>
            </Field>

            {!selectedModule && (
              <>
                <div className="grid grid-cols-3 gap-4">
                  <Field label="Module no.">
                    <input
                      type="number"
                      className={inputCls}
                      value={newModNumber}
                      onChange={(e) => setNewModNumber(e.target.value)}
                    />
                  </Field>
                  <div className="col-span-2">
                    <Field label="Module title">
                      <input
                        className={inputCls}
                        value={newModTitle}
                        onChange={(e) => setNewModTitle(e.target.value)}
                      />
                    </Field>
                  </div>
                </div>
              </>
            )}
          </div>

          <div className="mt-5">
            <div
              onClick={() => fileInputRef.current?.click()}
              className="flex h-32 w-full cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed border-wine/50 bg-beige/30 text-center transition hover:bg-beige/60"
            >
              <input
                type="file"
                accept=".pptx"
                ref={fileInputRef}
                className="hidden"
                onChange={(e) => setSelectedFile(e.target.files?.[0] ?? null)}
              />
              <UploadCloud className="size-10 text-wine" strokeWidth={1.3} />
              <div className="mt-3 font-serif text-2xl text-wine">
                {selectedFile?.name || "Drop your PPT here"}
              </div>
              <div className="text-sm text-muted-foreground">
                or click to browse · .pptx up to 25 MB
              </div>
            </div>
          </div>

          {isUploading && (
            <div className="mt-5 rounded-xl bg-beige/50 p-4">
              <div className="mb-2 flex justify-between text-sm">
                <span className="flex items-center gap-2">
                  <FileText className="size-4 text-wine" />
                  {selectedFile?.name || "Uploading..."}
                </span>
                <span className="font-mono text-xs">Uploading…</span>
              </div>
              <Bar v={50} />
            </div>
          )}

          {moduleStatus && moduleStatus.processing_status === "processing" && (
            <div className="mt-5 rounded-xl bg-beige/50 p-4">
              <div className="mb-2 flex justify-between text-sm">
                <span className="flex items-center gap-2">
                  <FileText className="size-4 text-wine" />
                  Processing chunks…
                </span>
                <span className="font-mono text-xs">
                  {moduleStatus.chunks_tagged}/{moduleStatus.chunks_total} tagged
                </span>
              </div>
              <Bar
                v={
                  moduleStatus.chunks_total > 0
                    ? (moduleStatus.chunks_tagged / moduleStatus.chunks_total) * 100
                    : 0
                }
              />
            </div>
          )}

          {uploadError && (
            <div className="mt-5 rounded-xl bg-wine/10 p-4">
              <p className="text-sm text-wine">{uploadError}</p>
            </div>
          )}

          <div className="mt-5 flex justify-end">
            <Btn onClick={handleUpload} disabled={isUploading || !activeSubject}>
              <UploadCloud className="size-4" />
              Upload & process
            </Btn>
          </div>
        </Card>

        {/* CO coverage */}
        <Card className="col-span-5" title="CO coverage">
          {!coverage?.length ? (
            <p className="py-8 text-center text-sm text-muted-foreground">
              Upload a module to see CO coverage.
            </p>
          ) : (
            <>
              {coverage.map((c) => (
                <div key={c.co_id} className="mb-3 flex items-center gap-3">
                  <CO n={c.co_number} />
                  <div className="flex-1">
                    <Bar v={Math.max(c.chunk_count * 5, 1)} tone={c.warning ? "wine" : "blue"} />
                  </div>
                  <span className="w-16 text-right font-mono text-xs">{c.chunk_count} chunks</span>
                </div>
              ))}
              {coverage.some((c) => c.warning) && (
                <div className="mt-4 flex gap-3 rounded-xl border border-wine bg-wine/5 p-4">
                  <AlertTriangle className="size-5 shrink-0 text-wine" />
                  <div className="text-sm">
                    <b className="text-wine">Some COs have low coverage.</b> Upload more slides to
                    improve coverage.
                  </div>
                </div>
              )}
            </>
          )}
        </Card>

        {/* Modules list */}
        <Card className="col-span-5" title="Modules">
          {!detail?.modules?.length ? (
            <p className="py-6 text-center text-sm text-muted-foreground">
              No modules yet. Create one above.
            </p>
          ) : (
            detail.modules.map((m) => (
              <button
                key={m.id}
                onClick={() => setSelectedModule(m.id)}
                className={cn(
                  "mb-2 flex w-full items-center gap-3 rounded-xl px-3 py-3 text-left",
                  selectedModule === m.id ? "bg-beige" : "hover:bg-beige/50",
                )}
              >
                <span className="font-mono text-xs text-wine">M{m.number}</span>
                <span className="flex-1 text-sm font-medium">{m.title}</span>
                {m.processed_at && (
                  <span className="font-mono text-[11px] text-muted-foreground">
                    {new Date(m.processed_at).toLocaleDateString()}
                  </span>
                )}
                <Chip s={statusChip(m.processing_status)} />
              </button>
            ))
          )}
        </Card>

        {/* Module processing status */}
        <Card className="col-span-7" title="Module status">
          {!selectedModule ? (
            <p className="py-6 text-center text-sm text-muted-foreground">
              Select a module to view its processing status.
            </p>
          ) : moduleStatus ? (
            <>
              <div className="mb-4 flex items-center justify-between">
                <span className="font-mono text-sm text-muted-foreground">
                  Status:{" "}
                  <span
                    className={cn(
                      "font-semibold",
                      moduleStatus.processing_status === "done"
                        ? "text-success"
                        : moduleStatus.processing_status === "processing"
                          ? "text-warn"
                          : moduleStatus.processing_status === "failed"
                            ? "text-wine"
                            : "text-espresso",
                    )}
                  >
                    {moduleStatus.processing_status}
                  </span>
                </span>
                <Chip
                  s={
                    moduleStatus.processing_status === "done"
                      ? "Done"
                      : moduleStatus.processing_status === "processing"
                        ? "Processing"
                        : moduleStatus.processing_status === "failed"
                          ? "Failed"
                          : "Draft"
                  }
                />
              </div>
              <div className="mb-2 flex justify-between text-sm">
                <span>Total chunks</span>
                <span className="font-mono">{moduleStatus.chunks_total}</span>
              </div>
              <Bar
                v={
                  moduleStatus.chunks_total > 0
                    ? (moduleStatus.chunks_tagged / moduleStatus.chunks_total) * 100
                    : 0
                }
              />
              <div className="mt-3 grid grid-cols-2 gap-4 text-center">
                <div>
                  <div className="text-2xl font-bold text-wine">{moduleStatus.chunks_tagged}</div>
                  <div className="text-xs text-muted-foreground">Tagged (CO mapped)</div>
                </div>
                <div>
                  <div className="text-2xl font-bold text-wine">{moduleStatus.chunks_untagged}</div>
                  <div className="text-xs text-muted-foreground">Untagged</div>
                </div>
              </div>
              {moduleStatus.error && (
                <div className="mt-4 rounded-xl bg-wine/10 p-3">
                  <p className="text-sm text-wine">{moduleStatus.error}</p>
                </div>
              )}
              {moduleStatus.processing_status === "failed" && (
                <Btn
                  variant="secondary"
                  className="mt-3 w-full"
                  onClick={async () => {
                    if (!selectedModule) return;
                    const formData = new FormData();
                    // Re-upload the same file to retry. User must select again.
                    const input = fileInputRef.current;
                    if (input?.files?.[0]) {
                      formData.append("file", input.files[0]);
                      setIsUploading(true);
                      try {
                        await uploadMutation.mutateAsync({
                          moduleId: selectedModule,
                          formData,
                        });
                        queryClient.invalidateQueries({ queryKey: ["subject-detail", activeSubject] });
                        toast.success("Retry upload started.");
                      } catch (e) {
                        if (e instanceof ApiError) toast.error(e.message);
                        else toast.error("Retry failed.");
                      } finally {
                        setIsUploading(false);
                      }
                    } else {
                      toast.error("Please select a .pptx file to retry.");
                    }
                  }}
                >
                  Retry upload
                </Btn>
              )}
            </>
          ) : (
            <p className="py-6 text-center text-sm text-muted-foreground">Status not available.</p>
          )}
        </Card>

        {/* Roster upload */}
        <Card className="col-span-12" title="Roster upload">
          {!rosterPreview && !rosterResult ? (
            <div>
              <p className="text-sm text-muted-foreground">
                Upload a CSV roster to enrol students. The file is previewed before
                any changes are applied.
              </p>
              <div className="mt-4 flex items-center gap-3">
                <input
                  type="file"
                  accept=".csv"
                  onChange={(e) => {
                    const f = e.target.files?.[0];
                    if (f) void handleRosterPreview(f);
                    e.target.value = "";
                  }}
                />
                {!activeSubject && (
                  <span className="text-xs text-wine">Select a subject first.</span>
                )}
              </div>
            </div>
          ) : rosterPreview ? (
            <RosterPreviewView
              preview={rosterPreview}
              onConfirm={handleRosterConfirm}
              confirming={rosterConfirming}
            />
          ) : rosterResult ? (
            <RosterResultView result={rosterResult} subjectName={detail?.name ?? activeSubject ?? ""} />
          ) : null}
        </Card>
      </div>
    </Shell>
  );
}

function RosterPreviewView({
  preview,
  onConfirm,
  confirming,
}: {
  preview: RosterPreview;
  onConfirm: () => void;
  confirming: boolean;
}) {
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-4 gap-4 text-center">
        <div className="paper p-3">
          <div className="text-2xl font-bold text-wine">{preview.total_rows}</div>
          <div className="eyebrow">Total rows</div>
        </div>
        <div className="paper p-3">
          <div className="text-2xl font-bold text-success">{preview.valid.length}</div>
          <div className="eyebrow">Valid</div>
        </div>
        <div className="paper p-3">
          <div className="text-2xl font-bold text-warn">{preview.bad_rows.length}</div>
          <div className="eyebrow">Invalid</div>
        </div>
        <div className="paper p-3">
          <div className="text-2xl font-bold text-oxblood">{preview.already_enrolled.length}</div>
          <div className="eyebrow">Already enrolled</div>
        </div>
      </div>

      {preview.bad_rows.length > 0 && (
        <div>
          <h4 className="eyebrow mb-2">Invalid rows</h4>
          <div className="space-y-1">
            {preview.bad_rows.map((r) => (
              <div key={r.row} className="font-mono text-xs text-wine">
                Row {r.row} ({r.usn}): {r.reason}
              </div>
            ))}
          </div>
        </div>
      )}

      {preview.duplicates_in_file.length > 0 && (
        <div>
          <h4 className="eyebrow mb-2">Duplicates in file</h4>
          <div className="space-y-1">
            {preview.duplicates_in_file.map((d) => (
              <div key={d.usn} className="font-mono text-xs text-wine">
                {d.usn} appears on rows: {d.rows.join(", ")}
              </div>
            ))}
          </div>
        </div>
      )}

      {preview.already_enrolled.length > 0 && (
        <div>
          <h4 className="eyebrow mb-2">Already enrolled</h4>
          <div className="flex flex-wrap gap-1">
            {preview.already_enrolled.map((usn) => (
              <span key={usn} className="font-mono text-xs text-wine">
                {usn}
              </span>
            ))}
          </div>
        </div>
      )}

      <Btn onClick={onConfirm} disabled={confirming || preview.valid.length === 0}>
        {confirming ? "Confirming…" : "Confirm enrolment"}
      </Btn>
    </div>
  );
}

function RosterResultView({ result, subjectName }: { result: RosterConfirm; subjectName: string }) {
  return (
    <div className="space-y-4">
      <p className="text-sm">
        Enrolled {result.created_enrollments} students ({result.created_students} new accounts) into{" "}
        <b>{subjectName}</b>.
      </p>
      {result.skipped.length > 0 && (
        <div>
          <h4 className="eyebrow mb-2">Skipped</h4>
          <div className="space-y-1">
            {result.skipped.map((s) => (
              <div key={s.row} className="font-mono text-xs">
                Row {s.row} ({s.usn}): {s.reason}
              </div>
            ))}
          </div>
        </div>
      )}
      {result.credentials.length > 0 && (
        <div>
          <h4 className="eyebrow mb-2">New student PINs (share securely)</h4>
          <div className="grid grid-cols-2 gap-2 font-mono text-xs">
            {result.credentials.map((c) => (
              <div key={c.usn} className="rounded border border-wine/20 px-2 py-1">
                <span className="text-muted-foreground">{c.usn}:</span>{" "}
                <span className="font-semibold text-wine">{c.pin}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
