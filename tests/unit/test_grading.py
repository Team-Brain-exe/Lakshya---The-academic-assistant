import unittest

from app.engine.grading import (
    QuestionKey,
    grade_attempt,
    meets_threshold,
    percentage,
    round2,
)


def quiz():
    """5 questions worth 6 marks: CO1 has 3 (1 mark each), CO2 has 1 (2 marks), CO3 has 1 (1 mark)."""
    return [
        QuestionKey("q1", co=1, correct_option=0),
        QuestionKey("q2", co=1, correct_option=1),
        QuestionKey("q3", co=1, correct_option=2),
        QuestionKey("q4", co=2, correct_option=3, marks=2),
        QuestionKey("q5", co=3, correct_option=0),
    ]


class GradeAttemptTests(unittest.TestCase):
    def test_all_correct_gives_full_marks(self):
        answers = {"q1": 0, "q2": 1, "q3": 2, "q4": 3, "q5": 0}
        r = grade_attempt(quiz(), answers)
        self.assertEqual(r.total_obtained, 6)
        self.assertEqual(r.total_max, 6)
        self.assertEqual(r.percentage, 100)
        for co in (1, 2, 3):
            self.assertEqual(r.per_co[co].percentage, 100)

    def test_hand_calculated_mixed_attempt(self):
        # CO1: q1 right, q2 wrong, q3 right  -> 2 of 3
        # CO2: q4 wrong                      -> 0 of 2
        # CO3: q5 right                      -> 1 of 1
        answers = {"q1": 0, "q2": 3, "q3": 2, "q4": 0, "q5": 0}
        r = grade_attempt(quiz(), answers)
        self.assertEqual((r.per_co[1].obtained, r.per_co[1].maximum), (2, 3))
        self.assertEqual((r.per_co[2].obtained, r.per_co[2].maximum), (0, 2))
        self.assertEqual((r.per_co[3].obtained, r.per_co[3].maximum), (1, 1))
        self.assertEqual((r.total_obtained, r.total_max), (3, 6))
        self.assertAlmostEqual(r.per_co[1].percentage, 66.6666667, places=5)
        self.assertEqual(r.per_co[2].percentage, 0)
        self.assertEqual(r.per_co[3].percentage, 100)
        self.assertEqual(r.percentage, 50)

    def test_weighted_marks_use_question_marks(self):
        answers = {"q4": 3}  # the 2-mark CO2 question, correct; everything else blank
        r = grade_attempt(quiz(), answers)
        self.assertEqual(r.per_co[2].obtained, 2)
        self.assertEqual(r.total_obtained, 2)

    def test_unanswered_scores_zero_but_counts_in_maximum(self):
        r = grade_attempt(quiz(), {})
        self.assertEqual(r.total_obtained, 0)
        self.assertEqual(r.total_max, 6)
        self.assertEqual(r.per_co[1].maximum, 3)
        self.assertEqual(r.per_co[1].percentage, 0)

    def test_none_answer_is_unanswered(self):
        r = grade_attempt(quiz(), {"q1": None, "q2": 1})
        self.assertEqual(r.per_co[1].obtained, 1)

    def test_invalid_answers_score_zero(self):
        answers = {"q1": -1, "q2": "1", "q3": True, "q4": 99, "q5": 1.0}
        r = grade_attempt(quiz(), answers)
        self.assertEqual(r.total_obtained, 0)
        # bool, str, float and negative are not accepted as choices
        self.assertIsNone(next(x for x in r.questions if x.question_id == "q3").chosen)
        self.assertIsNone(next(x for x in r.questions if x.question_id == "q5").chosen)

    def test_answer_for_unknown_question_is_ignored(self):
        r = grade_attempt(quiz(), {"q1": 0, "not-in-quiz": 0})
        self.assertEqual(r.total_obtained, 1)
        self.assertEqual(len(r.questions), 5)

    def test_co_with_no_questions_is_absent_not_zero(self):
        only_co1 = [QuestionKey("a", co=1, correct_option=0), QuestionKey("b", co=1, correct_option=1)]
        r = grade_attempt(only_co1, {"a": 0, "b": 1})
        self.assertEqual(list(r.per_co), [1])
        self.assertNotIn(4, r.per_co)

    def test_empty_quiz_has_no_percentage(self):
        r = grade_attempt([], {})
        self.assertEqual(r.total_max, 0)
        self.assertIsNone(r.percentage)
        self.assertEqual(dict(r.per_co), {})

    def test_per_co_is_sorted_by_co_number(self):
        questions = [
            QuestionKey("a", co=3, correct_option=0),
            QuestionKey("b", co=1, correct_option=0),
            QuestionKey("c", co=2, correct_option=0),
        ]
        self.assertEqual(list(grade_attempt(questions, {}).per_co), [1, 2, 3])

    def test_question_results_report_what_was_chosen(self):
        r = grade_attempt(quiz(), {"q1": 2, "q2": 1})
        q1 = next(x for x in r.questions if x.question_id == "q1")
        q2 = next(x for x in r.questions if x.question_id == "q2")
        self.assertFalse(q1.is_correct)
        self.assertEqual(q1.chosen, 2)
        self.assertEqual(q1.correct_option, 0)
        self.assertTrue(q2.is_correct)
        self.assertEqual(q2.marks_awarded, 1)

    def test_duplicate_question_ids_are_rejected(self):
        dup = [QuestionKey("a", co=1, correct_option=0), QuestionKey("a", co=2, correct_option=0)]
        with self.assertRaises(ValueError):
            grade_attempt(dup, {})

    def test_non_positive_marks_are_rejected(self):
        with self.assertRaises(ValueError):
            QuestionKey("a", co=1, correct_option=0, marks=0)
        with self.assertRaises(ValueError):
            QuestionKey("a", co=1, correct_option=0, marks=-1)

    def test_negative_correct_option_is_rejected(self):
        with self.assertRaises(ValueError):
            QuestionKey("a", co=1, correct_option=-1)


class PercentageTests(unittest.TestCase):
    def test_percentage(self):
        self.assertEqual(percentage(3, 5), 60.0)
        self.assertEqual(percentage(0, 4), 0)
        self.assertIsNone(percentage(0, 0))

    def test_threshold_is_inclusive(self):
        self.assertTrue(meets_threshold(60.0, 60))
        self.assertTrue(meets_threshold(percentage(3, 5), 60))
        self.assertFalse(meets_threshold(59.99, 60))

    def test_threshold_with_no_data_is_false(self):
        self.assertFalse(meets_threshold(None, 0))

    def test_threshold_tolerates_float_noise(self):
        self.assertTrue(meets_threshold(59.99999999999999, 60))

    def test_round2(self):
        self.assertEqual(round2(66.666666), 66.67)
        self.assertIsNone(round2(None))


if __name__ == "__main__":
    unittest.main()
