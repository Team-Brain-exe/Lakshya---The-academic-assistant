"""Unit tests for CO sheet, class summary, weak-CO flags, drill-down, and student progress."""

import unittest

from app.engine.co_math import AttemptScore, COConfig, StudentInfo
from app.engine.grading import COMarks, QuestionResult
from app.services.co_analytics import (
    ForbiddenError,
    InMemoryAnalyticsStore,
    NotFoundError,
    export_co_sheet_excel,
    get_class_summary_data,
    get_co_drilldown_data,
    get_co_sheet_data,
    get_student_progress_data,
    get_weak_cos_data,
)


class COAnalyticsServiceTests(unittest.TestCase):
    def setUp(self):
        self.subject_id = "cs201"
        self.cos = [
            COConfig(number=1, threshold_pct=60.0, target_pct=60.0),
            COConfig(number=2, threshold_pct=60.0, target_pct=60.0),
            COConfig(number=3, threshold_pct=60.0, target_pct=60.0),
        ]
        self.roster = [
            StudentInfo(usn="1XX23CS001", name="Aarav Sharma", section="A"),
            StudentInfo(usn="1XX23CS002", name="Bhavya Reddy", section="A"),
            StudentInfo(usn="1XX23CS031", name="Chetan Patel", section="B"),
        ]

        # Attempts: Aarav does well across CO1, CO2, CO3; Chetan fails CO3 (weak student)
        # S1 (Aarav): CO1 (3/3), CO2 (2/2), CO3 (3/3)
        # S2 (Bhavya): CO1 (2/3), CO2 (1/2), CO3 (2/3)
        # S3 (Chetan): CO1 (2/3), CO2 (1/2), CO3 (0/3) -> weak in CO3!
        q_results = (
            QuestionResult("q1", co=3, chosen=0, correct_option=1, is_correct=False, marks_awarded=0, marks_max=1),
            QuestionResult("q2", co=3, chosen=1, correct_option=1, is_correct=True, marks_awarded=1, marks_max=1),
        )
        self.attempts = [
            AttemptScore(
                usn="1XX23CS001",
                quiz_id="q-1",
                module_id="mod-1",
                attempt_number=1,
                per_co={1: COMarks(1, 3, 3), 2: COMarks(2, 2, 2), 3: COMarks(3, 3, 3)},
                questions=q_results,
            ),
            AttemptScore(
                usn="1XX23CS002",
                quiz_id="q-1",
                module_id="mod-1",
                attempt_number=1,
                per_co={1: COMarks(1, 2, 3), 2: COMarks(2, 1, 2), 3: COMarks(3, 2, 3)},
                questions=q_results,
            ),
            AttemptScore(
                usn="1XX23CS031",
                quiz_id="q-1",
                module_id="mod-1",
                attempt_number=1,
                per_co={1: COMarks(1, 2, 3), 2: COMarks(2, 1, 2), 3: COMarks(3, 0, 3)},
                questions=q_results,
            ),
        ]

        self.store = InMemoryAnalyticsStore(
            cos=self.cos,
            roster=self.roster,
            attempts=self.attempts,
            co_id_map={"co-3-id": self.cos[2]},
        )

        self.faculty_user = {"user_id": "fac-1", "role": "faculty"}
        self.student_1 = {"user_id": "u-1", "role": "student", "usn": "1XX23CS001"}
        self.student_2 = {"user_id": "u-2", "role": "student", "usn": "1XX23CS002"}

    def test_get_co_sheet_data(self):
        sheet = get_co_sheet_data(self.store, self.subject_id)
        self.assertEqual(sheet["columns"], ["CO1", "CO2", "CO3"])
        self.assertEqual(len(sheet["rows"]), 3)
        self.assertEqual(sheet["rows"][0]["usn"], "1XX23CS001")
        self.assertEqual(sheet["rows"][0]["co_scores"]["CO1"], 100.0)

    def test_get_class_summary_data(self):
        summary = get_class_summary_data(self.store, self.subject_id)
        self.assertEqual(len(summary), 3)
        # CO1: Aarav (100%), Bhavya (66.7%), Chetan (66.7%) -> all 3 >= 60% threshold -> attainment 100%
        co1 = next(s for s in summary if s["co_number"] == 1)
        self.assertEqual(co1["above"], 3)
        self.assertTrue(co1["target_met"])

        # CO3: Aarav (100%), Bhavya (66.7%), Chetan (0%) -> 2 of 3 >= 60% -> 66.7% attainment -> target met
        co3 = next(s for s in summary if s["co_number"] == 3)
        self.assertEqual(co3["above"], 2)
        self.assertEqual(co3["below"], 1)

    def test_get_weak_cos_data(self):
        # Let's adjust CO3 target to 70% so 66.7% falls below target
        co3_high_target = [
            self.cos[0],
            self.cos[1],
            COConfig(number=3, threshold_pct=60.0, target_pct=75.0),
        ]
        store = InMemoryAnalyticsStore(
            cos=co3_high_target,
            roster=self.roster,
            attempts=self.attempts,
        )
        weak = get_weak_cos_data(store, self.subject_id)
        # CO2 (33.3% attainment) and CO3 (66.7% attainment) are both below their targets
        self.assertEqual(len(weak), 2)
        weak_cos_nums = [w["co_number"] for w in weak]
        self.assertIn(2, weak_cos_nums)
        self.assertIn(3, weak_cos_nums)
        self.assertGreater(weak[0]["gap"], 0)

    def test_get_co_drilldown_data(self):
        dd = get_co_drilldown_data(self.store, self.subject_id, "co-3-id")
        self.assertEqual(dd["co_number"], 3)
        self.assertEqual(len(dd["modules"]), 1)
        self.assertEqual(len(dd["students"]), 3)
        # Students sorted weakest first: Chetan (0%) first
        self.assertEqual(dd["students"][0]["usn"], "1XX23CS031")
        self.assertEqual(dd["students"][0]["percentage"], 0.0)

    def test_export_co_sheet_excel(self):
        xlsx_bytes = export_co_sheet_excel(self.store, self.subject_id)
        self.assertIsInstance(xlsx_bytes, bytes)
        # Standard ZIP magic header for .xlsx
        self.assertTrue(xlsx_bytes.startswith(b"PK\x03\x04"))

    def test_get_student_progress_data_and_isolation(self):
        # Student 1 requesting own progress -> Allowed
        prog = get_student_progress_data(self.store, self.student_1, "1XX23CS001", self.subject_id)
        self.assertEqual(prog["usn"], "1XX23CS001")
        self.assertEqual(len(prog["co_scores"]), 3)

        # Student 1 requesting Student 2's progress -> 403 ForbiddenError
        with self.assertRaises(ForbiddenError):
            get_student_progress_data(self.store, self.student_1, "1XX23CS002", self.subject_id)

        # Faculty requesting Student 2's progress -> Allowed
        fac_prog = get_student_progress_data(self.store, self.faculty_user, "1XX23CS002", self.subject_id)
        self.assertEqual(fac_prog["usn"], "1XX23CS002")


if __name__ == "__main__":
    unittest.main()
