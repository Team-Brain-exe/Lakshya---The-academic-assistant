"""Tests for backend/app/agent_tools.py (docs/api-contract.md section 11)."""
from sqlalchemy import text

import pytest

from backend.app.agent_tools import (
    GetCOAttainmentArgs,
    FindWeakCOsArgs,
    GetStudentProgressArgs,
    ExportSheetArgs,
    GenerateQuizArgs,
    export_sheet,
    find_weak_COs,
    generate_quiz,
    get_co_attainment,
    get_student_progress,
)
from backend.app.errors import AppError
from backend.app.engine.co_math import (
    AttemptScore,
    COMarks,
    COConfig,
    StudentInfo,
)
from backend.app.services.co_analytics import InMemoryAnalyticsStore


# ---------------------------------------------------------------------------
# Helpers to build in-memory analytics data
# ---------------------------------------------------------------------------

def _make_attempt_score(usn, quiz_id, module_id, attempt_number, co_marks):
    return AttemptScore(
        usn=usn,
        quiz_id=quiz_id,
        module_id=module_id,
        attempt_number=attempt_number,
        per_co={c: COMarks(co=c, obtained=o, maximum=m) for c, (o, m) in co_marks.items()},
    )


def _make_store(cos, roster, attempts, progress_map=None):
    return InMemoryAnalyticsStore(
        cos=cos,
        roster=roster,
        attempts=attempts,
        progress_map=progress_map or {},
    )


# ---------------------------------------------------------------------------
# Fake AI generation for generate_quiz tests (no network / no API key needed)
# ---------------------------------------------------------------------------

_FAKE_QUESTION = {
    "stem": "Test question stem?",
    "options": ["Option A", "Option B", "Option C", "Option D"],
    "correct_option": 0,
    "explanation": "Test explanation",
    "marks": 1.0,
    "difficulty": "medium",
    "bloom_level": "remember",
    "status": "draft",
    "source": "AI",
}


@pytest.fixture
def fake_ai(monkeypatch):
    """Monkeypatch the AI generation call so no network or API key is needed."""
    monkeypatch.setenv("TOKEN_FACTORY_API_KEY", "test-key")
    monkeypatch.setenv("TOKEN_FACTORY_BASE_URL", "https://test.token.factory")
    monkeypatch.setenv("MODEL_GENERATION", "test-model")

    class FakeClient:
        def __init__(self, **kwargs):
            pass
        def close(self):
            pass

    def fake_generate_quiz(module, co, difficulty, count, client, *, model,
                           usage_recorder=None):
        if usage_recorder is not None:
            usage_recorder({"step": "quiz_generation", "model": model,
                            "prompt_tokens": 10, "completion_tokens": 20,
                            "total_tokens": 30})
        return [_FAKE_QUESTION.copy() for _ in range(count)]

    import backend.app.agent_tools as at
    monkeypatch.setattr(at, "_ai_generate_quiz", fake_generate_quiz)
    monkeypatch.setattr(at, "TokenFactoryClient", FakeClient)


@pytest.fixture
def fake_ai_failure(monkeypatch):
    """Monkeypatch the AI generation to raise QuizGenerationError."""
    monkeypatch.setenv("TOKEN_FACTORY_API_KEY", "test-key")
    monkeypatch.setenv("TOKEN_FACTORY_BASE_URL", "https://test.token.factory")
    monkeypatch.setenv("MODEL_GENERATION", "test-model")

    class FakeClient:
        def __init__(self, **kwargs):
            pass
        def close(self):
            pass

    from ai.quiz_generation import QuizGenerationError

    def failing_generate_quiz(*args, **kwargs):
        raise QuizGenerationError("Model returned garbage")

    import backend.app.agent_tools as at
    monkeypatch.setattr(at, "_ai_generate_quiz", failing_generate_quiz)
    monkeypatch.setattr(at, "TokenFactoryClient", FakeClient)


# ---------------------------------------------------------------------------
# get_co_attainment
# ---------------------------------------------------------------------------

