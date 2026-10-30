/// <reference types="vite/client" />

/**
 * LAKSHYA typed API client.
 *
 * Reads the backend origin from VITE_API_URL (defaults to the Render deployment),
 * keeps the bearer token in memory + sessionStorage, sends Authorization on every
 * authenticated request, parses backend errors from
 *   { "error": { "code": "...", "message": "...", "details": {...} } }
 * and on an HTTP 401 clears the session and redirects to /login.
 */

// ── Environment ─────────────────────────────────────────────────────────

/** Backend API origin.  Read from VITE_API_URL, falling back to Render. */
export const BASE_URL: string =
  import.meta.env.VITE_API_URL ?? "https://lakshya-the-academic-assistant.onrender.com";

/** Where to send the user when their session is no longer valid. */
export const LOGIN_PATH = "/login";

// ── Token management ────────────────────────────────────────────────────

const TOKEN_KEY = "lakshya_access_token";

/** In-memory copy so we avoid hitting sessionStorage on every request. */
let _token: string | null = null;

/** Populate the in-memory token from sessionStorage (browser only). */
function _hydrateToken(): void {
  if (typeof sessionStorage !== "undefined") {
    _token = sessionStorage.getItem(TOKEN_KEY);
  }
}

_hydrateToken();

/** Persist a new token to memory and sessionStorage. */
export function setToken(token: string): void {
  _token = token;
  if (typeof sessionStorage !== "undefined") {
    sessionStorage.setItem(TOKEN_KEY, token);
  }
}

/** Return the current bearer token, or null when unauthenticated. */
export function getToken(): string | null {
  return _token;
}

/** Remove the token from memory and sessionStorage. */
export function clearToken(): void {
  _token = null;
  if (typeof sessionStorage !== "undefined") {
    sessionStorage.removeItem(TOKEN_KEY);
  }
}

/** True when a usable token is present. */
export function isAuthenticated(): boolean {
  return _token !== null && _token.length > 0;
}

// ── Error model ─────────────────────────────────────────────────────────

/** The `details` sub-object that may accompany a backend error. */
export interface ErrorDetails {
  field?: string;
  value?: unknown;
  constraint?: string;
  fields?: Array<{ field: string; message: string }>;
  [key: string]: unknown;
}

/** Parsed body of every backend error response. */
export interface BackendErrorBody {
  error: {
    code: string;
    message: string;
    details?: ErrorDetails;
  };
}

/**
 * Thrown by the client for non-2xx responses and network failures.
 * `status` is 0 for network-level failures.
 */
export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details?: ErrorDetails | undefined;

  constructor(status: number, code: string, message: string, details?: ErrorDetails) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }

  /** Human-friendly summary, combining the code and message. */
  override toString(): string {
    return `[${this.name}] ${this.code} (HTTP ${this.status}): ${this.message}`;
  }
}

// ── Core request ────────────────────────────────────────────────────────

export type HttpMethod = "GET" | "POST" | "PATCH" | "PUT" | "DELETE";

export interface RequestOptions {
  method?: HttpMethod;
  /** JSON-serialisable body, or a FormData instance for file uploads. */
  body?: unknown;
  /** Query-string parameters (omitted when null/undefined / empty string). */
  params?: Record<string, string | number | boolean | null | undefined> | undefined;
  /** Extra request headers. */
  headers?: Record<string, string>;
  /** Attach the bearer token (default true). */
  auth?: boolean;
  /** Interpret the response as a Blob (for binary downloads). */
  responseType?: "json" | "blob";
}

/** Build a query string from a params map, skipping null/undefined values. */
function buildQuery(params: RequestOptions["params"] | undefined): string {
  if (!params) return "";
  const parts: string[] = [];
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null) continue;
    parts.push(`${encodeURIComponent(key)}=${encodeURIComponent(String(value))}`);
  }
  return parts.length ? `?${parts.join("&")}` : "";
}

/**
 * Low-level fetch wrapper that handles auth, serialisation, error parsing
 * and the 401 → redirect behaviour.
 */
