"""Unit tests for quiz publishing, attempt lifecycle, answer masking, and score persistence."""

import unittest
from datetime import datetime, timedelta, timezone

from app.services.quizzes import (
    AttemptLimitReachedError,
    ForbiddenError,
    InMemoryQuizStore,
    NotFoundError,
    QuestionNotApprovedError,
    QuestionRecord,
    QuizClosedError,
    QuizNotOpenError,
    QuizNotPublishedError,
    create_quiz,
    get_active_attempt,
    list_quizzes,
    publish_quiz,
    review_attempt,
    save_draft_answers,
    start_quiz_attempt,
    submit_attempt,
)


class QuizServiceTests(unittest.TestCase):
    def setUp(self):
        self.store = InMemoryQuizStore()
        self.faculty_user = {"user_id": "fac-1", "role": "faculty"}
        self.student_user = {"user_id": "user-s1", "role": "student", "student_id": "stud-1", "usn": "1XX23CS001"}
        self.student_user_2 = {"user_id": "user-s2", "role": "student", "student_id": "stud-2", "usn": "1XX23CS002"}
        self.now = datetime(2026, 10, 20, 10, 0, 0, tzinfo=timezone.utc)

        # Questions
        self.q1_approved = QuestionRecord(
            id="q1",
            module_id="mod-1",
            co_id="co-1",
            co_number=1,
            stem="What is Big-O of binary search?",
            options=["O(1)", "O(log n)", "O(n)", "O(n^2)"],
            correct_option=1,
            explanation="Halves search space.",
            marks=1.0,
            status="approved",
        )
        self.q2_approved = QuestionRecord(
            id="q2",
            module_id="mod-1",
            co_id="co-2",
            co_number=2,
            stem="Which structure is LIFO?",
            options=["Queue", "Stack", "Tree", "Graph"],
            correct_option=1,
            explanation="Stack is LIFO.",
            marks=2.0,
            status="approved",
        )
        self.q3_draft = QuestionRecord(
            id="q3",
            module_id="mod-1",
            co_id="co-1",
            co_number=1,
            stem="Draft question?",
            options=["A", "B", "C", "D"],
            correct_option=0,
            explanation="Draft explanation",
            marks=1.0,
            status="draft",
        )

        self.store.add_question(self.q1_approved)
        self.store.add_question(self.q2_approved)
        self.store.add_question(self.q3_draft)

    def test_publish_refuses_unapproved_question(self):
        # Create quiz with draft question
        quiz = create_quiz(
            self.store,
            self.faculty_user,
            module_id="mod-1",
            subject_id="cs201",
            title="Quiz with Draft",
            question_ids=["q1", "q3"],
        )
        self.assertFalse(quiz.published)

        # Publishing must be refused with QuestionNotApprovedError
        with self.assertRaises(QuestionNotApprovedError):
            publish_quiz(self.store, self.faculty_user, quiz.id)

    def test_publish_succeeds_when_all_approved(self):
        quiz = create_quiz(
            self.store,
            self.faculty_user,
            module_id="mod-1",
            subject_id="cs201",
            title="Approved Quiz",
            question_ids=["q1", "q2"],
        )
        pub = publish_quiz(self.store, self.faculty_user, quiz.id)
        self.assertTrue(pub.published)
        self.assertIsNotNone(pub.published_at)

    def test_start_attempt_masks_answers_and_checks_status(self):
        # Unpublished quiz raises QuizNotPublishedError
        unpub = create_quiz(
            self.store,
            self.faculty_user,
            module_id="mod-1",
            subject_id="cs201",
            title="Unpublished",
            question_ids=["q1"],
        )
        with self.assertRaises(QuizNotPublishedError):
            start_quiz_attempt(self.store, self.student_user, unpub.id, now=self.now)

        # Publish quiz
        pub = publish_quiz(self.store, self.faculty_user, unpub.id)

        # Start attempt
        att_res = start_quiz_attempt(self.store, self.student_user, pub.id, now=self.now)
        self.assertEqual(att_res["attempt_number"], 1)
        self.assertEqual(att_res["attempts_left"], 1)

        # Verify correct_option and explanation are stripped
        questions = att_res["questions"]
        self.assertEqual(len(questions), 1)
        self.assertNotIn("correct_option", questions[0])
        self.assertNotIn("explanation", questions[0])
        self.assertIn("stem", questions[0])
        self.assertIn("options", questions[0])

    def test_quiz_window_checks(self):
        opens = self.now + timedelta(hours=2)
        closes = self.now + timedelta(hours=5)

        quiz = create_quiz(
            self.store,
            self.faculty_user,
            module_id="mod-1",
            subject_id="cs201",
            title="Timed Quiz",
            question_ids=["q1"],
            opens_at=opens,
            closes_at=closes,
        )
        publish_quiz(self.store, self.faculty_user, quiz.id)

        # Before opening
        with self.assertRaises(QuizNotOpenError):
            start_quiz_attempt(self.store, self.student_user, quiz.id, now=self.now)

        # After closing
        with self.assertRaises(QuizClosedError):
            start_quiz_attempt(self.store, self.student_user, quiz.id, now=closes + timedelta(minutes=1))

    def test_attempt_limit_and_multiple_attempts_scoring(self):
        quiz = create_quiz(
            self.store,
            self.faculty_user,
            module_id="mod-1",
            subject_id="cs201",
            title="Two Attempt Quiz",
            question_ids=["q1", "q2"],
        )
        publish_quiz(self.store, self.faculty_user, quiz.id)

        # Attempt 1: gets q1 wrong (0/1), q2 right (2/2) -> 2 marks total
        att1 = start_quiz_attempt(self.store, self.student_user, quiz.id, now=self.now)
        att1_id = att1["attempt_id"]

        save_draft_answers(self.store, self.student_user, att1_id, {"q1": 0, "q2": 1})
        sub1 = submit_attempt(self.store, self.student_user, att1_id, {"q1": 0, "q2": 1}, now=self.now)
        self.assertEqual(sub1["total_score"], 2.0)
        self.assertEqual(sub1["max_score"], 3.0)

        # Check StudentCOScore rows saved
        scores = self.store.list_co_scores_for_student("stud-1", "cs201")
        self.assertEqual(len(scores), 2)
        self.assertTrue(all(s.counted for s in scores))

        # Attempt 2: gets both right -> 3 marks total
        att2 = start_quiz_attempt(self.store, self.student_user, quiz.id, now=self.now + timedelta(hours=1))
        att2_id = att2["attempt_id"]
        sub2 = submit_attempt(self.store, self.student_user, att2_id, {"q1": 1, "q2": 1}, now=self.now + timedelta(hours=1))
        self.assertEqual(sub2["total_score"], 3.0)

        # Check counted flag: under "best", attempt 2 (3 marks) is counted=True, attempt 1 (2 marks) is counted=False
        scores = self.store.list_co_scores_for_student("stud-1", "cs201")
        self.assertEqual(len(scores), 4)
        att1_scores = [s for s in scores if s.attempt_id == att1_id]
        att2_scores = [s for s in scores if s.attempt_id == att2_id]
        self.assertTrue(all(not s.counted for s in att1_scores))
        self.assertTrue(all(s.counted for s in att2_scores))

        # Attempt 3: MUST raise AttemptLimitReachedError
        with self.assertRaises(AttemptLimitReachedError):
            start_quiz_attempt(self.store, self.student_user, quiz.id, now=self.now + timedelta(hours=2))

    def test_review_attempt_student_isolation(self):
        quiz = create_quiz(
            self.store,
            self.faculty_user,
            module_id="mod-1",
            subject_id="cs201",
            title="Review Test Quiz",
            question_ids=["q1"],
        )
        publish_quiz(self.store, self.faculty_user, quiz.id)

        att = start_quiz_attempt(self.store, self.student_user, quiz.id, now=self.now)
        att_id = att["attempt_id"]

        # Cannot review before submitting
        with self.assertRaises(Exception):
            review_attempt(self.store, self.student_user, att_id)

        submit_attempt(self.store, self.student_user, att_id, {"q1": 1}, now=self.now)

        # Student 2 cannot review Student 1's attempt (ForbiddenError)
        with self.assertRaises(ForbiddenError):
            review_attempt(self.store, self.student_user_2, att_id)

        # Student 1 can review own attempt: reveals correct option and explanation
        rev = review_attempt(self.store, self.student_user, att_id)
        self.assertEqual(len(rev), 1)
        self.assertEqual(rev[0]["chosen"], 1)
        self.assertEqual(rev[0]["correct"], 1)
        self.assertEqual(rev[0]["explanation"], "Halves search space.")


if __name__ == "__main__":
    unittest.main()

