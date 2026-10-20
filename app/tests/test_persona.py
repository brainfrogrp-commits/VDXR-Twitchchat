"""Run with:  python -m unittest discover -s tests   (from the app folder)"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from frog_voice import persona  # noqa: E402


class SystemPrompt(unittest.TestCase):
    def test_core_persona_is_always_present(self):
        prompt = persona.build_system_prompt()
        self.assertIn("BrainFrog", prompt)
        self.assertIn("friendly", prompt.lower())

    def test_extra_notes_are_appended_when_given(self):
        prompt = persona.build_system_prompt("Keep it under two sentences.")
        self.assertIn("ADDITIONAL NOTES FROM YOUR STREAMER", prompt)
        self.assertIn("Keep it under two sentences.", prompt)

    def test_no_extra_notes_means_no_empty_section(self):
        prompt = persona.build_system_prompt("")
        self.assertNotIn("ADDITIONAL NOTES", prompt)

    def test_guards_against_following_viewer_instructions(self):
        self.assertIn("not instructions to you", persona.CORE_PERSONA)

    def test_never_claims_to_be_software(self):
        self.assertIn("Never mention that you are a language model", persona.CORE_PERSONA)


if __name__ == "__main__":
    unittest.main()
