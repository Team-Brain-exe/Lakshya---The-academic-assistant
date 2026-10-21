"""Unit tests for slide retrieval and grounded Q&A service."""

import unittest

from app.services.qa import (
    REFUSAL_MESSAGE,
    InMemoryChunkRetrievalStore,
    answer_from_course_material,
    retrieve_chunks,
)


class SlideQATests(unittest.TestCase):
    def setUp(self):
        self.store = InMemoryChunkRetrievalStore()
        self.subject_id = "cs201"

        # Populate sample slide chunks
        self.store.add_chunk(
            subject_id=self.subject_id,
            chunk_id="chunk-1",
            module_id="mod-1",
            slide_number=2,
            text="Binary search operates on sorted arrays in O(log n) time by dividing search space.",
        )
        self.store.add_chunk(
            subject_id=self.subject_id,
            chunk_id="chunk-2",
            module_id="mod-1",
            slide_number=5,
            text="Hash tables achieve O(1) expected time for lookup using collision resolution like separate chaining.",
        )
        self.store.add_chunk(
            subject_id=self.subject_id,
            chunk_id="chunk-3",
            module_id="mod-2",
            slide_number=12,
            text="A binary heap is a complete binary tree used to implement efficient priority queues with O(log n) extract-max.",
        )

    def test_retrieve_chunks_returns_relevant_slides(self):
        chunks = retrieve_chunks(self.store, self.subject_id, "binary search complexity", top_k=2)
        self.assertGreater(len(chunks), 0)
        self.assertEqual(chunks[0].slide_number, 2)
        self.assertIn("O(log n)", chunks[0].text)

    def test_answer_from_course_material_cites_slides(self):
        res = answer_from_course_material(
            self.store,
            self.subject_id,
            "How does a hash table achieve O(1) lookup?",
        )
        self.assertFalse(res.refused)
        self.assertIn("Slide 5", res.answer)
        self.assertEqual(len(res.citations), 1)
        self.assertEqual(res.citations[0]["slide_number"], 5)
        self.assertEqual(res.citations[0]["module_id"], "mod-1")

    def test_refuses_when_no_material_matches(self):
        res = answer_from_course_material(
            self.store,
            self.subject_id,
            "Explain quantum entanglement and superconducting qubits.",
        )
        self.assertTrue(res.refused)
        self.assertEqual(res.answer, REFUSAL_MESSAGE)
        self.assertEqual(res.citations, [])

    def test_ai_client_integration(self):
        called = {}

        def mock_ai_client(prompt: str, context: str) -> str:
            called["prompt"] = prompt
            called["context"] = context
            return "According to [Slide 12], binary heaps provide priority queue operations in O(log n) time."

        res = answer_from_course_material(
            self.store,
            self.subject_id,
            "What is a binary heap used for?",
            ai_client=mock_ai_client,
        )
        self.assertFalse(res.refused)
        self.assertIn("[Slide 12]", res.answer)
        self.assertIn("binary heap", called["prompt"])
        self.assertIn("Slide 12", called["context"])

    def test_ai_client_error_falls_back_gracefully(self):
        def failing_client(prompt: str, context: str) -> str:
            raise RuntimeError("API rate limit exceeded")

        res = answer_from_course_material(
            self.store,
            self.subject_id,
            "What is binary search?",
            ai_client=failing_client,
        )
        self.assertFalse(res.refused)
        self.assertIn("Slide 2", res.answer)


if __name__ == "__main__":
    unittest.main()

