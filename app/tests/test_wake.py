"""Run with:  python -m unittest discover -s tests   (from the app folder)"""

import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from frog_voice.wake import BLOCK, Segmenter, is_noise, mentions_wake_word  # noqa: E402


def run(blocks):
    """blocks: list of (loudness, seconds). Feeds them in and returns utterances."""
    seg, out, now = Segmenter(threshold=0.02, silence_s=0.8), [], 0.0
    for level, seconds in blocks:
        for _ in range(int(seconds / 0.064)):
            block = np.full(BLOCK, level, dtype="float32")
            audio = seg.feed(block, now)
            now += 0.064
            if audio is not None:
                out.append(audio)
    return out


class Segmentation(unittest.TestCase):
    def test_speech_between_silence_is_one_utterance(self):
        self.assertEqual(len(run([(0.0, 1.0), (0.1, 1.5), (0.0, 2.0)])), 1)

    def test_quiet_room_makes_nothing(self):
        self.assertEqual(run([(0.005, 5.0)]), [])

    def test_short_click_is_ignored(self):
        self.assertEqual(run([(0.0, 1.0), (0.2, 0.15), (0.0, 2.0)]), [])

    def test_two_sentences_with_a_long_pause_are_two(self):
        self.assertEqual(len(run([(0.1, 1.0), (0.0, 1.5), (0.1, 1.0), (0.0, 1.5)])), 2)

    def test_short_pause_does_not_split(self):
        self.assertEqual(len(run([(0.1, 1.0), (0.0, 0.4), (0.1, 1.0), (0.0, 1.5)])), 1)


class WakeWord(unittest.TestCase):
    def test_matches_the_word_anywhere_in_the_sentence(self):
        for text in ("brainfrog read me chat", "hey brainfrog", "ok brainfrog, what's up",
                     "BrainFrog!", "hey, brain frog, you there"):
            self.assertTrue(mentions_wake_word(text, "brainfrog"), text)

    def test_does_not_match_unrelated_speech(self):
        for text in ("that was a great play", "chat is going wild", "brain surgery is hard"):
            self.assertFalse(mentions_wake_word(text, "brainfrog"), text)

    def test_a_custom_wake_word_is_respected(self):
        self.assertTrue(mentions_wake_word("hey froggy can you check chat", "froggy"))
        self.assertFalse(mentions_wake_word("hey froggy can you check chat", "brainfrog"))

    def test_empty_wake_word_never_matches(self):
        self.assertFalse(mentions_wake_word("anything at all", ""))


class Noise(unittest.TestCase):
    def test_common_misheard_silence_is_noise(self):
        for text in ("", "  ", "thanks for watching", "thank you", "um", "okay"):
            self.assertTrue(is_noise(text))

    def test_real_speech_is_not_noise(self):
        self.assertFalse(is_noise("what is chat saying"))


if __name__ == "__main__":
    unittest.main()
