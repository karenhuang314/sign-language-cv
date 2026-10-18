"""Practice rules, independent of Qt, webcam, and MediaPipe."""

import random

from features import MOTION_LETTERS

HOLD_SECONDS = 0.6
FEEDBACK_SECONDS = 1.5
MAX_SAMPLE_GAP = 0.6


class PracticeController:
    def __init__(self, letters):
        self.letters = tuple(sorted(set(letters)))
        if not self.letters:
            raise ValueError("No practice letters are available.")
        self.reset()

    def _choose(self):
        if self.focus != "Random":
            return self.focus
        return random.choice([x for x in self.letters if x != self.target] or self.letters)

    def clear_evidence(self):
        self.matching_since = None
        self.matching_samples = 0
        self.last_sample = None

    def reset(self, focus="Random"):
        if focus != "Random" and focus not in self.letters:
            raise ValueError(f"Unsupported practice letter: {focus}")
        self.focus = focus
        self.target = None
        self.target = self._choose()
        self.score = 0
        self.correct_until = 0.0
        self.accepted_letter = None
        self.release_needed = False
        self.clear_evidence()

    def skip(self):
        self.target = self._choose()
        self.correct_until = 0.0
        self.release_needed = False
        self.accepted_letter = None
        self.clear_evidence()

    def advance(self, now):
        if self.correct_until and now >= self.correct_until:
            self.correct_until = 0.0
            self.target = self._choose()
            self.clear_evidence()

    def observe(self, letter, motion_event, now):
        """Return True only on a newly accepted sign, never from a held result."""
        self.advance(now)
        if self.release_needed and letter != self.accepted_letter:
            self.release_needed = False
        if self.correct_until or self.release_needed:
            self.clear_evidence()
            return False
        if self.last_sample is not None and now - self.last_sample > MAX_SAMPLE_GAP:
            self.clear_evidence()
        self.last_sample = now
        if letter != self.target:
            self.matching_since = None
            self.matching_samples = 0
            return False
        if self.target in MOTION_LETTERS:
            accepted = motion_event
        else:
            if self.matching_since is None:
                self.matching_since = now
            self.matching_samples += 1
            accepted = (now - self.matching_since >= HOLD_SECONDS
                        and self.matching_samples >= 3)
        if not accepted:
            return False
        self.score += 1
        self.accepted_letter = letter
        self.release_needed = True
        self.correct_until = now + FEEDBACK_SECONDS
        self.clear_evidence()
        return True

    def progress(self, now):
        if self.correct_until:
            return 100
        if self.matching_since is None:
            return 0
        # A quiet/stopped stream cannot turn a stale observation into a success.
        if self.last_sample is None or now - self.last_sample > MAX_SAMPLE_GAP:
            return 0
        return min(99, int(100 * (now - self.matching_since) / HOLD_SECONDS))

    def instruction(self, now):
        if self.correct_until and now < self.correct_until:
            return "Correct! Nicely done."
        if self.release_needed:
            return "Relax or lower your hand before the next attempt."
        if self.target == "J":
            return "Draw J with your pinky over about 1–2 seconds."
        if self.target == "Z":
            return "Draw Z with your index finger over about 1–2 seconds."
        return "Hold the matching sign steadily for about 0.6 seconds."