def test_get_co_attainment_faculty():
    """Faculty calling get_co_attainment gets class summary data."""
    cos = [COConfig(number=1, threshold_pct=60, target_pct=70),
           COConfig(number=2, threshold_pct=50, target_pct=80)]
    roster = [StudentInfo(usn="1AT0001", name="Alice", section="A"),
              StudentInfo(usn="1AT0002", name="Bob", section="A")]
    attempts = [
        _make_attempt_score("1AT0001", "q1", "m1", 1, {1: (4.0, 5.0), 2: (4.0, 5.0)}),
        _make_attempt_score("1AT0002", "q1", "m1", 1, {1: (2.0, 5.0), 2: (1.0, 5.0)}),
    ]
    store = _make_store(cos, roster, attempts)

    user = {"user_id": "fac-1", "role": "faculty", "student_id": None, "usn": None}
    args = GetCOAttainmentArgs(subject_id="subj-1")

    result = get_co_attainment(args, user, store)
    assert len(result) == 2
    # Alice: 80% on CO1 (above 60 threshold), 80% on CO2 (above 50)
    # Bob: 40% on CO1 (below 60), 20% on CO2 (below 50)
    co1 = next(r for r in result if r["co_number"] == 1)
    assert co1["enrolled"] == 2
    assert co1["above"] == 1  # only Alice
    assert co1["below"] == 1  # only Bob


def test_get_co_attainment_student_forbidden():
    """Students cannot call get_co_attainment."""
    cos = [COConfig(number=1, threshold_pct=60, target_pct=70)]
    store = _make_store(cos, [], [])
    user = {"user_id": "stu-1", "role": "student", "student_id": "stu-1", "usn": "1AT0999"}
    args = GetCOAttainmentArgs(subject_id="subj-1")
    with pytest.raises(AppError) as exc:
        get_co_attainment(args, user, store)
    assert exc.value.status_code == 403


# ---------------------------------------------------------------------------
# find_weak_COs
# ---------------------------------------------------------------------------

def test_find_weak_cos_faculty():
    """Faculty calling find_weak_COs gets weak COs."""
    cos = [COConfig(number=1, threshold_pct=60, target_pct=80),
           COConfig(number=2, threshold_pct=50, target_pct=90)]
    roster = [StudentInfo(usn="1AT0001", name="Alice", section="A"),
              StudentInfo(usn="1AT0002", name="Bob", section="A")]
    # CO1: both students below threshold → weak (attainment 0%, gap 80%)
    # CO2: both students below threshold → weak (attainment 0%, gap 90%)
    attempts = [
        _make_attempt_score("1AT0001", "q1", "m1", 1, {1: (2.0, 5.0), 2: (1.0, 5.0)}),
        _make_attempt_score("1AT0002", "q1", "m1", 1, {1: (2.0, 5.0), 2: (1.0, 5.0)}),
    ]
    store = _make_store(cos, roster, attempts)
    user = {"user_id": "fac-1", "role": "faculty"}
    args = FindWeakCOsArgs(subject_id="subj-1")

    result = find_weak_COs(args, user, store)
    assert len(result) == 2
    co_numbers = {r["co_number"] for r in result}
    assert co_numbers == {1, 2}


def test_find_weak_cos_student_forbidden():
    """Students cannot call find_weak_COs."""
    store = _make_store([], [], [])
    user = {"user_id": "stu-1", "role": "student", "student_id": "stu-1", "usn": "1AT0999"}
    args = FindWeakCOsArgs(subject_id="subj-1")
    with pytest.raises(AppError) as exc:
        find_weak_COs(args, user, store)
    assert exc.value.status_code == 403


# ---------------------------------------------------------------------------
# get_student_progress
# ---------------------------------------------------------------------------

def test_get_student_progress_student_own():
    """A student can view their own progress."""
    cos = [COConfig(number=1, threshold_pct=60, target_pct=70)]
    roster = [StudentInfo(usn="1AT0001", name="Alice", section="A")]
    attempts = [
        _make_attempt_score("1AT0001", "q1", "m1", 1, {1: (4.0, 5.0)}),
    ]
    store = _make_store(cos, roster, attempts)

    user = {"user_id": "u-1", "role": "student", "student_id": "stu-1", "usn": "1AT0001"}
    args = GetStudentProgressArgs(subject_id="subj-1")

    result = get_student_progress(args, user, store)
    assert result["usn"] == "1AT0001"
    assert result["name"] == "Alice"
    assert len(result["co_scores"]) == 1
    assert result["co_scores"][0]["percentage"] == 80.0
    assert result["co_scores"][0]["attained"] is True


