"""Unit tests for synthetic seed data generator."""

import unittest

from app.engine.co_math import (
    AttemptScore,
    COConfig,
    StudentInfo,
    build_co_sheet,
    class_summary,
    select_counted,
    weak_cos,
)
from app.engine.grading import COMarks
from seed.seed_data import generate_seed_data, generate_sql


class SeedDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = generate_seed_data()

    def test_course_structure(self):
        self.assertEqual(self.data.subject["code"], "CS201")
        self.assertEqual(len(self.data.cos), 6)
        self.assertEqual(len(self.data.modules), 4)
        for i, co in enumerate(self.data.cos, start=1):
            self.assertEqual(co["number"], i)
            self.assertEqual(co["threshold_pct"], 60.0)
            self.assertEqual(co["target_attainment_pct"], 60.0)

    def test_synthetic_students_count_and_usn_normalization(self):
        self.assertEqual(len(self.data.students), 60)
        self.assertEqual(len(self.data.users), 60)  # 60 student users
        self.assertEqual(len(self.data.enrollments), 60)

        usns = [s["usn"] for s in self.data.students]
        self.assertEqual(len(set(usns)), 60)
        for i, usn in enumerate(sorted(usns), start=1):
            expected = f"1XX23CS{i:03d}"
            self.assertEqual(usn, expected)
            self.assertEqual(usn, usn.strip().upper())

        # Section split
        section_a = [e for e in self.data.enrollments if e["section"] == "A"]
        section_b = [e for e in self.data.enrollments if e["section"] == "B"]
        self.assertEqual(len(section_a), 30)
        self.assertEqual(len(section_b), 30)

    def test_approved_quizzes_and_questions(self):
        self.assertEqual(len(self.data.quizzes), 2)
        for qz in self.data.quizzes:
            self.assertTrue(qz["published"])

        # 10 questions total (5 per quiz)
        self.assertEqual(len(self.data.questions), 10)
        for q in self.data.questions:
            self.assertEqual(q["status"], "approved")
            self.assertEqual(len(q["options"]), 4)
            self.assertIn(q["correct_option"], (0, 1, 2, 3))
            self.assertGreater(q["marks"], 0)
            self.assertTrue(q["explanation"])

    def test_attempts_and_weak_co3_flagging(self):
        """Feeding seed scores into the CO engine must flag CO3 as weak."""
        roster = [
            StudentInfo(usn=s["usn"], name=s["name"], section=e["section"])
            for s, e in zip(self.data.students, self.data.enrollments)
        ]
        cos = [
            COConfig(number=c["number"], threshold_pct=c["threshold_pct"], target_pct=c["target_attainment_pct"])
            for c in self.data.cos
        ]

        # Reconstruct AttemptScore objects from seed student_co_scores
        # Group by (usn, quiz_id, attempt_number)
        attempts_map: dict[str, dict[str, Any]] = {}
        for qa in self.data.quiz_attempts:
            attempts_map[qa["id"]] = {
                "usn": next(s["usn"] for s in self.data.students if s["id"] == qa["student_id"]),
                "quiz_id": qa["quiz_id"],
                "module_id": next(q["module_id"] for q in self.data.quizzes if q["id"] == qa["quiz_id"]),
                "attempt_number": qa["attempt_number"],
                "marks_by_co": {},
            }

        co_number_by_id = {c["id"]: c["number"] for c in self.data.cos}
        for sc in self.data.student_co_scores:
            att = attempts_map[sc["attempt_id"]]
            c_num = co_number_by_id[sc["co_id"]]
            att["marks_by_co"][c_num] = COMarks(c_num, sc["marks_obtained"], sc["max_marks"])

        attempt_scores = [
            AttemptScore(
                usn=v["usn"],
                quiz_id=v["quiz_id"],
                module_id=v["module_id"],
                attempt_number=v["attempt_number"],
                per_co=v["marks_by_co"],
            )
            for v in attempts_map.values()
        ]

        counted = select_counted(attempt_scores, "best")
        sheet = build_co_sheet(counted, roster, cos)
        summary = class_summary(sheet, cos)
        weak = weak_cos(summary)

        # CO3 must be identified as weak (target 60% not met)
        weak_numbers = [w.co for w in weak]
        self.assertIn(3, weak_numbers)
        co3_summary = next(s for s in summary if s.co == 3)
        self.assertFalse(co3_summary.met)
        self.assertLess(co3_summary.attainment_pct, 60.0)

    def test_sql_generation(self):
        sql = generate_sql(self.data)
        self.assertIn("BEGIN;", sql)
        self.assertTrue(sql.rstrip().endswith("COMMIT;"))
        self.assertIn("INSERT INTO subjects", sql)
        self.assertIn("INSERT INTO course_outcomes", sql)
        self.assertIn("INSERT INTO modules", sql)
        self.assertIn("INSERT INTO students", sql)
        self.assertIn("INSERT INTO questions", sql)
        self.assertIn("INSERT INTO quizzes", sql)
        self.assertIn("INSERT INTO student_co_scores", sql)

    def test_deterministic_generation(self):
        data2 = generate_seed_data()
        self.assertEqual(self.data.subject["id"], data2.subject["id"])
        self.assertEqual(len(self.data.students), len(data2.students))
        self.assertEqual(self.data.students[0]["id"], data2.students[0]["id"])
        self.assertEqual(self.data.students[0]["usn"], data2.students[0]["usn"])


if __name__ == "__main__":
    unittest.main()
