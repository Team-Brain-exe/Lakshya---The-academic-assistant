"""Unit tests for study material (flashcards/notes) and personalized study plan services."""

import unittest

from app.services.study_material import (
    InMemoryStudyMaterialStore,
    generate_module_study_material,
    get_module_flashcards,
    get_module_notes,
)
from app.services.study_plan import (
    InMemoryStudyPlanStore,
    build_study_plan,
    get_latest_study_plan,
)


class StudyServicesTests(unittest.TestCase):
    def setUp(self):
        self.material_store = InMemoryStudyMaterialStore()
        self.plan_store = InMemoryStudyPlanStore()
        self.module_id = "mod-trees"
        self.chunks = [
            {"slide_number": 1, "text": "Binary Trees\nProperties and recursive in-order, pre-order traversals.", "co_number": 3},
            {"slide_number": 2, "text": "Binary Search Trees\nBST search and insertion algorithm with logarithmic average cost.", "co_number": 3},
        ]
        self.co_configs = {
            1: {"id": "co-1-id", "threshold_pct": 60.0, "description": "Complexity Analysis"},
            2: {"id": "co-2-id", "threshold_pct": 60.0, "description": "Linear Structures"},
            3: {"id": "co-3-id", "threshold_pct": 60.0, "description": "Hierarchical Trees"},
        }

    def test_generate_module_study_material_once_per_module(self):
        cards1, notes1 = generate_module_study_material(
            self.material_store, self.module_id, "Module 3: Trees", self.chunks
        )
        self.assertEqual(len(cards1), 2)
        self.assertEqual(len(notes1), 2)
        self.assertIn("Binary Trees", cards1[0].front)

        # Second call returns existing without duplicating
        cards2, notes2 = generate_module_study_material(
            self.material_store, self.module_id, "Module 3: Trees", self.chunks
        )
        self.assertEqual(len(cards2), 2)
        self.assertEqual(len(self.material_store.list_flashcards(self.module_id)), 2)

    def test_get_flashcards_and_notes(self):
        generate_module_study_material(
            self.material_store, self.module_id, "Module 3: Trees", self.chunks
        )
        cards = get_module_flashcards(self.material_store, self.module_id)
        notes = get_module_notes(self.material_store, self.module_id)
        self.assertEqual(len(cards), 2)
        self.assertEqual(len(notes), 2)
        self.assertIn("front", cards[0])
        self.assertIn("title", notes[0])

    def test_build_study_plan_targets_weak_co(self):
        # Student score: CO1 = 80% (pass), CO2 = 75% (pass), CO3 = 20% (weak!)
        student_scores = {1: 80.0, 2: 75.0, 3: 20.0}
        flashcards = [
            {"id": "card-1", "co_number": 3, "front": "What is a BST?", "back": "A binary tree with ordered keys"}
        ]

        plan = build_study_plan(
            self.plan_store,
            student_id="student-1",
            subject_id="cs201",
            student_co_percentages=student_scores,
            co_configs=self.co_configs,
            slide_chunks=self.chunks,
            flashcards=flashcards,
        )

        self.assertEqual(plan.student_id, "student-1")
        self.assertIn("co-3-id", plan.weak_co_ids)
        self.assertEqual(plan.plan["weak_cos"], [3])

        steps = plan.plan["steps"]
        self.assertEqual(len(steps), 1)
        step3 = steps[0]
        self.assertEqual(step3["co_number"], 3)
        self.assertIn("Hierarchical Trees", step3["goal"])
        self.assertEqual(len(step3["slides"]), 2)
        self.assertEqual(len(step3["flashcards"]), 1)

    def test_get_latest_study_plan(self):
        student_scores = {3: 30.0}
        p1 = build_study_plan(
            self.plan_store,
            student_id="student-2",
            subject_id="cs201",
            student_co_percentages=student_scores,
            co_configs=self.co_configs,
            slide_chunks=self.chunks,
            flashcards=[],
        )
        retrieved = get_latest_study_plan(self.plan_store, "student-2", "cs201")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved["id"], p1.id)


if __name__ == "__main__":
    unittest.main()

