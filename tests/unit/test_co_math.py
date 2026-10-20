import unittest

from app.engine.co_math import (
    AttemptScore,
    COConfig,
    CountedScore,
    StudentInfo,
    aggregate_student_scores,
    build_co_sheet,
    class_summary,
    co_drilldown,
    select_counted,
    weak_cos,
)
from app.engine.grading import COMarks, QuestionKey, grade_attempt


def marks(**by_co):
    """marks(co1=(2, 3), co2=(1, 2)) -> {1: COMarks(1, 2, 3), 2: COMarks(2, 1, 2)}"""
    return {int(k[2:]): COMarks(int(k[2:]), ob, mx) for k, (ob, mx) in by_co.items()}


def attempt(usn, quiz, module, n, **by_co):
    return AttemptScore(usn, quiz, module, n, marks(**by_co))


def counted(usn, quiz, module, **by_co):
    return CountedScore(usn, quiz, module, marks(**by_co))


CONFIG = [COConfig(1, 60, 60), COConfig(2, 60, 60), COConfig(3, 60, 60)]


class AttemptRuleTests(unittest.TestCase):
    def setUp(self):
        # attempt 1 is the stronger one (3 marks); attempt 2 is weaker (2 marks)
        self.two = [
            attempt("S1", "Q1", "M1", 1, co1=(3, 3), co2=(0, 2)),
            attempt("S1", "Q1", "M1", 2, co1=(1, 3), co2=(1, 2)),
        ]

    def test_best_picks_the_highest_total(self):
        [c] = select_counted(self.two, "best")
        self.assertEqual((c.per_co[1].obtained, c.per_co[2].obtained), (3, 0))

    def test_latest_picks_the_highest_attempt_number(self):
        [c] = select_counted(self.two, "latest")
        self.assertEqual((c.per_co[1].obtained, c.per_co[2].obtained), (1, 1))

    def test_average_takes_the_mean_per_co(self):
        [c] = select_counted(self.two, "average")
        self.assertEqual((c.per_co[1].obtained, c.per_co[1].maximum), (2, 3))
        self.assertEqual((c.per_co[2].obtained, c.per_co[2].maximum), (0.5, 2))

    def test_order_of_input_does_not_matter(self):
        [c] = select_counted(list(reversed(self.two)), "latest")
        self.assertEqual(c.per_co[1].obtained, 1)

    def test_best_on_a_tie_takes_the_later_attempt(self):
        tie = [
            attempt("S1", "Q1", "M1", 1, co1=(2, 3), co2=(0, 2)),
            attempt("S1", "Q1", "M1", 2, co1=(0, 3), co2=(2, 2)),
        ]
        [c] = select_counted(tie, "best")
        self.assertEqual(c.per_co[2].obtained, 2)

    def test_one_attempt_gives_the_same_result_under_every_rule(self):
        one = [attempt("S1", "Q1", "M1", 1, co1=(2, 3))]
        for rule in ("best", "latest", "average"):
            [c] = select_counted(one, rule)
            self.assertEqual((c.per_co[1].obtained, c.per_co[1].maximum), (2, 3), rule)

    def test_quizzes_and_students_are_counted_separately(self):
        attempts = self.two + [
            attempt("S1", "Q2", "M2", 1, co1=(1, 1)),
            attempt("S2", "Q1", "M1", 1, co1=(0, 3)),
        ]
        result = select_counted(attempts, "best")
        self.assertEqual([(c.usn, c.quiz_id) for c in result], [("S1", "Q1"), ("S1", "Q2"), ("S2", "Q1")])

    def test_unknown_rule_is_rejected(self):
        with self.assertRaises(ValueError):
            select_counted(self.two, "median")

    def test_duplicate_attempt_number_is_rejected(self):
        dup = [attempt("S1", "Q1", "M1", 1, co1=(1, 1)), attempt("S1", "Q1", "M1", 1, co1=(0, 1))]
        with self.assertRaises(ValueError):
            select_counted(dup, "best")

    def test_no_attempts_gives_nothing(self):
        self.assertEqual(select_counted([], "best"), [])