export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const {
    method = "GET",
    body,
    params,
    headers = {},
    auth = true,
    responseType = "json",
  } = options;

  // ── Assemble URL ──
  const url = `${BASE_URL}${path}${buildQuery(params)}`;

  // ── Assemble headers ──
  const hdr = new Headers();
  for (const [k, v] of Object.entries(headers)) hdr.set(k, v);

  if (auth) {
    const token = getToken();
    if (token) {
      hdr.set("Authorization", `Bearer ${token}`);
    }
  }

  // ── Assemble fetch options ──
  const fetchOpts: RequestInit = { method, headers: hdr, credentials: "include" };

  if (body instanceof FormData) {
    // Let the browser set Content-Type (multipart/form-data; boundary=…).
    fetchOpts.body = body;
  } else if (body !== undefined && body !== null) {
    hdr.set("Content-Type", "application/json");
    fetchOpts.body = JSON.stringify(body);
  }

  // ── Execute ──
  let res: Response;
  try {
    res = await fetch(url, fetchOpts);
  } catch {
    throw new ApiError(0, "NETWORK_ERROR", "Network error — please check your connection.");
  }

  // ── 401 → clear session & redirect ──
  if (res.status === 401) {
    clearToken();
    if (typeof window !== "undefined" && typeof window.location !== "undefined") {
      window.location.href = LOGIN_PATH;
    }
    throw new ApiError(401, "UNAUTHENTICATED", "Your session has expired. Please log in again.");
  }

  // ── Parse body ──
  const contentType = res.headers.get("content-type") ?? "";
  let data: unknown;

  if (responseType === "blob") {
    data = await res.blob();
  } else if (contentType.includes("application/json")) {
    const text = await res.text();
    // An empty body is possible (e.g. DELETE returns {} but some endpoints return nothing)
    data = text.trim() ? JSON.parse(text) : null;
  } else {
    data = await res.text();
  }

  // ── Error branch ──
  if (!res.ok) {
    // Backend format: { "error": { "code": "...", "message": "...", "details": {...} } }
    if (
      data !== null &&
      typeof data === "object" &&
      "error" in data &&
      typeof (data as BackendErrorBody).error === "object"
    ) {
      const err = (data as BackendErrorBody).error;
      throw new ApiError(res.status, err.code, err.message, err.details);
    }
    throw new ApiError(res.status, "HTTP_ERROR", `Request failed with status ${res.status}.`);
  }

  return data as T;
}

// ── Domain types ────────────────────────────────────────────────────────
// These mirror the backend response shapes exactly (see backend/app/routers/*.py).

export type Role = "student" | "faculty";

export interface User {
  id: string;
  role: Role;
  name: string;
  usn: string | null;
  email: string | null;
  student_id?: string;
}

// ── Auth ──

export interface LoginCredentials {
  usn?: string;
  pin?: string;
  email?: string;
  password?: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  role: Role;
  user: User;
}

// ── Health ──

export interface HealthStatus {
  status: string;
}

// ── Subjects ──

export interface Subject {
  id: string;
  code: string;
  name: string;
  semester: string;
  target_attainment_pct: number;
  default_threshold_pct: number;
  faculty_user_id: string;
}

export interface CourseOutcome {
  id: string;
  subject_id: string;
  number: number;
  description: string;
  threshold_pct: number;
  target_attainment_pct: number;
}

export interface ModuleSummary {
  id: string;
  subject_id: string;
  number: number;
  title: string;
  ppt_file_path: string | null;
  processing_status: string;
  processing_error: string | null;
  processed_at: string | null;
}

export interface SubjectDetail extends Subject {
  cos: CourseOutcome[];
  modules: ModuleSummary[];
}

export interface CreateSubjectBody {
  code: string;
  name: string;
  semester: string;
  target_attainment_pct?: number;
  default_threshold_pct?: number;
}

export interface CosUpsert {
  cos: Array<{
    number: number;
    description: string;
    threshold_pct?: number;
    target_attainment_pct?: number;
  }>;
}

export interface CreateModuleBody {
  number: number;
  title: string;
}

// ── Questions ──

export interface Question {
  id: string;
  module_id: string;
  co_id: string;
  co_number: number;
  stem: string;
  options: string[];
  correct_option: number;
  explanation: string | null;
  marks: number | null;
  difficulty: string | null;
  bloom_level: string | null;
  status: string;
  source: string;
  created_by: string | null;
}

export interface CreateQuestionBody {
  module_id: string;
  co_id: string;
  stem: string;
  options: string[];
  correct_option: number;
  explanation?: string;
  marks?: number;
  difficulty?: string;
  bloom_level?: string;
}

// ── Quizzes ──