def test_get_student_progress_student_own_explicit_usn():
    """A student passing their own USN gets their data."""
    cos = [COConfig(number=1, threshold_pct=60, target_pct=70)]
    roster = [StudentInfo(usn="1AT0001", name="Alice", section="A")]
    store = _make_store(cos, roster, [])
    user = {"user_id": "u-1", "role": "student", "student_id": "stu-1", "usn": "1AT0001"}
    args = GetStudentProgressArgs(subject_id="subj-1", usn="1AT0001")

    result = get_student_progress(args, user, store)
    assert result["usn"] == "1AT0001"


def test_get_student_progress_student_cannot_read_other():
    """A student passing another student's USN gets a 403 AppError."""
    cos = [COConfig(number=1, threshold_pct=60, target_pct=70)]
    roster = [StudentInfo(usn="1AT0001", name="Alice", section="A"),
              StudentInfo(usn="1AT0002", name="Bob", section="A")]
    store = _make_store(cos, roster, [])
    user = {"user_id": "u-1", "role": "student", "student_id": "stu-1", "usn": "1AT0001"}
    args = GetStudentProgressArgs(subject_id="subj-1", usn="1AT0002")

    with pytest.raises(AppError) as exc:
        get_student_progress(args, user, store)
    assert exc.value.status_code == 403
    assert "own progress" in exc.value.message


def test_get_student_progress_student_usn_case_insensitive():
    """USN comparison is case-insensitive and trimmed."""
    cos = [COConfig(number=1, threshold_pct=60, target_pct=70)]
    roster = [StudentInfo(usn="1AT0001", name="Alice", section="A")]
    store = _make_store(cos, roster, [])
    user = {"user_id": "u-1", "role": "student", "student_id": "stu-1", "usn": "1AT0001"}
    # Lowercase + spaces should still match
    args = GetStudentProgressArgs(subject_id="subj-1", usn="  1at0001  ")

    result = get_student_progress(args, user, store)
    assert result["usn"] == "1AT0001"


def test_get_student_progress_faculty_can_read_any():
    """A faculty member can look up any student by USN."""
    cos = [COConfig(number=1, threshold_pct=60, target_pct=70)]
    roster = [StudentInfo(usn="1AT0001", name="Alice", section="A"),
              StudentInfo(usn="1AT0002", name="Bob", section="A")]
    store = _make_store(cos, roster, [])
    user = {"user_id": "fac-1", "role": "faculty"}
    args = GetStudentProgressArgs(subject_id="subj-1", usn="1AT0002")

    result = get_student_progress(args, user, store)
    assert result["usn"] == "1AT0002"
    assert result["name"] == "Bob"


def test_get_student_progress_faculty_missing_usn():
    """Faculty without a USN gets a 400."""
    cos = [COConfig(number=1, threshold_pct=60, target_pct=70)]
    store = _make_store(cos, [], [])
    user = {"user_id": "fac-1", "role": "faculty"}
    args = GetStudentProgressArgs(subject_id="subj-1")
    with pytest.raises(AppError) as exc:
        get_student_progress(args, user, store)
    assert exc.value.status_code == 400


# ---------------------------------------------------------------------------
# export_sheet
# ---------------------------------------------------------------------------

def test_export_sheet_faculty():
    """Faculty calling export_sheet gets Excel bytes."""
    cos = [COConfig(number=1, threshold_pct=60, target_pct=70)]
    roster = [StudentInfo(usn="1AT0001", name="Alice", section="A")]
    attempts = [_make_attempt_score("1AT0001", "q1", "m1", 1, {1: (4.0, 5.0)})]
    store = _make_store(cos, roster, attempts)
    user = {"user_id": "fac-1", "role": "faculty"}
    args = ExportSheetArgs(subject_id="subj-1")

    result = export_sheet(args, user, store)
    assert isinstance(result, bytes)
    assert len(result) > 0


def test_export_sheet_student_forbidden():
    """Students cannot call export_sheet."""
    store = _make_store([], [], [])
    user = {"user_id": "stu-1", "role": "student"}
    args = ExportSheetArgs(subject_id="subj-1")
    with pytest.raises(AppError) as exc:
        export_sheet(args, user, store)
    assert exc.value.status_code == 403