class AggregateTests(unittest.TestCase):
    def test_sums_across_quizzes_and_filters_by_module(self):
        c = [
            counted("S1", "Q1", "M1", co1=(2, 3)),
            counted("S1", "Q2", "M1", co1=(1, 2)),
            counted("S1", "Q3", "M2", co1=(3, 3)),
        ]
        sem = aggregate_student_scores(c)["S1"][1]
        self.assertEqual((sem.obtained, sem.maximum), (6, 8))
        m1 = aggregate_student_scores(c, module_id="M1")["S1"][1]
        self.assertEqual((m1.obtained, m1.maximum), (3, 5))
        self.assertNotIn("S1", aggregate_student_scores(c, module_id="M9"))


class COSheetTests(unittest.TestCase):
    def setUp(self):
        # Hand calculation
        #   S1  Q1 (M1): CO1 2/3, CO2 1/2     Q2 (M2): CO1 3/3
        #       semester: CO1 5/6 = 83.33, CO2 1/2 = 50, total 6/8 = 75
        #       module M1: CO1 2/3 = 66.67, CO2 50, total 3/5 = 60
        #   S2  Q1 (M1): CO1 0/3, CO2 2/2     -> CO1 0, CO2 100, total 2/5 = 40
        #   S3  no attempts                   -> all None
        self.counted = [
            counted("S1", "Q1", "M1", co1=(2, 3), co2=(1, 2)),
            counted("S1", "Q2", "M2", co1=(3, 3)),
            counted("S2", "Q1", "M1", co1=(0, 3), co2=(2, 2)),
        ]
        self.roster = [StudentInfo("S3", "Cara"), StudentInfo("S1", "Asha"), StudentInfo("S2", "Bala")]

    def row(self, sheet, usn):
        return next(r for r in sheet.rows if r.usn == usn)

    def test_semester_sheet_matches_hand_calculation(self):
        sheet = build_co_sheet(self.counted, self.roster, CONFIG)
        s1 = self.row(sheet, "S1")
        self.assertAlmostEqual(s1.co_scores[1], 83.3333333, places=5)
        self.assertEqual(s1.co_scores[2], 50)
        self.assertEqual((s1.total_obtained, s1.total_max), (6, 8))
        self.assertEqual(s1.total_pct, 75)
        s2 = self.row(sheet, "S2")
        self.assertEqual((s2.co_scores[1], s2.co_scores[2]), (0, 100))
        self.assertEqual(s2.total_pct, 40)

    def test_module_scope_uses_only_that_module(self):
        sheet = build_co_sheet(self.counted, self.roster, CONFIG, module_id="M1")
        s1 = self.row(sheet, "S1")
        self.assertAlmostEqual(s1.co_scores[1], 66.6666667, places=5)
        self.assertEqual(s1.total_pct, 60)

    def test_co_with_no_questions_is_none_not_zero(self):
        sheet = build_co_sheet(self.counted, self.roster, CONFIG)
        self.assertIsNone(self.row(sheet, "S1").co_scores[3])
        self.assertIsNone(sheet.averages[3])

    def test_student_with_no_attempts_still_has_a_row_of_nones(self):
        sheet = build_co_sheet(self.counted, self.roster, CONFIG)
        s3 = self.row(sheet, "S3")
        self.assertTrue(all(v is None for v in s3.co_scores.values()))
        self.assertIsNone(s3.total_pct)
        self.assertEqual(s3.total_max, 0)

    def test_averages_skip_students_with_no_data(self):
        sheet = build_co_sheet(self.counted, self.roster, CONFIG)
        self.assertAlmostEqual(sheet.averages[1], (83.3333333 + 0) / 2, places=4)
        self.assertEqual(sheet.averages[2], 75)

    def test_rows_are_sorted_by_usn_and_columns_by_co_number(self):
        sheet = build_co_sheet(self.counted, self.roster, list(reversed(CONFIG)))
        self.assertEqual([r.usn for r in sheet.rows], ["S1", "S2", "S3"])
        self.assertEqual(sheet.co_numbers, (1, 2, 3))

    def test_section_filter(self):
        roster = [StudentInfo("S1", "Asha", "A"), StudentInfo("S2", "Bala", "B")]
        sheet = build_co_sheet(self.counted, roster, CONFIG, section="B")
        self.assertEqual([r.usn for r in sheet.rows], ["S2"])

    def test_scores_for_students_not_on_the_roster_are_left_out(self):
        extra = self.counted + [counted("GHOST", "Q1", "M1", co1=(3, 3))]
        sheet = build_co_sheet(extra, self.roster, CONFIG)
        self.assertNotIn("GHOST", [r.usn for r in sheet.rows])

    def test_scores_for_unconfigured_cos_are_left_out_of_the_total(self):
        data = [counted("S1", "Q1", "M1", co1=(1, 2), co9=(5, 5))]
        sheet = build_co_sheet(data, [StudentInfo("S1")], [COConfig(1, 60, 60)])
        row = sheet.rows[0]
        self.assertEqual((row.total_obtained, row.total_max), (1, 2))
        self.assertEqual(sheet.co_numbers, (1,))

    def test_changing_one_answer_updates_the_sheet_correctly(self):
        quiz = [
            QuestionKey("a", co=1, correct_option=0),
            QuestionKey("b", co=1, correct_option=1),
            QuestionKey("c", co=2, correct_option=2),
            QuestionKey("d", co=2, correct_option=3),
        ]

        def sheet_for(answers):
            grade = grade_attempt(quiz, answers)
            attempts = [AttemptScore.from_grade("S1", "Q1", "M1", 1, grade)]
            return build_co_sheet(select_counted(attempts, "best"), [StudentInfo("S1")], CONFIG[:2])

        before = sheet_for({"a": 0, "b": 0, "c": 2, "d": 0})  # CO1 1/2, CO2 1/2
        after = sheet_for({"a": 0, "b": 1, "c": 2, "d": 0})  # b fixed: CO1 2/2, CO2 1/2
        b, a = before.rows[0], after.rows[0]
        self.assertEqual((b.co_scores[1], b.co_scores[2], b.total_pct), (50, 50, 50))
        self.assertEqual((a.co_scores[1], a.co_scores[2], a.total_pct), (100, 50, 75))


