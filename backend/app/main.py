from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import IntegrityError

from .config import FRONTEND_ORIGIN
from .errors import (
    AppError,
    app_error_handler,
    validation_exception_handler,
    integrity_error_handler,
    unexpected_exception_handler,
)
from .routers import (
    auth, subjects, modules, roster, questions, health, quizzes, quizzes_admin, attempts,
    upload, co_sheet, study, calendar, usage,
)


app = FastAPI(
    title="Academic Assistant & CO Tracker",
    description="FastAPI backend for academics, grading and CO attainment.",
)

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_ORIGIN],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Exception handlers — order matters: specific first, generic last
# ---------------------------------------------------------------------------

app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(IntegrityError, integrity_error_handler)
app.add_exception_handler(Exception, unexpected_exception_handler)

# ---------------------------------------------------------------------------
# Routers (add new ones here — one line each)
# ---------------------------------------------------------------------------

routers = [
    health.router,
    auth.router,
    subjects.router,
    modules.router,
    roster.router,
    questions.router,
    quizzes_admin.router,  # restored from 8b266dd — full quiz/create/publish endpoints
    quizzes.router,        # minimal — full implementation is Arya's section 7
    attempts.router,       # section 7 — attempt start, resume, save, submit, review
    upload.router,         # section 6 — slide upload, status, coverage (Arya)
    co_sheet.router,       # section 8 — CO sheet, summary, drill-down, export, progress (Arya)
    study.router,          # section 9 — Q&A, study plan, flashcards, notes (Arya)
    calendar.router,       # section 10 — events (Arya)
    usage.router,          # section 12 — token usage summary (Arya)
]

for r in routers:
    app.include_router(r)