# ---------------------------------------------------------------------------
# generate_quiz
# ---------------------------------------------------------------------------

def test_generate_quiz_faculty_creates_drafts(db, ctx, fake_ai):
    """Faculty can generate quiz questions; they are saved as drafts."""
    faculty = ctx.make_faculty()
    subj = ctx.make_subject(faculty["user_id"])
    co = ctx.make_co(subj["subject_id"], 1, "CO1")
    mod = ctx.make_module(subj["subject_id"], 1, "Module 1")

    user = {"user_id": faculty["user_id"], "role": "faculty"}
    args = GenerateQuizArgs(module_id=mod["module_id"], co_id=co["co_id"],
                            difficulty="medium", count=3)

    created_ids = generate_quiz(args, user, db)
    assert len(created_ids) == 3

    # Verify each question is a draft with source='AI'
    for qid in created_ids:
        row = db.execute(
            text("SELECT status, source FROM questions WHERE id = :id"),
            {"id": qid},
        ).mappings().fetchone()
        assert row["status"] == "draft"
        assert row["source"] == "AI"


def test_generate_quiz_student_forbidden(db, ctx):
    """Students cannot call generate_quiz."""
    user = {"user_id": "stu-1", "role": "student", "student_id": "stu-1", "usn": "1STU001"}
    import uuid as _uuid
    args = GenerateQuizArgs(module_id=str(_uuid.uuid4()), co_id=str(_uuid.uuid4()), count=2)
    with pytest.raises(AppError) as exc:
        generate_quiz(args, user, db)
    assert exc.value.status_code == 403


def test_generate_quiz_validates_count():
    """Pydantic validation: count must be >= 1."""
    with pytest.raises(ValueError):
        GenerateQuizArgs(module_id="m1", co_id="c1", count=0)


def test_generate_quiz_validates_difficulty():
    """Pydantic validation: difficulty must be easy/medium/hard."""
    with pytest.raises(ValueError):
        GenerateQuizArgs(module_id="m1", co_id="c1", count=3, difficulty="insane")


def test_generate_quiz_invalid_module(db, ctx, fake_ai):
    """Faculty providing a non-owned module gets 404."""
    import uuid as _uuid
    faculty = ctx.make_faculty()
    user = {"user_id": faculty["user_id"], "role": "faculty"}
    args = GenerateQuizArgs(module_id=str(_uuid.uuid4()), co_id=str(_uuid.uuid4()), count=2)
    with pytest.raises(AppError) as exc:
        generate_quiz(args, user, db)
    assert exc.value.status_code == 404


def test_generate_quiz_module_not_owned(db, ctx, fake_ai):
    """Faculty cannot generate questions for a module they don't own."""
    faculty_a = ctx.make_faculty()
    faculty_b = ctx.make_faculty()
    subj_a = ctx.make_subject(faculty_a["user_id"])
    mod_a = ctx.make_module(subj_a["subject_id"], 1, "Owned Module")
    co_a = ctx.make_co(subj_a["subject_id"], 1, "Owned CO")

    # Faculty B tries to generate for Faculty A's module
    user_b = {"user_id": faculty_b["user_id"], "role": "faculty"}
    args = GenerateQuizArgs(module_id=mod_a["module_id"], co_id=co_a["co_id"], count=2)
    with pytest.raises(AppError) as exc:
        generate_quiz(args, user_b, db)
    assert exc.value.status_code == 404


def test_generate_quiz_saves_question_with_correct_fields(db, ctx, fake_ai):
    """Generated questions have all expected fields set."""
    faculty = ctx.make_faculty()
    subj = ctx.make_subject(faculty["user_id"])
    co = ctx.make_co(subj["subject_id"], 1, "CO1")
    mod = ctx.make_module(subj["subject_id"], 1, "Module 1")

    user = {"user_id": faculty["user_id"], "role": "faculty"}
    args = GenerateQuizArgs(module_id=mod["module_id"], co_id=co["co_id"],
                            difficulty="easy", count=2)

    created_ids = generate_quiz(args, user, db)
    assert len(created_ids) == 2

    for qid in created_ids:
        row = db.execute(
            text("SELECT stem, options, correct_option, marks, difficulty, "
                 "bloom_level, status, source, module_id, co_id, created_by "
                 "FROM questions WHERE id = :id"),
            {"id": qid},
        ).mappings().fetchone()
        assert row["status"] == "draft"
        assert row["source"] == "AI"
        assert str(row["module_id"]) == mod["module_id"]
        assert str(row["co_id"]) == co["co_id"]
        assert str(row["created_by"]) == faculty["user_id"]
        opts = row["options"]
        assert isinstance(opts, (list, dict)) or hasattr(opts, "__iter__")