export interface Quiz {
  id: string;
  module_id: string | null;
  subject_id: string;
  title: string;
  opens_at: string | null;
  closes_at: string | null;
  published: boolean;
  published_at: string | null;
  question_count: number;
  attempts_used?: number;
  attempts_left?: number;
  event_id?: string;
}

export interface QuizQuestion {
  id: string;
  module_id: string;
  co_id: string;
  co_number: number;
  stem: string;
  options: string[];
  marks: number;
}

export interface AttemptStart {
  attempt_id: string;
  attempt_number: number;
  attempts_left: number;
  questions: QuizQuestion[];
}

export interface AttemptState {
  attempt_id: string;
  quiz_id: string;
  attempt_number: number;
  attempts_left: number;
  status: "in_progress" | "submitted";
  answers: Record<string, number>;
  questions: QuizQuestion[];
  closes_at: string | null;
}

export interface SubmitResult {
  total_score: number;
  max_score: number;
  co_scores: Array<{
    co_number: number;
    marks: number;
    max: number;
    percentage: number | null;
  }>;
}

export interface ReviewItem {
  question_id: string;
  question: string;
  options: string[];
  chosen: number | null;
  correct: number;
  co_number: number;
  explanation: string | null;
}

export interface CreateQuizBody {
  module_id: string;
  title: string;
  question_ids: string[];
  opens_at?: string | undefined;
  closes_at?: string | undefined;
}

// ── Upload / Coverage ──

export interface ModuleStatus {
  processing_status: string;
  chunks_total: number;
  chunks_tagged: number;
  chunks_untagged: number;
  error: string | null;
}

export interface CoverageItem {
  co_id: string;
  co_number: number;
  chunk_count: number;
  warning: boolean;
  message: string | null;
}

// ── CO Sheet / Analytics ──

export interface COSheetRow {
  usn: string;
  name: string;
  section: string;
  co_scores: Record<string, number>;
  total: number;
  total_obtained: number;
  total_max: number;
  total_pct: number;
}

export interface COSheet {
  columns: string[];
  rows: COSheetRow[];
  averages: Record<string, number>;
}

export interface COSummaryItem {
  co_number: number;
  threshold_pct: number;
  target_pct: number;
  enrolled: number;
  attempted: number;
  average: number | null;
  above: number;
  below: number;
  attainment_pct: number | null;
  met: boolean;
  target_met: boolean;
  gap: number | null;
}

export interface WeakCO {
  co_number: number;
  attainment_pct: number | null;
  target_pct: number;
  gap: number | null;
}

export interface StudentProgressCO {
  co_number: number;
  marks_obtained: number | null;
  max_marks: number | null;
  percentage: number | null;
  threshold_pct: number;
  attained: boolean;
}

export interface StudentProgressAttempt {
  quiz_id: string;
  module_id: string;
  co_scores: Record<string, number | null>;
}

export interface StudentProgress {
  usn: string;
  name: string;
  section: string;
  subject_id: string;
  co_scores: StudentProgressCO[];
  attempts: StudentProgressAttempt[];
}

// ── Calendar ──

export type EventType = "quiz" | "assignment" | "exam" | "teaching" | "custom";

export interface CalendarEvent {
  id: string;
  subject_id: string;
  type: EventType;
  title: string;
  starts_at: string;
  ends_at: string | null;
  section: string | null;
  quiz_id: string | null;
  module_id: string | null;
  created_by: string | null;
  created_by_agent: boolean;
  created_at: string;
}

export interface CreateEventBody {
  subject_id: string;
  type: EventType;
  title: string;
  starts_at: string;
  ends_at?: string | null;
  section?: string | null;
  quiz_id?: string | null;
  module_id?: string | null;
}

// ── Study / QA ──

export interface Citation {
  module_id: string;
  slide_number: number;
}

export interface QAResult {
  answer: string;
  citations: Citation[];
  refused: boolean;
}

export interface RetrievalChunk {
  chunk_id: string;
  module_id: string;
  slide_number: number;
  text: string;
  score: number;
}

export interface StudyStep {
  co_number: number;
  goal: string;
  recommendation: string;
  slides: Array<{
    module_id: string;
    slide_number: number;
    summary: string;
  }>;
  flashcards: Array<{
    id: string;
    front: string;
    back: string;
  }>;
}

