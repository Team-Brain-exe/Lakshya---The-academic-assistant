import io
import unittest

from app.pipeline.coverage import coverage
from app.pipeline.memory_store import InMemoryChunkStore
from app.pipeline.upload import COInfo, TagResult, process_module_upload
from helpers import build_deck, build_picture_only_deck

COS = [COInfo(1, "Hashing"), COInfo(2, "Trees"), COInfo(3, "Graphs")]


def deck():
    return io.BytesIO(build_deck())


def tag_everything_as_co1(chunks, cos):
    return [{"chunk_id": c.id, "cos": [1], "confidence": 0.9} for c in chunks]


class UploadPipelineTests(unittest.TestCase):
    def setUp(self):
        self.store = InMemoryChunkStore()

    def run_upload(self, tagger, source=None, cos=COS, **kw):
        return process_module_upload("M1", source or deck(), cos, tagger, self.store, **kw)

    def test_happy_path_saves_and_tags_every_chunk(self):
        report = self.run_upload(tag_everything_as_co1)
        self.assertEqual(report.status, "done")
        self.assertEqual((report.chunks_saved, report.tagged, report.untagged), (3, 3, 0))
        self.assertEqual(report.skipped_slides, (3,))
        self.assertEqual(report.total_slides, 4)
        self.assertEqual(self.store.final_status, "done")
        self.assertEqual([s[1] for s in self.store.status_history], ["processing", "done"])
        self.assertEqual(len(self.store.chunk_co_links()), 3)

    def test_tagger_that_raises_does_not_fail_the_upload(self):
        def boom(chunks, cos):
            raise RuntimeError("model unavailable")

        report = self.run_upload(boom)
        self.assertEqual(report.status, "done")
        self.assertEqual((report.tagged, report.untagged), (0, 3))
        self.assertEqual(self.store.untagged, set(self.store.chunks))
        self.assertIn("model unavailable", report.tagging_errors[0])

    def test_unusable_tagger_output_leaves_chunks_untagged(self):
        report = self.run_upload(lambda chunks, cos: [None, "garbage", 42, {"chunk_id": 7}, {}])
        self.assertEqual(report.status, "done")
        self.assertEqual(report.untagged, 3)

    def test_chunks_the_tagger_skipped_are_untagged(self):
        def tag_first_only(chunks, cos):
            return [TagResult(chunks[0].id, (2,), 0.8)]

        report = self.run_upload(tag_first_only)
        self.assertEqual((report.tagged, report.untagged), (1, 2))
        self.assertEqual(len(self.store.untagged), 2)

    def test_chunk_with_no_cos_counts_as_untagged(self):
        report = self.run_upload(lambda chunks, cos: [{"chunk_id": c.id, "cos": []} for c in chunks])
        self.assertEqual(report.untagged, 3)

    def test_unknown_co_numbers_are_dropped(self):
        def tagger(chunks, cos):
            return [
                {"chunk_id": chunks[0].id, "cos": [1, 9]},  # 9 does not exist
                {"chunk_id": chunks[1].id, "cos": [9]},  # only unknown -> untagged
            ]

        report = self.run_upload(tagger)
        self.assertEqual(report.tagged, 1)
        self.assertEqual(self.store.tags[chunks_id(self.store, 0)].cos, (1,))

    def test_co_labels_like_CO3_are_understood(self):
        def tagger(chunks, cos):
            return [{"chunk_id": chunks[0].id, "cos": ["CO3", " co2 ", "3"]}]

        self.run_upload(tagger)
        self.assertEqual(self.store.tags[chunks_id(self.store, 0)].cos, (2, 3))

    def test_confidence_outside_zero_to_one_is_dropped(self):
        def tagger(chunks, cos):
            return [
                {"chunk_id": chunks[0].id, "cos": [1], "confidence": 1.7},
                {"chunk_id": chunks[1].id, "cos": [1], "confidence": 0.5},
                {"chunk_id": chunks[2].id, "cos": [1], "confidence": "high"},
            ]

        self.run_upload(tagger)
        confidences = [self.store.tags[chunks_id(self.store, i)].confidence for i in range(3)]
        self.assertEqual(confidences, [None, 0.5, None])

    def test_results_for_chunks_outside_the_batch_are_ignored(self):
        report = self.run_upload(lambda chunks, cos: [{"chunk_id": "chunk-999", "cos": [1]}])
        self.assertEqual(report.tagged, 0)
        self.assertNotIn("chunk-999", self.store.tags)

    def test_chunks_are_tagged_in_batches(self):
        sizes = []

        def tagger(chunks, cos):
            sizes.append(len(chunks))
            return tag_everything_as_co1(chunks, cos)

        report = self.run_upload(tagger, batch_size=2)
        self.assertEqual(sizes, [2, 1])
        self.assertEqual(report.tagged, 3)

    def test_one_failed_batch_leaves_only_that_batch_untagged(self):
        calls = {"n": 0}

        def flaky(chunks, cos):
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("bad json")
            return tag_everything_as_co1(chunks, cos)

        report = self.run_upload(flaky, batch_size=2)
        self.assertEqual((report.tagged, report.untagged), (1, 2))
        self.assertEqual(report.status, "done")
        self.assertEqual(len(report.tagging_errors), 1)

    def test_no_cos_defined_means_no_tagging_call(self):
        called = []
        report = self.run_upload(lambda chunks, cos: called.append(1) or [], cos=[])
        self.assertEqual(called, [])
        self.assertEqual((report.status, report.untagged), ("done", 3))
        self.assertTrue(report.tagging_errors)

    def test_file_that_is_not_a_pptx_fails_cleanly(self):
        report = self.run_upload(tag_everything_as_co1, source=io.BytesIO(b"nope"))
        self.assertEqual(report.status, "failed")
        self.assertIn(".pptx", report.error)
        self.assertEqual(self.store.final_status, "failed")
        self.assertEqual(self.store.chunks, {})

    def test_deck_with_no_text_fails_with_a_clear_message(self):
        report = self.run_upload(tag_everything_as_co1, source=io.BytesIO(build_picture_only_deck()))
        self.assertEqual(report.status, "failed")
        self.assertIn("No text", report.error)
        self.assertEqual(report.skipped_slides, (1, 2))

    def test_database_failure_marks_the_module_failed_and_raises(self):
        class BrokenStore(InMemoryChunkStore):
            def save_chunks(self, module_id, chunks):
                raise RuntimeError("db down")

        store = BrokenStore()
        with self.assertRaises(RuntimeError):
            process_module_upload("M1", deck(), COS, tag_everything_as_co1, store)
        self.assertEqual(store.final_status, "failed")

    def test_batch_size_must_be_positive(self):
        with self.assertRaises(ValueError):
            self.run_upload(tag_everything_as_co1, batch_size=0)


