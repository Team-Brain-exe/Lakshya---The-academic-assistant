import sys
from pathlib import Path

# The shared AI package lives at the repository root, while the existing launch
# command runs with `backend/` as the working directory.
_REPO_ROOT = str(Path(__file__).resolve().parents[2])
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

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
from .routers import auth, subjects, modules, roster, questions, health, quizzes, quizzes_admin, attempts, agent
from .services.agent_runtime import close_agent_runtime, configure_agent_runtime


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
    agent.router,          # role-scoped agent; handlers are injected by the runtime bootstrap
]

for r in routers:
    app.include_router(r)

# Agent routes stay disabled until the HTTPS provider and task-specific models
# are configured in .env. Tool contracts still omit any unimplemented handlers.
configure_agent_runtime(app)
app.router.add_event_handler("shutdown", lambda: close_agent_runtime(app))