class ClassSummaryTests(unittest.TestCase):
    def sheet(self, co1_scores, co2_scores=None, cfg=None):
        """One student per entry; maximum 100 so obtained equals the percentage."""
        co2_scores = co2_scores or [None] * len(co1_scores)
        data, roster = [], []
        for i, (a, b) in enumerate(zip(co1_scores, co2_scores), start=1):
            usn = f"S{i}"
            roster.append(StudentInfo(usn))
            by_co = {}
            if a is not None:
                by_co["co1"] = (a, 100)
            if b is not None:
                by_co["co2"] = (b, 100)
            if by_co:
                data.append(counted(usn, "Q1", "M1", **by_co))
        cfg = cfg or [COConfig(1, 60, 60), COConfig(2, 60, 60)]
        return build_co_sheet(data, roster, cfg), cfg

    def test_counts_average_and_attainment(self):
        # 80 and 60 reach the threshold (60 is inclusive); 59 and 40 do not; one student absent
        sheet, cfg = self.sheet([80, 60, 59, 40, None])
        co1 = class_summary(sheet, cfg)[0]
        self.assertEqual((co1.enrolled, co1.attempted, co1.not_attempted), (5, 4, 1))
        self.assertEqual((co1.above, co1.below), (2, 2))
        self.assertEqual(co1.average, 59.75)
        self.assertEqual(co1.attainment_pct, 40)  # 2 of 5 enrolled
        self.assertFalse(co1.met)
        self.assertEqual(co1.gap, 20)

    def test_attempted_denominator_excludes_absent_students(self):
        sheet, cfg = self.sheet([80, 60, 59, 40, None])
        co1 = class_summary(sheet, cfg, denominator="attempted")[0]
        self.assertEqual(co1.attainment_pct, 50)  # 2 of 4 attempted
        self.assertEqual(co1.gap, 10)

    def test_target_met_when_attainment_reaches_target(self):
        sheet, _ = self.sheet([80, 60, 59, 40, None])
        cfg = [COConfig(1, 60, 40), COConfig(2, 60, 60)]
        co1 = class_summary(sheet, cfg)[0]
        self.assertTrue(co1.met)  # 40 >= 40
        self.assertEqual(co1.gap, 0)

    def test_weak_cos_are_below_target_with_the_biggest_gap_first(self):
        sheet, cfg = self.sheet([80, 70, 65, 90], [30, 40, 50, 70])
        # CO1: all 4 reach 60 -> 100% (met). CO2: only 70 reaches -> 25% vs target 60 (gap 35)
        weak = weak_cos(class_summary(sheet, cfg))
        self.assertEqual([w.co for w in weak], [2])
        self.assertEqual((weak[0].attainment_pct, weak[0].gap), (25, 35))

    def test_weak_cos_sorted_by_gap(self):
        sheet, _ = self.sheet([10, 20, 30, 40], [30, 40, 50, 70])
        cfg = [COConfig(1, 60, 60), COConfig(2, 60, 60)]
        weak = weak_cos(class_summary(sheet, cfg))
        self.assertEqual([w.co for w in weak], [1, 2])  # CO1 attainment 0 (gap 60), CO2 25 (gap 35)

    def test_a_co_nobody_attempted_is_no_data_not_weak(self):
        sheet, cfg = self.sheet([80, 90, 70])  # CO2 has no scores at all
        summary = class_summary(sheet, cfg)
        co2 = summary[1]
        self.assertFalse(co2.has_data)
        self.assertEqual(weak_cos(summary), [])

    def test_no_students_means_no_attainment(self):
        sheet = build_co_sheet([], [], [COConfig(1, 60, 60)])
        [co1] = class_summary(sheet, [COConfig(1, 60, 60)])
        self.assertIsNone(co1.attainment_pct)
        self.assertFalse(co1.met)

    def test_invalid_denominator_is_rejected(self):
        sheet, cfg = self.sheet([80])
        with self.assertRaises(ValueError):
            class_summary(sheet, cfg, denominator="everyone")