export interface StudyPlan {
  id: string;
  student_id: string;
  subject_id: string;
  weak_co_ids: string[];
  plan: {
    title: string;
    weak_cos: number[];
    steps: StudyStep[];
    created_at: string;
  };
  generated_at: string;
}

export interface Flashcard {
  id: string;
  module_id: string;
  co_id: string | null;
  front: string;
  back: string;
}

export interface Note {
  id: string;
  module_id: string;
  co_id: string | null;
  title: string;
  body: string;
}

export interface QARequest {
  subject_id: string;
  question: string;
}

// ── Roster ──

export interface RosterPreview {
  total_rows: number;
  valid: Array<{ row: number; usn: string; name: string; section: string }>;
  bad_rows: Array<{ row: number; usn: string; reason: string }>;
  duplicates_in_file: Array<{ usn: string; rows: number[] }>;
  already_enrolled: string[];
}

export interface RosterConfirm {
  created_students: number;
  created_enrollments: number;
  skipped: Array<{ row: number; usn: string; reason: string }>;
  credentials: Array<{ usn: string; pin: string }>;
}

// ── Agent ──

export interface AgentProposal {
  id: string;
  description: string;
  confirmed: boolean;
}

export interface AgentChatResponse {
  conversation_id: string;
  reply: string;
  tool_calls: unknown[];
  proposals: AgentProposal[];
  drafts: unknown[];
}

// ── Usage ──

export interface UsageSummaryEntry {
  step: string;
  calls: number;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
}

// ── Auth API ────────────────────────────────────────────────────────────

/**
 * Store the token from a login response and return the user/role payload.
 */
export function setSession(data: LoginResponse): void {
  setToken(data.access_token);
}

export const auth = {
  /**
   * Authenticate a student (usn + pin) or faculty (email + password).
   * On success the token is persisted to sessionStorage.
   */
  login(credentials: LoginCredentials): Promise<LoginResponse> {
    return apiRequest<LoginResponse>("/auth/login", {
      method: "POST",
      body: credentials,
      auth: false,
    });
  },

  /** Clear the stored token without hitting the backend. */
  logout(): void {
    clearToken();
  },

  /** Fetch the authenticated user's profile (calls /auth/me). */
  getMe(): Promise<User> {
    return apiRequest<User>("/auth/me");
  },
};

// ── Health ──────────────────────────────────────────────────────────────

export const health = {
  check(): Promise<HealthStatus> {
    return apiRequest<HealthStatus>("/health", { auth: false });
  },
};

// ── Subjects ────────────────────────────────────────────────────────────

export const subjects = {
  list(): Promise<Subject[]> {
    return apiRequest<Subject[]>("/subjects");
  },

  get(id: string): Promise<SubjectDetail> {
    return apiRequest<SubjectDetail>(`/subjects/${encodeURIComponent(id)}`);
  },

  create(body: CreateSubjectBody): Promise<Subject> {
    return apiRequest<Subject>("/subjects", { method: "POST", body });
  },

  update(id: string, body: Partial<CreateSubjectBody>): Promise<Subject> {
    return apiRequest<Subject>(`/subjects/${encodeURIComponent(id)}`, {
      method: "PATCH",
      body,
    });
  },

  remove(id: string): Promise<{ deleted: boolean }> {
    return apiRequest<{ deleted: boolean }>(`/subjects/${encodeURIComponent(id)}`, {
      method: "DELETE",
    });
  },

  listCOs(subjectId: string): Promise<CourseOutcome[]> {
    return apiRequest<CourseOutcome[]>(`/subjects/${encodeURIComponent(subjectId)}/cos`);
  },

  upsertCOs(subjectId: string, body: CosUpsert): Promise<CourseOutcome[]> {
    return apiRequest<CourseOutcome[]>(`/subjects/${encodeURIComponent(subjectId)}/cos`, {
      method: "PUT",
      body,
    });
  },
};

// ── Modules ─────────────────────────────────────────────────────────────

export const modules = {
  create(subjectId: string, body: CreateModuleBody): Promise<ModuleSummary> {
    return apiRequest<ModuleSummary>(`/subjects/${encodeURIComponent(subjectId)}/modules`, {
      method: "POST",
      body,
    });
  },

  update(
    id: string,
    body: Partial<
      CreateModuleBody &
        Pick<ModuleSummary, "ppt_file_path" | "processing_status" | "processing_error">
    >,
  ): Promise<ModuleSummary> {
    return apiRequest<ModuleSummary>(`/modules/${encodeURIComponent(id)}`, {
      method: "PATCH",
      body,
    });
  },

  remove(id: string): Promise<{ deleted: boolean }> {
    return apiRequest<{ deleted: boolean }>(`/modules/${encodeURIComponent(id)}`, {
      method: "DELETE",
    });
  },
};

