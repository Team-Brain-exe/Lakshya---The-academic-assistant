"""Unit tests for calendar service and calendar agent tools."""

import unittest
from datetime import datetime, timedelta, timezone

from app.services.calendar import (
    CalendarPermissionError,
    CalendarValidationError,
    InMemoryCalendarStore,
    auto_create_quiz_event,
    create_event,
    delete_event,
    list_events,
    list_events_tool,
    schedule_event_tool,
    update_event,
)


class CalendarServiceTests(unittest.TestCase):
    def setUp(self):
        self.store = InMemoryCalendarStore()
        self.faculty_user = {"user_id": "fac-1", "role": "faculty", "name": "Dr. Raman"}
        self.student_user = {"user_id": "stud-1", "role": "student", "usn": "1XX23CS001"}
        self.now = datetime(2026, 10, 20, 10, 0, 0, tzinfo=timezone.utc)

    def test_faculty_can_create_event(self):
        event = create_event(
            self.store,
            self.faculty_user,
            subject_id="cs201",
            event_type="teaching",
            title="Lecture on Heaps",
            starts_at=self.now,
            ends_at=self.now + timedelta(hours=1),
        )
        self.assertEqual(event.title, "Lecture on Heaps")
        self.assertEqual(event.type, "teaching")
        self.assertFalse(event.created_by_agent)
        self.assertIsNotNone(self.store.get_event(event.id))

    def test_student_cannot_create_or_delete_event(self):
        with self.assertRaises(CalendarPermissionError):
            create_event(
                self.store,
                self.student_user,
                subject_id="cs201",
                event_type="quiz",
                title="Attempted Student Quiz",
                starts_at=self.now,
            )

        with self.assertRaises(CalendarPermissionError):
            delete_event(self.store, self.student_user, "any-id")

    def test_event_validation_rules(self):
        # Invalid type
        with self.assertRaises(CalendarValidationError):
            create_event(
                self.store,
                self.faculty_user,
                subject_id="cs201",
                event_type="hackathon",  # not in enum
                title="Invalid",
                starts_at=self.now,
            )

        # ends_at before starts_at
        with self.assertRaises(CalendarValidationError):
            create_event(
                self.store,
                self.faculty_user,
                subject_id="cs201",
                event_type="exam",
                title="Bad Times",
                starts_at=self.now,
                ends_at=self.now - timedelta(minutes=10),
            )

    def test_student_enrollment_scoping_on_list(self):
        # Create events for two subjects
        create_event(self.store, self.faculty_user, "cs201", "teaching", "CS201 Class", self.now)
        create_event(self.store, self.faculty_user, "ee101", "teaching", "EE101 Class", self.now)

        # Student enrolled only in cs201
        events = list_events(
            self.store,
            self.student_user,
            student_enrolled_subjects=["cs201"],
        )
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].subject_id, "cs201")

        # Student asking specifically for unenrolled subject gets 403
        with self.assertRaises(CalendarPermissionError):
            list_events(
                self.store,
                self.student_user,
                subject_id="ee101",
                student_enrolled_subjects=["cs201"],
            )

    def test_update_and_delete_event(self):
        event = create_event(
            self.store, self.faculty_user, "cs201", "quiz", "Pop Quiz", self.now
        )
        new_time = self.now + timedelta(days=1)
        updated = update_event(
            self.store, self.faculty_user, event.id, {"title": "Rescheduled Quiz", "starts_at": new_time}
        )
        self.assertEqual(updated.title, "Rescheduled Quiz")
        self.assertEqual(updated.starts_at, new_time)

        self.assertTrue(delete_event(self.store, self.faculty_user, event.id))
        self.assertIsNone(self.store.get_event(event.id))

    def test_auto_create_quiz_event(self):
        ev = auto_create_quiz_event(
            self.store,
            self.faculty_user,
            subject_id="cs201",
            quiz_id="quiz-101",
            title="Module 1 Quiz",
            opens_at=self.now,
            closes_at=self.now + timedelta(days=2),
        )
        self.assertEqual(ev.type, "quiz")
        self.assertEqual(ev.quiz_id, "quiz-101")
        self.assertEqual(ev.title, "Quiz: Module 1 Quiz")

    def test_agent_tools(self):
        # schedule_event_tool
        res = schedule_event_tool(
            self.store,
            self.faculty_user,
            subject_id="cs201",
            type="assignment",
            title="Assignment 1",
            starts_at="2026-10-25T09:00:00Z",
            ends_at="2026-10-30T23:59:59Z",
        )
        self.assertEqual(res["status"], "created")
        self.assertTrue(res["event"]["created_by_agent"])

        # list_events_tool
        listed = list_events_tool(
            self.store,
            self.faculty_user,
            subject_id="cs201",
        )
        self.assertEqual(len(listed), 1)
        self.assertEqual(listed[0]["title"], "Assignment 1")


if __name__ == "__main__":
    unittest.main()

