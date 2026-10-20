# Arya, part 1: the engine (grading, CO sheet, export, PPT pipeline)

Everything in part 1 is plain Python with no web framework, no database and no network calls, so it runs and is tested without anyone else's work. Part 2 connects it to Aparna's database and Danwin's AI client.

## What is in part 1

| Your task | Code | Tests |
| --- | --- | --- |
| 4. Grading and CO marks | `backend/app/engine/grading.py`, `settings.py` | `test_grading.py`, `test_settings.py` |
| 6. CO sheet, class summary, weak-CO flag, drill-down (the logic) | `backend/app/engine/co_math.py` | `test_co_math.py` |
| 7. Excel export | `backend/app/export/sheet_xlsx.py` | `test_export.py` |
| 3. PPT parsing, chunks, upload pipeline, coverage | `backend/app/pipeline/ppt.py`, `upload.py`, `coverage.py`, `memory_store.py` | `test_pipeline.py`, `test_ppt.py` |

The HTTP endpoints for tasks 3, 5 and 6 are part 2, because they need Aparna's auth and schema.

## Run the tests

```bash
pip install -r backend/requirements.txt
pytest
```

110 tests. They include the hand-calculated CO sheet, the "change one answer and the sheet updates" test, and the drill-down agreeing with the sheet.

## How to call it

```python
from app.engine.grading import QuestionKey, grade_attempt
from app.engine.co_math import (
    AttemptScore, COConfig, StudentInfo,
    select_counted, build_co_sheet, class_summary, weak_cos, co_drilldown,
)
from app.engine.settings import load_grading_settings
from app.export.sheet_xlsx import build_sheet_workbook

quiz = [QuestionKey("q1", co=1, correct_option=0), QuestionKey("q2", co=2, correct_option=1)]
grade = grade_attempt(quiz, {"q1": 0, "q2": 3})          # one attempt, graded in code

attempts = [AttemptScore.from_grade("1XX23CS001", "quiz-1", "module-1", 1, grade)]
counted = select_counted(attempts, load_grading_settings().attempt_rule)

cos = [COConfig(1, threshold_pct=60, target_pct=60), COConfig(2, 60, 60)]
roster = [StudentInfo("1XX23CS001", "Asha")]

sheet = build_co_sheet(counted, roster, cos)              # module_id=... or section=... to filter
summary = class_summary(sheet, cos)
weak = weak_cos(summary)                                  # what find_weak_COs returns
detail = co_drilldown(counted, roster, cos[1])            # modules, questions, students behind CO2

xlsx_bytes = build_sheet_workbook(sheet, {c.number: c.threshold_pct for c in cos}, summary)
```

For the upload pipeline:

```python
from app.pipeline.upload import process_module_upload, COInfo
report = process_module_upload(module_id, uploaded_file, [COInfo(1, "..."), ...], tagger, store)
```

## What the other two need to match

**Aparna (database).** `process_module_upload` calls a `store` with four methods: `set_module_status`, `save_chunks`, `save_tags`, `mark_untagged`. The exact signatures are the `ChunkStore` protocol in `upload.py`, and `memory_store.py` is a working example. Her real store implements the same four methods.

The sheet is built from `AttemptScore` objects, one per stored attempt. They come from `QuizAttempt` rows plus the questions' `co_id`, `correct_option` and `marks`.

**Danwin (AI).** The `tagger` is a function `(chunks, cos) -> list of results`. Each result is `{"chunk_id": str, "cos": [1, 3], "confidence": 0.0 to 1.0}`. Numbers, `"3"` and `"CO3"` are all accepted for a CO, and anything unusable leaves that chunk untagged instead of failing the upload. The token usage that Danwin returns per call is not read here yet. That is part 2 (usage logging).

## Rules the code enforces

- Every question has one CO. Blank answers score 0 but still count toward the maximum.
- A CO with no questions is blank ("no data"), never 0, and is left out of averages.
- Attempt rule comes from `ATTEMPT_RULE` (`best`, `latest`, `average`), default `best`. Maximum attempts is `MAX_ATTEMPTS`, default 2.
- A tagging failure never fails an upload. A file that is not a `.pptx`, or has no text, fails cleanly with a message and nothing is raised.
- Text that looks like a formula (`=1+1`) in a USN or name stays text in the Excel file.

The assumptions behind the numbers are listed in `docs/decisions.md`, item 7.

## Part 2 (waits on Aparna's schema and Danwin's client)

| Task | Needs |
| --- | --- |
| 5. Quiz publish and attempt endpoints (max 2 attempts, publish refuses unapproved questions) | Schema, auth, question endpoints |
| 3 and 6. HTTP endpoints: upload, status, coverage, sheet, summary, drill-down, weak COs, export | Schema, auth, DB library choice |
| 8. Slide-grounded Q&A | Retrieval decision, Danwin's client |
| 9. Study plan | Danwin's client, schema (`StudyPlan`) |
| 10. Flashcards and notes | Danwin's client, schema |
| 11. Calendar backend and tools | Schema, auth |
| 12. Usage logging | Danwin returning token counts |
| 2. Seed data | Schema, Danwin's approved quizzes |