// ── Questions ───────────────────────────────────────────────────────────

export interface QuestionListParams {
  module_id: string;
  co_id?: string;
  status?: string;
  source?: string;
}

export const questions = {
  list(params: QuestionListParams): Promise<Question[]> {
    const qp: Record<string, string | number | boolean | null | undefined> = {
      module_id: params.module_id,
    };
    if (params.co_id) qp["co_id"] = params.co_id;
    if (params.status) qp["status"] = params.status;
    if (params.source) qp["source"] = params.source;
    return apiRequest<Question[]>("/questions", { params: qp });
  },

  create(body: CreateQuestionBody): Promise<Question> {
    return apiRequest<Question>("/questions", { method: "POST", body });
  },

  batchCreate(bodies: CreateQuestionBody[]): Promise<Question[]> {
    return apiRequest<Question[]>("/questions/batch", {
      method: "POST",
      body: { questions: bodies },
    });
  },

  update(
    id: string,
    body: Partial<CreateQuestionBody & { status?: string; source?: string }>,
  ): Promise<Question> {
    return apiRequest<Question>(`/questions/${encodeURIComponent(id)}`, {
      method: "PATCH",
      body,
    });
  },

  approve(id: string): Promise<Question> {
    return apiRequest<Question>(`/questions/${encodeURIComponent(id)}/approve`, {
      method: "POST",
    });
  },

  reject(id: string): Promise<Question> {
    return apiRequest<Question>(`/questions/${encodeURIComponent(id)}/reject`, {
      method: "POST",
    });
  },
};

// ── Quizzes ─────────────────────────────────────────────────────────────

export const quizzes = {
  list(params?: { subject_id?: string; module_id?: string }): Promise<Quiz[]> {
    if (params?.subject_id || params?.module_id) {
      const qp: Record<string, string | number | boolean | null | undefined> = {};
      if (params?.subject_id) qp["subject_id"] = params.subject_id;
      if (params?.module_id) qp["module_id"] = params.module_id;
      return apiRequest<Quiz[]>("/quizzes", { params: qp });
    }
    return apiRequest<Quiz[]>("/quizzes");
  },

  get(id: string): Promise<Quiz> {
    return apiRequest<Quiz>(`/quizzes/${encodeURIComponent(id)}`);
  },

  create(body: CreateQuizBody): Promise<Quiz> {
    return apiRequest<Quiz>("/quizzes", { method: "POST", body });
  },

  publish(id: string): Promise<Quiz> {
    return apiRequest<Quiz>(`/quizzes/${encodeURIComponent(id)}/publish`, {
      method: "POST",
    });
  },

  addQuestion(id: string, questionId: string): Promise<{ added: boolean; question_id: string }> {
    return apiRequest<{ added: boolean; question_id: string }>(
      `/quizzes/${encodeURIComponent(id)}/questions`,
      { method: "POST", body: { question_id: questionId } },
    );
  },
};

// ── Attempts ────────────────────────────────────────────────────────────

export const attempts = {
  start(quizId: string): Promise<AttemptStart> {
    return apiRequest<AttemptStart>(`/quizzes/${encodeURIComponent(quizId)}/attempts`, {
      method: "POST",
    });
  },

  getState(id: string): Promise<AttemptState> {
    return apiRequest<AttemptState>(`/attempts/${encodeURIComponent(id)}`);
  },

  saveAnswers(id: string, answers: Record<string, number>): Promise<{ saved: boolean }> {
    return apiRequest<{ saved: boolean }>(`/attempts/${encodeURIComponent(id)}/answers`, {
      method: "PUT",
      body: { answers },
    });
  },

  submit(id: string, answers: Record<string, number>): Promise<SubmitResult> {
    return apiRequest<SubmitResult>(`/attempts/${encodeURIComponent(id)}/submit`, {
      method: "POST",
      body: { answers },
    });
  },

  review(id: string): Promise<ReviewItem[]> {
    return apiRequest<ReviewItem[]>(`/attempts/${encodeURIComponent(id)}/review`);
  },
};