def chunks_id(store, index):
    """Id of the index-th saved chunk (ids are assigned in slide order)."""
    return sorted(store.chunks, key=lambda cid: store.chunks[cid].slide_number)[index]


class CoverageTests(unittest.TestCase):
    def test_zero_chunks_gets_a_warning(self):
        result = coverage([1, 2, 3], [("a", 1), ("b", 1), ("c", 2)])
        by_co = {r.co: r for r in result}
        self.assertEqual(by_co[1].chunk_count, 2)
        self.assertFalse(by_co[1].warning)
        self.assertEqual(by_co[3].chunk_count, 0)
        self.assertTrue(by_co[3].warning)
        self.assertEqual(by_co[3].message, "No slides are mapped to CO3.")
        self.assertIsNone(by_co[1].message)

    def test_a_chunk_counts_once_per_co(self):
        [r] = coverage([1], [("a", 1), ("a", 1)])
        self.assertEqual(r.chunk_count, 1)

    def test_links_to_unknown_cos_are_ignored(self):
        result = coverage([1], [("a", 1), ("b", 7)])
        self.assertEqual([(r.co, r.chunk_count) for r in result], [(1, 1)])

    def test_results_are_sorted_by_co(self):
        self.assertEqual([r.co for r in coverage([3, 1, 2], [])], [1, 2, 3])

    def test_works_end_to_end_with_an_upload(self):
        store = InMemoryChunkStore()

        def tagger(chunks, cos):
            return [{"chunk_id": c.id, "cos": [1 if c.slide_number < 4 else 2]} for c in chunks]

        process_module_upload("M1", deck(), COS, tagger, store)
        by_co = {r.co: r.chunk_count for r in coverage([1, 2, 3], store.chunk_co_links())}
        self.assertEqual(by_co, {1: 2, 2: 1, 3: 0})


if __name__ == "__main__":
    unittest.main()
