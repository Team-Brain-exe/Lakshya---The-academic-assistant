import io
import unittest

from pptx import Presentation

from app.pipeline.ppt import PptParseError, parse_pptx
from helpers import build_deck


class ParsePptxTests(unittest.TestCase):
    def setUp(self):
        self.deck = parse_pptx(io.BytesIO(build_deck()))
        self.by_number = {c.slide_number: c.text for c in self.deck.chunks}

    def test_one_chunk_per_slide_with_text(self):
        self.assertEqual([c.slide_number for c in self.deck.chunks], [1, 2, 4])
        self.assertEqual(self.deck.total_slides, 4)

    def test_empty_slides_are_skipped_and_reported(self):
        self.assertEqual(self.deck.skipped_slides, (3,))

    def test_title_comes_first_then_body(self):
        lines = self.by_number[1].split("\n")
        self.assertEqual(lines[0], "Hash tables")
        self.assertIn("Keys map to buckets", lines)
        self.assertIn("Collisions need a strategy", lines)

    def test_speaker_notes_are_included(self):
        self.assertIn("Speaker notes: Mention load factor", self.by_number[1])

    def test_notes_can_be_left_out(self):
        deck = parse_pptx(io.BytesIO(build_deck()), include_notes=False)
        self.assertNotIn("Speaker notes", deck.chunks[0].text)

    def test_text_boxes_tables_and_groups_are_read(self):
        text = self.by_number[2]
        self.assertIn("Chaining vs probing", text)
        self.assertIn("Method | Cost", text)
        self.assertIn("Chaining | O(1) average", text)
        self.assertIn("Grouped note", text)

    def test_title_only_slide_is_kept(self):
        self.assertEqual(self.by_number[4], "Summary")

    def test_reads_from_a_file_path(self):
        import tempfile, os

        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "deck.pptx")
            with open(path, "wb") as f:
                f.write(build_deck())
            deck = parse_pptx(path)
        self.assertEqual(len(deck.chunks), 3)

    def test_a_file_that_is_not_a_pptx_is_rejected_clearly(self):
        with self.assertRaises(PptParseError):
            parse_pptx(io.BytesIO(b"this is not a presentation"))

    def test_an_empty_presentation_gives_no_chunks(self):
        buf = io.BytesIO()
        Presentation().save(buf)
        deck = parse_pptx(io.BytesIO(buf.getvalue()))
        self.assertEqual((deck.chunks, deck.skipped_slides, deck.total_slides), ((), (), 0))


if __name__ == "__main__":
    unittest.main()