// ── Upload / Coverage ──────────────────────────────────────────────────

export const upload = {
  /**
   * Upload a .pptx deck for a module.
   * Pass a FormData with a `file` field, or a Blob/File directly.
   */
  uploadModule(
    moduleId: string,
    formData: FormData,
  ): Promise<{ module_id: string; processing_status: string }> {
    return apiRequest<{ module_id: string; processing_status: string }>(
      `/modules/${encodeURIComponent(moduleId)}/upload`,
      { method: "POST", body: formData },
    );
  },

  getModuleStatus(moduleId: string): Promise<ModuleStatus> {
    return apiRequest<ModuleStatus>(`/modules/${encodeURIComponent(moduleId)}/status`);
  },

  getCoverage(subjectId: string): Promise<CoverageItem[]> {
    return apiRequest<CoverageItem[]>(`/subjects/${encodeURIComponent(subjectId)}/coverage`);
  },
};

// ── CO Sheet / Analytics ────────────────────────────────────────────────

export interface COSheetOptions {
  scope?: string;
  module_id?: string | undefined;
  section?: string | undefined;
}

/** Convert an options object into query params, omitting undefined values. */
function toParams(obj: object | undefined): RequestOptions["params"] | undefined {
  if (!obj) return undefined;
  const out: Record<string, string | number | boolean | null | undefined> = {};
  for (const [k, v] of Object.entries(obj)) {
    if (v !== undefined && v !== null && v !== "") out[k] = String(v);
  }
  return Object.keys(out).length ? out : undefined;
}

export const coSheet = {
  getSheet(subjectId: string, options?: COSheetOptions): Promise<COSheet> {
    return apiRequest<COSheet>(`/subjects/${encodeURIComponent(subjectId)}/co-sheet`, {
      params: toParams(options),
    });
  },

  getSummary(subjectId: string, section?: string): Promise<COSummaryItem[]> {
    return apiRequest<COSummaryItem[]>(`/subjects/${encodeURIComponent(subjectId)}/co-summary`, {
      params: section ? { section } : undefined,
    });
  },

  getWeakCOs(subjectId: string, section?: string): Promise<WeakCO[]> {
    return apiRequest<WeakCO[]>(`/subjects/${encodeURIComponent(subjectId)}/weak-cos`, {
      params: section ? { section } : undefined,
    });
  },

  getDrilldown(
    subjectId: string,
    coId: string,
    options?: { module_id?: string; section?: string },
  ): Promise<unknown> {
    return apiRequest<unknown>(
      `/subjects/${encodeURIComponent(subjectId)}/cos/${encodeURIComponent(coId)}/drilldown`,
      { params: toParams(options) },
    );
  },

  exportSheet(subjectId: string, options?: COSheetOptions): Promise<Blob> {
    return apiRequest<Blob>(`/subjects/${encodeURIComponent(subjectId)}/co-sheet/export`, {
      params: toParams(options),
      responseType: "blob",
    });
  },

  getStudentProgress(usn: string, subjectId: string): Promise<StudentProgress> {
    return apiRequest<StudentProgress>(`/students/${encodeURIComponent(usn)}/progress`, {
      params: { subject_id: subjectId },
    });
  },

  getMyProgress(subjectId: string): Promise<StudentProgress> {
    return apiRequest<StudentProgress>("/students/me/progress", {
      params: { subject_id: subjectId },
    });
  },
};

// ── Calendar ────────────────────────────────────────────────────────────

export interface CalendarListParams {
  subject_id?: string;
  from?: string;
  to?: string;
}

export const calendarApi = {
  list(params?: CalendarListParams): Promise<CalendarEvent[]> {
    return apiRequest<CalendarEvent[]>("/events", { params: toParams(params) });
  },

  create(body: CreateEventBody): Promise<CalendarEvent> {
    return apiRequest<CalendarEvent>("/events", { method: "POST", body });
  },

  update(eventId: string, body: Partial<CreateEventBody>): Promise<CalendarEvent> {
    return apiRequest<CalendarEvent>(`/events/${encodeURIComponent(eventId)}`, {
      method: "PATCH",
      body,
    });
  },

  remove(eventId: string): Promise<{ deleted: boolean }> {
    return apiRequest<{ deleted: boolean }>(`/events/${encodeURIComponent(eventId)}`, {
      method: "DELETE",
    });
  },
};

