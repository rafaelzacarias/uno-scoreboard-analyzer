"""Tests for app.py – game reset detection and analyzer loop helpers."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from scraper import ScoreboardState

# Import after path setup (conftest.py handles this)
from app import _is_game_reset


class TestIsGameReset(unittest.TestCase):
    def _state(self, home_score: str = "0", away_score: str = "0", **kw) -> ScoreboardState:
        defaults = dict(home_team="A", away_team="B", game_time="00:00")
        defaults.update(kw)
        return ScoreboardState(home_score=home_score, away_score=away_score, **defaults)

    def test_no_previous_not_reset(self):
        self.assertFalse(_is_game_reset(None, self._state()))

    def test_zero_to_zero_not_reset(self):
        prev = self._state("0", "0")
        curr = self._state("0", "0")
        self.assertFalse(_is_game_reset(prev, curr))

    def test_score_drops_to_zero(self):
        prev = self._state("5", "3")
        curr = self._state("0", "0")
        self.assertTrue(_is_game_reset(prev, curr))

    def test_only_home_had_score(self):
        prev = self._state("2", "0")
        curr = self._state("0", "0")
        self.assertTrue(_is_game_reset(prev, curr))

    def test_only_away_had_score(self):
        prev = self._state("0", "1")
        curr = self._state("0", "0")
        self.assertTrue(_is_game_reset(prev, curr))

    def test_score_increase_not_reset(self):
        prev = self._state("1", "0")
        curr = self._state("2", "0")
        self.assertFalse(_is_game_reset(prev, curr))

    def test_empty_string_scores_treated_as_zero(self):
        prev = self._state("3", "2")
        curr = self._state("", "")
        self.assertTrue(_is_game_reset(prev, curr))


if __name__ == "__main__":
    unittest.main()