class DrilldownTests(unittest.TestCase):
    def graded(self, usn, quiz, module, n, keys, answers):
        return AttemptScore.from_grade(usn, quiz, module, n, grade_attempt(keys, answers))

    def setUp(self):
        self.q1 = [
            QuestionKey("a", co=1, correct_option=0),
            QuestionKey("b", co=1, correct_option=1),
            QuestionKey("c", co=2, correct_option=2),
        ]
        self.q2 = [QuestionKey("d", co=1, correct_option=3)]
        # Hand calculation (CO1 unless stated)
        #   S1  Q1 (M1): a right, b right -> 2/2     (CO2: c right -> 1/1)
        #       Q2 (M2): d right          -> 1/1     CO1 total 3/3 = 100
        #   S2  Q1 (M1): a right, b wrong -> 1/2     (CO2: c wrong -> 0/1)
        #       Q2 (M2): d wrong          -> 0/1     CO1 total 1/3 = 33.33
        #   S3  no attempts
        #   M1: 3/4 = 75, 2 students     M2: 1/2 = 50, 2 students
        #   questions: a 2 of 2 right, b 1 of 2, d 1 of 2
        attempts = [
            self.graded("S1", "Q1", "M1", 1, self.q1, {"a": 0, "b": 1, "c": 2}),
            self.graded("S2", "Q1", "M1", 1, self.q1, {"a": 0, "b": 0, "c": 0}),
            self.graded("S1", "Q2", "M2", 1, self.q2, {"d": 3}),
            self.graded("S2", "Q2", "M2", 1, self.q2, {"d": 0}),
        ]
        self.counted = select_counted(attempts, "best")
        self.roster = [
            StudentInfo("S1", "Asha", "A"),
            StudentInfo("S2", "Bala", "B"),
            StudentInfo("S3", "Cara", "A"),
        ]
        self.cfg = COConfig(1, 60, 60)

    def test_modules_match_hand_calculation(self):
        d = co_drilldown(self.counted, self.roster, self.cfg)
        self.assertEqual(
            [(m.module_id, m.obtained, m.maximum, m.students, m.percentage) for m in d.modules],
            [("M1", 3, 4, 2, 75), ("M2", 1, 2, 2, 50)],
        )

    def test_questions_are_listed_hardest_first(self):
        d = co_drilldown(self.counted, self.roster, self.cfg)
        self.assertEqual(
            [(q.question_id, q.module_id, q.samples, q.correct, q.correct_pct) for q in d.questions],
            [("b", "M1", 2, 1, 50), ("d", "M2", 2, 1, 50), ("a", "M1", 2, 2, 100)],
        )

    def test_students_are_listed_weakest_first_with_attained_flag(self):
        d = co_drilldown(self.counted, self.roster, self.cfg)
        self.assertEqual([s.usn for s in d.students], ["S2", "S1"])
        s2, s1 = d.students
        self.assertAlmostEqual(s2.percentage, 33.3333333, places=5)
        self.assertFalse(s2.attained)
        self.assertEqual(s1.percentage, 100)
        self.assertTrue(s1.attained)

    def test_students_with_no_marks_are_counted_as_not_attempted(self):
        d = co_drilldown(self.counted, self.roster, self.cfg)
        self.assertEqual(d.not_attempted, 1)  # S3
        self.assertNotIn("S3", [s.usn for s in d.students])

    def test_module_filter_uses_only_that_module(self):
        d = co_drilldown(self.counted, self.roster, self.cfg, module_id="M1")
        self.assertEqual([m.module_id for m in d.modules], ["M1"])
        self.assertEqual([q.question_id for q in d.questions], ["b", "a"])
        self.assertEqual([(s.usn, s.percentage) for s in d.students], [("S2", 50), ("S1", 100)])

    def test_section_filter_uses_only_that_section(self):
        d = co_drilldown(self.counted, self.roster, self.cfg, section="A")
        self.assertEqual([s.usn for s in d.students], ["S1"])
        self.assertEqual(d.not_attempted, 1)  # S3 is in section A and has no marks
        self.assertEqual([m.students for m in d.modules], [1, 1])

    def test_only_questions_of_the_asked_co_are_listed(self):
        d = co_drilldown(self.counted, self.roster, COConfig(2, 60, 60))
        self.assertEqual([q.question_id for q in d.questions], ["c"])
        self.assertEqual([m.module_id for m in d.modules], ["M1"])
        self.assertEqual([(s.usn, s.percentage) for s in d.students], [("S2", 0), ("S1", 100)])

    def test_a_co_with_no_marks_gives_an_empty_drilldown(self):
        d = co_drilldown(self.counted, self.roster, COConfig(5, 60, 60))
        self.assertEqual((d.modules, d.questions, d.students), ((), (), ()))
        self.assertEqual(d.not_attempted, 3)

    def test_students_not_on_the_roster_are_left_out(self):
        extra = list(self.counted) + [counted("GHOST", "Q1", "M1", co1=(3, 3))]
        d = co_drilldown(extra, self.roster, self.cfg)
        self.assertNotIn("GHOST", [s.usn for s in d.students])
        self.assertEqual(d.modules[0].students, 2)

    def test_average_rule_counts_every_attempt_as_a_sample(self):
        attempts = [
            self.graded("S1", "Q1", "M1", 1, self.q1, {"a": 0, "b": 0, "c": 2}),
            self.graded("S1", "Q1", "M1", 2, self.q1, {"a": 0, "b": 1, "c": 2}),
        ]
        d = co_drilldown(select_counted(attempts, "average"), [StudentInfo("S1")], self.cfg)
        b = next(q for q in d.questions if q.question_id == "b")
        self.assertEqual((b.samples, b.correct), (2, 1))
        # attempt 1: CO1 1/2, attempt 2: CO1 2/2 -> mean 1.5 of 2 = 75
        self.assertEqual(d.students[0].percentage, 75)

    def test_best_rule_uses_the_questions_of_the_counted_attempt_only(self):
        attempts = [
            self.graded("S1", "Q1", "M1", 1, self.q1, {"a": 0, "b": 0, "c": 2}),  # weaker
            self.graded("S1", "Q1", "M1", 2, self.q1, {"a": 0, "b": 1, "c": 2}),  # counted
        ]
        d = co_drilldown(select_counted(attempts, "best"), [StudentInfo("S1")], self.cfg)
        b = next(q for q in d.questions if q.question_id == "b")
        self.assertEqual((b.samples, b.correct), (1, 1))

    def test_without_question_results_the_question_list_is_empty(self):
        c = [counted("S1", "Q1", "M1", co1=(1, 2))]
        d = co_drilldown(c, [StudentInfo("S1")], self.cfg)
        self.assertEqual(d.questions, ())
        self.assertEqual(d.modules[0].percentage, 50)

    def test_drilldown_agrees_with_the_sheet(self):
        cfgs = [self.cfg, COConfig(2, 60, 60)]
        sheet = build_co_sheet(self.counted, self.roster, cfgs)
        d = co_drilldown(self.counted, self.roster, self.cfg)
        for s in d.students:
            row = next(r for r in sheet.rows if r.usn == s.usn)
            self.assertAlmostEqual(row.co_scores[1], s.percentage)
        attained = sum(1 for s in d.students if s.attained)
        summary = class_summary(sheet, cfgs)[0]
        self.assertEqual((attained, len(d.students) - attained), (summary.above, summary.below))


if __name__ == "__main__":
    unittest.main()
