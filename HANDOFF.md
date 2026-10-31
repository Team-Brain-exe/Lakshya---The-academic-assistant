# HANDOFF — Lakshya Frontend Integration

## Build Status
- TypeScript: `tsc --noEmit` — PASS (exit 0)
- Vite production build: PASS (exit 0, `vite build`)
- Tests: 6/6 passing (vitest, mocked network responses)

## Environment
- Backend URL: `https://lakshya-the-academic-assistant.onrender.com`
- Frontend env var: `VITE_API_URL=https://lakshya-the-academic-assistant.onrender.com`
- See `frontend/.env.example`

## Backend CORS (required Render setting)
- `backend/app/main.py` already parses `FRONTEND_ORIGIN` as comma-separated:
  `allow_origins=[o.strip() for o in FRONTEND_ORIGIN.split(",") if o.strip()]`
- For local dev + production simultaneously, set Render:
  `FRONTEND_ORIGIN=https://lakshya-the-academic-assistant.onrender.com,http://localhost:5173`
- `FRONTEND_ORIGIN` must contain **frontend origins**, not the backend URL.
- No other backend logic was changed.

## Login Flow (traced end-to-end)
1. Form submit in `index.tsx` → `useAuth().login({usn, pin})` at top level.
2. POST `/auth/login` → backend returns `{access_token, token_type, user}`.
3. Token stored via `setToken(data.access_token)` **before** calling `getMe`.
4. `GET /auth/me` called via `auth.getMe()` (auth=true); 401 on `/auth/me` redirects to `/`.
5. AuthProvider resolves the server profile → `nav()` routes by `result.role`:
   - `student` → `/student/home`
   - `faculty` → `/faculty/dashboard`.
6. Route guard in `__root.tsx` + `RequireAuth` in `Shell.tsx` waits for auth
   restoration before redirecting (no flash of login page for authenticated users).

## Key Fixes This Session
1. **`LOGIN_PATH`**: changed from `/login` → `/` so all redirects target the real
   login form. The standalone `/login` route redirects to `/` and is dead code.
2. **401 handler**: only redirects on authenticated requests (`res.status === 401 && auth`).
   Failed login (auth=false) now shows the backend error in-place without reloading.
3. **`auth-context.tsx` `login()`**: uses `data.user` from `LoginResponse` directly,
   sets token first, then calls `getMe()` to refresh/correct the profile. Removed the
   stale JWT-decode fallback — on `getMe` failure the token is cleared, error is set,
   and the error is **re-thrown** so `index.tsx` catches it and displays
   `serverError` instead of silently navigating to a page that the Shell guard
   bounces back to login.
4. **`logout()`**: clears `lakshya_active_attempt`, `lakshya_answers_*`, selected subject,
   and `lakshya_token` via `clearToken`.
5. **`student.quiz.tsx`**: removed `useEffect` that auto-started attempts on page open.
   Replaced with an explicit quiz-list view where the user clicks "Start attempt". Added
   server-confirmed "Saved" indicator (was optimistic), save-error display, debounced
   save coalescing (no older-save-overwrite races), and `quizzes` query invalidation after
   submit. Retry uses explicit start, not auto-start. Submit uses `attempt.attempt_id`
   (not whichever quiz happens to be first open).
6. **USN regex**: relaxed from `^1[A-Z]{2}\d{2}[A-Z]{2}\d{3}$` to `^[A-Za-z0-9]{3,20}$`
   so valid USNs of any format are accepted.
7. **Shell.tsx hooks**: `useState(assistantOpen)` moved before the conditional
   `loading`/`!isAuthenticated` return (hooks-order violation fixed).
8. **Shell.tsx + student.home.tsx**: nonexistent student routes (`/student/study-plan`,
   `/student/flashcards`, `/student/qa`, `/student/calendar`) render as disabled
   "Coming soon" buttons — no links to dead routes. No `student.learning` route exists.

## Submission Flow Verification (API payloads vs backend)
| Step | Frontend call | Backend | Verified |
|------|--------------|---------|----------|
| Login | POST /auth/login `{usn,pin}` | routers/auth.py | curl OK |
| Profile | GET /auth/me | routers/auth.py | code OK |
| Subjects | GET /subjects | routers/subjects.py | code OK |
| Quiz list | GET /quizzes?subject_id= | routers/quizzes_admin.py | code OK |
| Start attempt | POST /quizzes/{id}/attempts | routers/quizzes.py | code OK |
| Attempt state | GET /attempts/{id} | routers/attempts.py | code OK |
| Save answers | PUT /attempts/{id}/answers `{answers}` | routers/attempts.py | code OK |
| Submit | POST /attempts/{id}/submit `{answers}` | routers/attempts.py | code OK |
| Review | GET /attempts/{id}/review | routers/attempts.py | code OK |
| CO sheet | GET /subjects/{id}/co-sheet | routers/co_sheet.py | code OK |
| Calendar | GET /events | routers/calendar.py | code OK |
| Module upload | POST /modules/{id}/upload | routers/upload.py | code OK |
| Approve Q | POST /questions/{id}/approve | routers/questions.py | code OK |

## Working Features
- Login on `/` with real `POST /auth/login` + `GET /auth/me`, role-based redirect
- Shell auth guard, logout, assistant panel, disabled "Coming soon" nav items
- Student Home: subject-filtered quizzes, real empty/error/loading states
- Student Quiz: explicit start, attempt resume via sessionStorage, debounced
  answer save, submit, review, retry when attempts remain, query invalidation
- Faculty Dashboard, Upload (roster preview → module upload → status poll →
  question approval), Review (approve/reject), Quiz Builder (draft + publish),
  Analytics (CO sheet + export)

## Remaining Limitations
- No live browser test performed — login flow verified via mocked vitest integration
  tests (auth-flow.test.tsx) plus curl preflight + POST /auth/login verification.
- `/login` standalone route (910 chars) exists as dead code — not the active path.
- student.study-plan, student.flashcards, student.qa, student.calendar do not exist;
  shown as disabled "Coming soon" items. Not built per scope.
- No tests for student.quiz.tsx flows (start/resume/submit/review) — the mocked
  auth-flow.test.tsx covers login/logout/navigation only.

## Files Modified This Session
- `frontend/src/lib/api.ts` — LOGIN_PATH → `/`, 401 handler guards on `auth` flag
- `frontend/src/lib/auth-context.tsx` — login() uses LoginResponse.user, logout clears state
- `frontend/src/lib/subject-context.ts` — added clearSavedAttempt()
- `frontend/src/routes/index.tsx` — USN regex relaxed
- `frontend/src/components/lk/Shell.tsx` — hooks order, disabled nav items
- `frontend/src/routes/student.home.tsx` — disabled quick links for nonexistent routes
- `frontend/src/routes/student.quiz.tsx` — removed auto-start, explicit start, server-confirmed saves, serialized saves, submit invalidation
- `frontend/src/test/auth-flow.test.tsx` — 6 mocked integration tests
- `frontend/HANDOFF.md` — this file
