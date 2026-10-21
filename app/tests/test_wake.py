"""Run with:  python -m unittest discover -s tests   (from the app folder)"""

import os
import sys
import unittest
from unittest import mock

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from frog_voice import wake as wake_mod  # noqa: E402
from frog_voice.wake import BLOCK, Segmenter, extract_after_wake_word, is_noise  # noqa: E402


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
    def test_matches_the_word_anywhere_and_returns_whats_after_it(self):
        cases = {
            "brainfrog how is it going": "how is it going",
            "hey brainfrog": "",
            "ok brainfrog, what's up": "what s up",  # normalize() splits "what's" on the apostrophe
            "BrainFrog! tell me a joke": "tell me a joke",
            "hey, brain frog, you there": "you there",  # split into two words by speech recognition
        }
        for text, expected in cases.items():
            self.assertEqual(extract_after_wake_word(text, "brainfrog"), expected, text)

    def test_returns_none_for_unrelated_speech(self):
        for text in ("that was a great play", "chat is going wild", "brain surgery is hard"):
            self.assertIsNone(extract_after_wake_word(text, "brainfrog"), text)

    def test_a_custom_wake_word_is_respected(self):
        self.assertEqual(extract_after_wake_word("hey froggy how are you", "froggy"), "how are you")
        self.assertIsNone(extract_after_wake_word("hey froggy how are you", "brainfrog"))

    def test_empty_wake_word_never_matches(self):
        self.assertIsNone(extract_after_wake_word("anything at all", ""))


class Noise(unittest.TestCase):
    def test_common_misheard_silence_is_noise(self):
        for text in ("", "  ", "thanks for watching", "thank you", "um", "okay"):
            self.assertTrue(is_noise(text))

    def test_real_speech_is_not_noise(self):
        self.assertFalse(is_noise("what is chat saying"))


class FakeEngine:
    def __init__(self):
        self.calls = []

    def note(self, kind, text):
        pass

    def read_now(self):
        self.calls.append(("read_now",))

    def ask(self, question):
        self.calls.append(("ask", question))


class Dispatch(unittest.TestCase):
    """What _handle does with a transcribed utterance -- exercised directly,
    with transcription stubbed out, so no real audio is needed."""

    def listener(self):
        listener = wake_mod.WakeListener(FakeEngine())
        listener._cfg = {"whisper_model_size": "x", "wake_word": "brainfrog"}
        return listener

    def run_with(self, heard):
        listener = self.listener()
        with mock.patch("frog_voice.speech_io.transcribe", lambda audio, model: heard):
            listener._handle(None)
        return listener.engine.calls

    def test_a_chat_request_reads_chat_even_with_the_wake_word(self):
        self.assertEqual(self.run_with("brainfrog, what's chat saying"), [("read_now",)])

    def test_a_chat_request_works_without_the_wake_word_too(self):
        self.assertEqual(self.run_with("what's chat saying"), [("read_now",)])

    def test_wake_word_plus_a_question_starts_a_conversation_instead(self):
        self.assertEqual(self.run_with("brainfrog how is it going"), [("ask", "how is it going")])

    def test_wake_word_alone_still_starts_a_conversation(self):
        self.assertEqual(self.run_with("hey brainfrog"), [("ask", "Hello?")])

    def test_neither_is_ignored(self):
        self.assertEqual(self.run_with("nice shot there"), [])

    def test_noise_is_ignored_before_either_check(self):
        self.assertEqual(self.run_with("thanks for watching"), [])


if __name__ == "__main__":
    unittest.main()
