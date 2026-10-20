import unittest

from app.engine.settings import GradingSettings, load_grading_settings


class SettingsTests(unittest.TestCase):
    def test_defaults_to_best_and_two_attempts(self):
        s = load_grading_settings({})
        self.assertEqual(s.attempt_rule, "best")
        self.assertEqual(s.max_attempts, 2)

    def test_empty_values_fall_back_to_defaults(self):
        s = load_grading_settings({"ATTEMPT_RULE": "", "MAX_ATTEMPTS": ""})
        self.assertEqual((s.attempt_rule, s.max_attempts), ("best", 2))

    def test_reads_values_case_insensitively(self):
        s = load_grading_settings({"ATTEMPT_RULE": " Latest ", "MAX_ATTEMPTS": "3"})
        self.assertEqual((s.attempt_rule, s.max_attempts), ("latest", 3))

    def test_rejects_unknown_rule(self):
        with self.assertRaises(ValueError):
            load_grading_settings({"ATTEMPT_RULE": "median"})

    def test_rejects_bad_max_attempts(self):
        with self.assertRaises(ValueError):
            load_grading_settings({"MAX_ATTEMPTS": "two"})
        with self.assertRaises(ValueError):
            GradingSettings(max_attempts=0)


if __name__ == "__main__":
    unittest.main()