def test_generate_quiz_status_always_draft(db, ctx, monkeypatch):
    """Even if the AI function returns status='approved', the DB row is draft."""
    faculty = ctx.make_faculty()
    subj = ctx.make_subject(faculty["user_id"])
    co = ctx.make_co(subj["subject_id"], 1, "CO1")
    mod = ctx.make_module(subj["subject_id"], 1, "Module 1")

    # Set env vars
    monkeypatch.setenv("TOKEN_FACTORY_API_KEY", "test-key")
    monkeypatch.setenv("TOKEN_FACTORY_BASE_URL", "https://test.token.factory")
    monkeypatch.setenv("MODEL_GENERATION", "test-model")

    class FakeClient:
        def __init__(self, **kwargs):
            pass
        def close(self):
            pass

    def fake_with_approved_status(module, co, difficulty, count, client,
                                  *, model, usage_recorder=None):
        return [
            {
                "stem": "Try to approve me",
                "options": ["A", "B", "C", "D"],
                "correct_option": 0,
                "explanation": None,
                "marks": 1.0,
                "difficulty": "medium",
                "bloom_level": "remember",
                "status": "approved",  # AI tries to override
                "source": "faculty",   # AI tries to override
            }
            for _ in range(count)
        ]

    import backend.app.agent_tools as at
    monkeypatch.setattr(at, "_ai_generate_quiz", fake_with_approved_status)
    monkeypatch.setattr(at, "TokenFactoryClient", FakeClient)

    user = {"user_id": faculty["user_id"], "role": "faculty"}
    args = GenerateQuizArgs(module_id=mod["module_id"], co_id=co["co_id"],
                            difficulty="medium", count=2)
    created_ids = generate_quiz(args, user, db)

    for qid in created_ids:
        row = db.execute(
            text("SELECT status, source FROM questions WHERE id = :id"),
            {"id": qid},
        ).mappings().fetchone()
        assert row["status"] == "draft"
        assert row["source"] == "AI"


def test_generate_quiz_quiz_generation_error(db, ctx, fake_ai_failure):
    """QuizGenerationError from the AI function is mapped to a clean AppError."""
    faculty = ctx.make_faculty()
    subj = ctx.make_subject(faculty["user_id"])
    co = ctx.make_co(subj["subject_id"], 1, "CO1")
    mod = ctx.make_module(subj["subject_id"], 1, "Module 1")

    user = {"user_id": faculty["user_id"], "role": "faculty"}
    args = GenerateQuizArgs(module_id=mod["module_id"], co_id=co["co_id"], count=2)
    with pytest.raises(AppError) as exc:
        generate_quiz(args, user, db)
    assert exc.value.status_code in (500, 502)


def test_generate_quiz_missing_env_var(db, ctx, monkeypatch):
    """Missing TOKEN_FACTORY_API_KEY raises a clean AppError, not a stack trace."""
    faculty = ctx.make_faculty()
    subj = ctx.make_subject(faculty["user_id"])
    co = ctx.make_co(subj["subject_id"], 1, "CO1")
    mod = ctx.make_module(subj["subject_id"], 1, "Module 1")

    # Env vars are NOT set (monkeypatch doesn't set them)
    monkeypatch.delenv("TOKEN_FACTORY_API_KEY", raising=False)
    monkeypatch.delenv("TOKEN_FACTORY_BASE_URL", raising=False)
    monkeypatch.delenv("MODEL_GENERATION", raising=False)

    user = {"user_id": faculty["user_id"], "role": "faculty"}
    args = GenerateQuizArgs(module_id=mod["module_id"], co_id=co["co_id"], count=2)
    with pytest.raises(AppError) as exc:
        generate_quiz(args, user, db)
    assert exc.value.status_code == 500
    assert "not configured" in exc.value.message.lower()
