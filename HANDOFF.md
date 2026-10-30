# HANDOFF — Lakshya Frontend Integration

## Build Status
- TypeScript: `tsc --noEmit` — PASS (exit 0)
- Vite production build: PASS (exit 0, `vite build`)

## Environment
- Backend URL: `https://lakshya-the-academic-assistant.onrender.com`
- Frontend env var: `VITE_API_URL=https://lakshya-the-academic-assistant.onrender.com`
- See `frontend/.env.example`

## Completed Features

### 1. API Client & Authentication (`src/lib/api.ts`)
- Full typed API client covering all backend endpoints
- Reads `VITE_API_URL` from env, defaults to Render URL
- Supports JSON requests and multipart FormData uploads
- Error parsing from `{"error":{"code":"...","message":"..."}}`
- Token stored in memory + sessionStorage; `Authorization: Bearer` header on requests
- 401 auto-clears session and redirects to `/login`
- No backend secrets in frontend env

### 2. Auth Context (`src/lib/auth-context.tsx`)
- `AuthProvider` wrapping the app with login/logout/refetch
- `RequireAuth` guard for protected routes
- SSR-safe `sessionStorage` access via `typeof` guards
- Logout clears token + cached user data

### 3. Login & Workspace (`src/routes/index.tsx`, `src/routes/__root.tsx`)
- Login persists token via `useAuth().login()`
- Redirects by role: student → `/student/home`, faculty → `/faculty/dashboard`
- Session restored on refresh
- Subjects loaded via `GET /subjects`
- Subject selector persisted in `sessionStorage` (`src/lib/subject-context.ts`)

### 4. Shell (`src/components/lk/Shell.tsx`)
- Auth integration, route protection, real logout
- `subjectLabel` prop on both student and faculty shells
- Functional assistant panel with proposal review

### 5. Faculty Routes (all connected)
- **Dashboard** — `GET /subjects/{id}`, `/co-summary`, `/weak-cos`, `/quizzes`, `/events`
- **Upload** — `POST /subjects`, `PUT /cos`, `POST /modules`, `POST /modules/{id}/upload` (FormData), `GET /modules/{id}/status` (polling), `/coverage`; roster preview + confirm flow
- **Review** — `GET /questions?module_id=`, `POST /questions`, `PATCH /questions/{id}`
- **Quiz Builder** — `POST /quizzes`, `POST /quizzes/{id}/publish`; time validation (`closes_at` after `opens_at`); "Save as draft" before publish
- **Analytics** — CO scores with null-safe rendering ("—" for null)

### 6. Student Routes (connected)
- **Student Home** — `GET /students/me/progress`, `/quizzes?subject_id=`, `/events`; quizzes filtered by subject; real empty states
- **Student Quiz** — `GET /quizzes?subject_id=`; attempt start/state/resume via `sessionStorage`; answer auto-save; `POST /attempts/{id}/submit`; `POST /attempts/{id}/review`; anti-duplicate guards on start/submit; retry button only when attempts remain

## Unfinished Features (left as-is per scope constraint)
- `/login` standalone route (`src/routes/login.tsx`) — exists but not fully wired into auth flow (login is handled on `src/routes/index.tsx`)
- `student.learning` route — not created (referenced in original checklist but not started)
- `student.study-plan`, `student.flashcards`, `student.qa`, `student.calendar` quick links — not created (only `/student/home` and `/student/quiz` exist)
- No new tests added (existing test at `src/test/app-routing.test.tsx` untouched)
- Backend CORS (`backend/app/main.py`) — `main.py` was modified (see git diff) but should be verified in production

## Files Modified
- `frontend/src/lib/api.ts` (new)
- `frontend/src/lib/auth-context.tsx` (new)
- `frontend/src/lib/subject-context.ts` (new)
- `frontend/src/components/lk/Shell.tsx` (rewritten)
- `frontend/src/components/lk/ui.tsx` (minor tweaks)
- `frontend/src/routes/index.tsx` (login + auth)
- `frontend/src/routes/__root.tsx` (AuthProvider wrapper)
- `frontend/src/routes/student.home.tsx` (subject filtering, Shell subjectLabel, quick links)
- `frontend/src/routes/student.quiz.tsx` (subject filtering, attempt persistence, review, anti-duplicate)
- `frontend/src/routes/faculty.dashboard.tsx`
- `frontend/src/routes/faculty.upload.tsx`
- `frontend/src/routes/faculty.review.tsx`
- `frontend/src/routes/faculty.quiz-builder.tsx`
- `frontend/src/routes/faculty.analytics.tsx`
- `frontend/src/routeTree.gen.ts` (auto-updated)
- `frontend/.env.example` (new)
- `frontend/src/vite-env.d.ts` (new)
- `backend/app/main.py` (CORS, see git diff)
