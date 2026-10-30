
import sys
from pathlib import Path

# The shared AI package lives at the repository root, while the existing
# launch command runs with backend/ as the working directory.
_REPO_ROOT = str(Path(__file__).resolve().parents[2])
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from fastapi import FastAPI
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
    auth,
    subjects,
    modules,
    roster,
    questions,
    health,
    quizzes,
    quizzes_admin,
    attempts,
    upload,
    co_sheet,
    study,
    calendar,
    usage,
    agent,
)
from .services.agent_runtime import (
    close_agent_runtime,
    configure_agent_runtime,
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
    allow_origins=[o.strip() for o in FRONTEND_ORIGIN.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Exception handlers — specific handlers first, generic handler last
# ---------------------------------------------------------------------------

app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(
    RequestValidationError, validation_exception_handler
)
app.add_exception_handler(IntegrityError, integrity_error_handler)
app.add_exception_handler(Exception, unexpected_exception_handler)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

routers = [
    health.router,
    auth.router,
    subjects.router,
    modules.router,
    roster.router,
    questions.router,
    quizzes_admin.router,
    quizzes.router,
    attempts.router,
    upload.router,
    co_sheet.router,
    study.router,
    calendar.router,
    usage.router,
    agent.router,
]

for router in routers:
    app.include_router(router)

# Agent routes remain unconfigured until the required model and provider
# settings are available. The runtime handles the unconfigured case.
configure_agent_runtime(app)

# Close the shared agent HTTP client during FastAPI shutdown.
app.add_event_handler(
    "shutdown",
    lambda: close_agent_runtime(app),
)