// ── Study / QA ──────────────────────────────────────────────────────────

export const study = {
  askQA(body: QARequest): Promise<QAResult> {
    return apiRequest<QAResult>("/qa", { method: "POST", body });
  },

  retrieve(subjectId: string, query: string): Promise<RetrievalChunk[]> {
    return apiRequest<RetrievalChunk[]>("/retrieve", {
      params: { subject_id: subjectId, q: query },
    });
  },

  createStudyPlan(subjectId: string): Promise<StudyPlan> {
    return apiRequest<StudyPlan>("/students/me/study-plan", {
      method: "POST",
      body: { subject_id: subjectId },
    });
  },

  getStudyPlan(subjectId: string): Promise<StudyPlan> {
    return apiRequest<StudyPlan>("/students/me/study-plan", {
      params: { subject_id: subjectId },
    });
  },

  generateMaterial(
    moduleId: string,
    regenerate?: boolean,
  ): Promise<{ flashcards: Flashcard[]; notes: Note[] }> {
    const params: RequestOptions["params"] = {};
    if (regenerate !== undefined) params["regenerate"] = regenerate;
    return apiRequest<{ flashcards: Flashcard[]; notes: Note[] }>(
      `/modules/${encodeURIComponent(moduleId)}/study-material`,
      { method: "POST", params },
    );
  },

  listFlashcards(moduleId: string): Promise<Flashcard[]> {
    return apiRequest<Flashcard[]>(`/modules/${encodeURIComponent(moduleId)}/flashcards`);
  },

  listNotes(moduleId: string): Promise<Note[]> {
    return apiRequest<Note[]>(`/modules/${encodeURIComponent(moduleId)}/notes`);
  },
};

// ── Roster ──────────────────────────────────────────────────────────────

export const roster = {
  /**
   * Preview a CSV roster upload. Pass a FormData with a `file` field.
   */
  preview(subjectId: string, formData: FormData): Promise<RosterPreview> {
    return apiRequest<RosterPreview>(`/subjects/${encodeURIComponent(subjectId)}/roster/preview`, {
      method: "POST",
      body: formData,
    });
  },

  /**
   * Confirm a CSV roster upload. Pass a FormData with a `file` field.
   */
  confirm(subjectId: string, formData: FormData): Promise<RosterConfirm> {
    return apiRequest<RosterConfirm>(`/subjects/${encodeURIComponent(subjectId)}/roster`, {
      method: "POST",
      body: formData,
    });
  },
};

// ── Agent ───────────────────────────────────────────────────────────────

export const agent = {
  chat(message: string, conversationId?: string): Promise<AgentChatResponse> {
    return apiRequest<AgentChatResponse>("/agent/chat", {
      method: "POST",
      body:
        conversationId !== undefined ? { message, conversation_id: conversationId } : { message },
    });
  },

  confirm(proposalId: string, approve: boolean): Promise<unknown> {
    return apiRequest<unknown>("/agent/confirm", {
      method: "POST",
      body: { proposal_id: proposalId, approve },
    });
  },
};

// ── Usage ───────────────────────────────────────────────────────────────

export const usageApi = {
  summary(params?: { from?: string; to?: string }): Promise<UsageSummaryEntry[]> {
    return apiRequest<UsageSummaryEntry[]>("/usage/summary", { params: toParams(params) });
  },

  // ── Convenience ────────────────────────────────────────────────────────

  /**
   * Decode the JWT payload (without verification) to read role/student_id/usn
   * client-side. Useful for quick checks without a round-trip to /auth/me.
   */
  currentUser(): User | null {
    const token = getToken();
    if (!token) return null;
    try {
      const parts = token.split(".");
      if (parts.length < 2) return null;
      const segment = parts[1];
      if (!segment) return null;
      const payload = JSON.parse(atob(segment.replace(/-/g, "+").replace(/_/g, "/"))) as {
        sub?: string;
        role?: string;
        student_id?: string;
        usn?: string;
        name?: string;
        email?: string;
      };
      if (!payload.sub || !payload.role) return null;
      const user: User = {
        id: payload.sub,
        role: payload.role as Role,
        name: payload.name ?? "",
        usn: payload.usn ?? null,
        email: payload.email ?? null,
      };
      if (payload.student_id !== undefined) {
        user.student_id = payload.student_id;
      }
      return user;
    } catch {
      return null;
    }
  },
};
