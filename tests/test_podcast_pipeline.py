import unittest

from agents.podcast.state import MAX_SEGMENT_WORDS, MIN_SEGMENT_WORDS, clamp_words, segment_budget


class PodcastPipelineTests(unittest.TestCase):
    def test_segment_budget_is_clamped(self):
        self.assertEqual(segment_budget(1200, 1), MAX_SEGMENT_WORDS)
        self.assertEqual(segment_budget(1200, 4), 300)
        self.assertEqual(segment_budget(100, 8), MIN_SEGMENT_WORDS)


    def test_clamp_words_enforces_hard_limit(self):
        self.assertEqual(clamp_words("one two three four", 2), "one two")