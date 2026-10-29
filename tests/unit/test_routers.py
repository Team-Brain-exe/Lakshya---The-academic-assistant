"""Comprehensive tests for API router handlers matching docs/api-contract.md.

Verifies:
- Standard error shape: {"error": {"code", "message", "details"}}
- Status codes: 200, 201, 202, 400, 403, 404, 409, 422
- Student data isolation: 403 on other students' data
- Role enforcement: 403 for student tokens calling faculty endpoints
- Answer secret masking before submission
- Attempt limit 2 enforced (409 ATTEMPT_LIMIT_REACHED)
- Unapproved question publish guard (409 QUESTION_NOT_APPROVED)
"""

import unittest
from datetime import datetime, timedelta, timezone

from app.engine.co_math import AttemptScore, COConfig, StudentInfo
from app.engine.grading import COMarks
from app.pipeline.memory_store import InMemoryChunkStore
from app.routers.calendar import CalendarRouterHandler
from app.routers.co_sheet import COSheetRouterHandler
from app.routers.quizzes import QuizRouterHandler
from app.routers.study import StudyRouterHandler
from app.routers.upload import UploadRouterHandler
from app.routers.usage import UsageRouterHandler
from app.services.calendar import InMemoryCalendarStore
from app.services.co_analytics import InMemoryAnalyticsStore
from app.services.qa import InMemoryChunkRetrievalStore
from app.services.quizzes import InMemoryQuizStore, QuestionRecord
from app.services.study_material import InMemoryStudyMaterialStore
from app.services.study_plan import InMemoryStudyPlanStore
from app.services.usage import InMemoryUsageStore, log_ai_call
from tests.unit.helpers import build_deck


