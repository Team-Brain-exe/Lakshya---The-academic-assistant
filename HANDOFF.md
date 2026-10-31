# HANDOFF — Lakshya Frontend Integration

## Build Status
- TypeScript: `tsc --noEmit` — PASS (exit 0)
- Vite production build: PASS (exit 0, `vite build`)

## Environment
- Backend URL: `https://lakshya-the-academic-assistant.onrender.com`
- Frontend env var: `VITE_API_URL=https://lakshya-the-academic-assistant.onrender.com`
- See `frontend/.env.example`

## Backend CORS (required Render setting)
- `backend/app/main.py` already parses `FRONTEND_ORIGIN` as comma-separated:
  `allow_origins=[o.strip() for o in FRONTEND_ORIGIN.split(",") if o.strip()]`
- Required Render environment variable: `FRONTEND_ORIGIN=https://lakshya-the-academic-assistant.onrender.com`
- For local dev, set: `FRONTEND_ORIGIN=http://localhost:3000`
- For both: `FRONTEND_ORIGIN=https://lakshya-the-academic-assistant.onrender.com,http://localhost:3000`
- No other backend logic was changed.

## Submission Flow Verification
1. Login — POST /auth/login with {usn, pin} or {email, password}. Verified in index.tsx. Token stored in memory + sessionStorage.
2. Profile — GET /auth/me called by useAuth().login() via refetch().
3. Role redirect — index.tsx navigates to /student/home or /faculty/dashboard.
4. Route protection — Shell bounces unauthenticated users to /.
5. Subjects — GET /subjects via subjects.list(). Persisted via sessionStorage.
6. Quiz list — GET /quizzes?subject_id={id} filtered by subject.
7. Start attempt — POST /quizzes/{id}/attempts. Backend returns {attempt_id, attempt_number, attempts_left, questions}. Verified.
8. Resume — GET /attempts/{id}. Attempt ID persisted in sessionStorage.
9. Save answers — PUT /attempts/{id}/answers with {answers}. Backend reads payload.get("answers"). Verified.
10. Submit — POST /attempts/{id}/submit with {answers}. Backend reads payload.get("answers"). Verified. Anti-duplicate via submitting state + session clear.
11. Review — GET /attempts/{id}/review. Wired to "Review answers" button.

## Completed Features
- API client (src/lib/api.ts), auth context (src/lib/auth-context.tsx), subject persistence (src/lib/subject-context.ts)
- Login on / (src/routes/index.tsx) with real POST /auth/login + GET /auth/me, role-based redirect, Shell guard to /
- Shell (src/components/lk/Shell.tsx): auth, route protection, logout, assistant panel, disabled "Coming soon" nav items for nonexistent student routes
- Student Home: subject-filtered quizzes/events, real empty states, coming-soon quick links
- Student Quiz: subject filtering, attempt start/resume via sessionStorage, answer auto-save, submit, review, anti-duplicate guards, retry when attempts remain
- Faculty Dashboard, Upload, Review, Quiz Builder, Analytics — all connected to real backend

## Unfinished (left as-is)
- /login standalone route — exists but login is on /
- student.study-plan, student.flashcards, student.qa, student.calendar — do not exist, shown as "Coming soon"
- student.learning — does not exist
- No new tests

## Files Modified
- frontend/src/lib/api.ts, auth-context.tsx, subject-context.ts (new)
- frontend/src/components/lk/Shell.tsx (rewritten)
- frontend/src/routes/index.tsx, student.home.tsx, student.quiz.tsx (updated)
- frontend/src/routes/faculty.{dashboard,upload,review,quiz-builder,analytics}.tsx (updated)
- frontend/src/routeTree.gen.ts (auto-updated)
- frontend/.env.example, frontend/src/vite-env.d.ts (new)
- backend/app/main.py (CORS unchanged — already comma-separated)