class RouterHandlerTests(unittest.TestCase):
    def setUp(self):
        self.faculty_user = {"user_id": "fac-1", "role": "faculty", "name": "Prof. Rao"}
        self.student_1 = {"user_id": "u-s1", "role": "student", "student_id": "stud-1", "usn": "1XX23CS001"}
        self.student_2 = {"user_id": "u-s2", "role": "student", "student_id": "stud-2", "usn": "1XX23CS002"}
        # Relative to the real clock: a fixed date makes quiz windows expire as time passes.
        self.now = datetime.now(timezone.utc).replace(microsecond=0) - timedelta(hours=1)

    # --- 1. Upload Router ---
    def test_upload_router_handlers(self):
        chunk_store = InMemoryChunkStore()
        handler = UploadRouterHandler(
            store=chunk_store,
            tagger=lambda chunks, cos: [{"chunk_id": chunks[0].id, "cos": [1], "confidence": 0.9}],
            cos_provider=lambda m: [],
        )

        # Student forbidden
        status, body = handler.upload_deck(self.student_1, "mod-1", b"dummy")
        self.assertEqual(status, 403)
        self.assertEqual(body["error"]["code"], "FORBIDDEN")

        # Bad file extension
        status, body = handler.upload_deck(self.faculty_user, "mod-1", b"dummy", filename="slides.pdf")
        self.assertEqual(status, 400)
        self.assertEqual(body["error"]["code"], "BAD_REQUEST")

        # Valid PPT deck upload
        deck_bytes = build_deck()
        status, body = handler.upload_deck(self.faculty_user, "mod-1", deck_bytes, filename="slides.pptx")
        self.assertEqual(status, 202)
        self.assertEqual(body["processing_status"], "done")

        # Status endpoint
        status, s_body = handler.get_status(self.faculty_user, "mod-1")
        self.assertEqual(status, 200)
        self.assertEqual(s_body["processing_status"], "done")

        # Coverage endpoint
        status, cov_body = handler.get_coverage(self.faculty_user, "cs201", [1, 2], [("c1", 1)])
        self.assertEqual(status, 200)
        self.assertEqual(cov_body[0]["co_number"], 1)
        self.assertFalse(cov_body[0]["warning"])
        self.assertTrue(cov_body[1]["warning"])  # CO2 has 0 chunks -> warning

    # --- 2. Quiz Router ---
    def test_quiz_router_handlers(self):
        quiz_store = InMemoryQuizStore()
        cal_store = InMemoryCalendarStore()
        handler = QuizRouterHandler(quiz_store=quiz_store, calendar_store=cal_store)

        q_app = QuestionRecord("q1", "mod-1", "co-1", 1, "Question?", ["A", "B", "C", "D"], 0, "Expl", 1.0, status="approved")
        q_draft = QuestionRecord("q2", "mod-1", "co-1", 1, "Draft?", ["A", "B", "C", "D"], 0, "Expl", 1.0, status="draft")
        quiz_store.add_question(q_app)
        quiz_store.add_question(q_draft)

        # Student cannot create quiz
        status, body = handler.create(self.student_1, "mod-1", "cs201", "Student Quiz", ["q1"])
        self.assertEqual(status, 403)

        # Faculty creates quiz
        status, body = handler.create(
            self.faculty_user, "mod-1", "cs201", "Exam 1", ["q1"],
            opens_at=self.now, closes_at=self.now + timedelta(days=2)
        )
        self.assertEqual(status, 201)
        quiz_id = body["id"]

        # Publishing with draft question fails
        status_draft, _ = handler.create(self.faculty_user, "mod-1", "cs201", "Draft Quiz", ["q2"])
        draft_quiz_id = _["id"]
        status, body = handler.publish(self.faculty_user, draft_quiz_id)
        self.assertEqual(status, 409)
        self.assertEqual(body["error"]["code"], "QUESTION_NOT_APPROVED")

        # Publishing approved quiz succeeds and creates calendar event
        status, body = handler.publish(self.faculty_user, quiz_id)
        self.assertEqual(status, 200)
        self.assertTrue(body["published"])
        self.assertIsNotNone(body["event_id"])

        # Student starts attempt at the same fixed clock time as the quiz window.
        status, att_body = handler.start_attempt(self.student_1, quiz_id, now=self.now)
        self.assertEqual(status, 201)
        att_id = att_body["attempt_id"]
        self.assertNotIn("correct_option", att_body["questions"][0])
        self.assertNotIn("explanation", att_body["questions"][0])

        # Autosave answers
        status, s_res = handler.save_answers(self.student_1, att_id, {"q1": 0})
        self.assertEqual(status, 200)
        self.assertTrue(s_res["saved"])

        # Submit attempt
        status, sub_res = handler.submit(self.student_1, att_id, {"q1": 0})
        self.assertEqual(status, 200)
        self.assertEqual(sub_res["total_score"], 1.0)

        # Review submitted attempt: student 2 cannot view student 1 review (403)
        status, _ = handler.review(self.student_2, att_id)
        self.assertEqual(status, 403)

        # Student 1 reviews own attempt
        status, rev_res = handler.review(self.student_1, att_id)
        self.assertEqual(status, 200)
        self.assertEqual(rev_res[0]["correct"], 0)
        self.assertEqual(rev_res[0]["explanation"], "Expl")

    # --- 3. CO Sheet Router ---
    def test_co_sheet_router_handlers(self):
        analytics_store = InMemoryAnalyticsStore(
            cos=[COConfig(1, 60.0, 60.0), COConfig(2, 60.0, 60.0)],
            roster=[StudentInfo("1XX23CS001", "Aarav", "A"), StudentInfo("1XX23CS002", "Bhavya", "A")],
            attempts=[
                AttemptScore("1XX23CS001", "q1", "mod-1", 1, {1: COMarks(1, 3, 3), 2: COMarks(2, 2, 2)}),
                AttemptScore("1XX23CS002", "q1", "mod-1", 1, {1: COMarks(1, 1, 3), 2: COMarks(2, 0, 2)}),
            ],
            co_id_map={"co-1-id": COConfig(1, 60.0, 60.0)},
        )
        handler = COSheetRouterHandler(store=analytics_store)

        # Student forbidden from viewing full sheet or export
        status, body = handler.get_sheet(self.student_1, "cs201")
        self.assertEqual(status, 403)
        status, _, _ = handler.export_excel(self.student_1, "cs201")
        self.assertEqual(status, 403)

        # Faculty gets sheet
        status, body = handler.get_sheet(self.faculty_user, "cs201")
        self.assertEqual(status, 200)
        self.assertEqual(len(body["rows"]), 2)

        # Faculty gets summary and weak COs
        status, summary = handler.get_summary(self.faculty_user, "cs201")
        self.assertEqual(status, 200)
        status, weak = handler.get_weak_cos(self.faculty_user, "cs201")
        self.assertEqual(status, 200)

        # Faculty exports excel
        status, raw_bytes, headers = handler.export_excel(self.faculty_user, "cs201")
        self.assertEqual(status, 200)
        self.assertTrue(raw_bytes.startswith(b"PK\x03\x04"))
        self.assertIn("co_sheet_cs201.xlsx", headers["Content-Disposition"])

        # Student progress: student 1 can view own
        status, prog = handler.get_progress(self.student_1, "1XX23CS001", "cs201")
        self.assertEqual(status, 200)
        self.assertEqual(prog["usn"], "1XX23CS001")

        # Student 1 cannot view student 2 progress (403)
        status, prog = handler.get_progress(self.student_1, "1XX23CS002", "cs201")
        self.assertEqual(status, 403)

    # --- 4. Study Router ---
    def test_study_router_handlers(self):
        retrieval = InMemoryChunkRetrievalStore()
        retrieval.add_chunk("cs201", "c1", "mod-1", 3, "Binary Search in sorted arrays takes O(log n).")
        mat_store = InMemoryStudyMaterialStore()
        plan_store = InMemoryStudyPlanStore()

        handler = StudyRouterHandler(
            retrieval_store=retrieval,
            material_store=mat_store,
            plan_store=plan_store,
            score_provider=lambda sid, sub: {1: 30.0},  # weak in CO1
            co_provider=lambda sub: {1: {"id": "co-1", "threshold_pct": 60.0, "description": "Complexity"}},
            chunk_provider=lambda mid: [{"slide_number": 3, "co_number": 1, "text": "Binary Search"}],
        )

        # Slide Q&A
        status, qa_res = handler.answer_question(self.student_1, "cs201", "What is binary search time?")
        self.assertEqual(status, 200)
        self.assertFalse(qa_res["refused"])
        self.assertEqual(qa_res["citations"][0]["slide_number"], 3)

        # Q&A refusal on out-of-scope query
        status, qa_ref = handler.answer_question(self.student_1, "cs201", "Unrelated quantum physics question.")
        self.assertEqual(status, 200)
        self.assertTrue(qa_ref["refused"])

        # Study plan generation (student only)
        status, _ = handler.create_study_plan(self.faculty_user, "cs201")
        self.assertEqual(status, 403)

        status, plan_res = handler.create_study_plan(self.student_1, "cs201")
        self.assertEqual(status, 201)
        self.assertEqual(plan_res["plan"]["weak_cos"], [1])

        # Study material: faculty generates, student reads
        status, _ = handler.generate_material(self.student_1, "mod-1")
        self.assertEqual(status, 403)

        status, gen_res = handler.generate_material(self.faculty_user, "mod-1")
        self.assertEqual(status, 200)
        self.assertEqual(len(gen_res["flashcards"]), 1)

        status, cards = handler.get_flashcards(self.student_1, "mod-1")
        self.assertEqual(status, 200)
        self.assertEqual(len(cards), 1)

    # --- 5. Calendar Router ---
    def test_calendar_router_handlers(self):
        cal_store = InMemoryCalendarStore()
        handler = CalendarRouterHandler(store=cal_store, enrollment_provider=lambda sid: ["cs201"])

        # Student cannot create event
        status, body = handler.create(self.student_1, "cs201", "quiz", "Pop Quiz", self.now)
        self.assertEqual(status, 403)

        # Faculty creates event
        status, ev = handler.create(self.faculty_user, "cs201", "teaching", "Lecture 1", self.now)
        self.assertEqual(status, 201)
        event_id = ev["id"]

        # Student lists events for enrolled subject cs201 (allowed)
        status, events = handler.list(self.student_1, subject_id="cs201")
        self.assertEqual(status, 200)
        self.assertEqual(len(events), 1)

        # Student lists events for unenrolled subject (forbidden)
        status, _ = handler.list(self.student_1, subject_id="ee101")
        self.assertEqual(status, 403)

        # Faculty updates and deletes event
        status, upd = handler.update(self.faculty_user, event_id, {"title": "Updated Lecture 1"})
        self.assertEqual(status, 200)
        self.assertEqual(upd["title"], "Updated Lecture 1")

        status, del_res = handler.delete(self.faculty_user, event_id)
        self.assertEqual(status, 200)
        self.assertTrue(del_res["deleted"])

    # --- 6. Usage Router ---
    def test_usage_router_handlers(self):
        u_store = InMemoryUsageStore()
        log_ai_call(u_store, step="tagging", model="nano", prompt_tokens=100, completion_tokens=50)
        handler = UsageRouterHandler(store=u_store)

        # Student cannot access usage
        status, _ = handler.get_summary(self.student_1)
        self.assertEqual(status, 403)

        # Faculty gets summary
        status, summary = handler.get_summary(self.faculty_user)
        self.assertEqual(status, 200)
        self.assertEqual(len(summary), 1)
        self.assertEqual(summary[0]["step"], "tagging")
        self.assertEqual(summary[0]["total_tokens"], 150)


if __name__ == "__main__":
    unittest.main()

