"""Tests for scraper.py."""

from __future__ import annotations

import textwrap
import unittest
from unittest.mock import MagicMock, patch

from scraper import (
    ScoreboardState,
    detect_changes,
    fetch_scoreboard,
    parse_scoreboard_html,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_html(
    home_team: str = "Team A",
    away_team: str = "Team B",
    home_score: str = "0",
    away_score: str = "0",
    game_time: str = "00:00",
) -> str:
    """Return minimal HTML that matches the default CSS selectors."""
    return textwrap.dedent(f"""\
        <html>
        <body>
          <div class="home-name">{home_team}</div>
          <div class="away-name">{away_team}</div>
          <div class="home-score">{home_score}</div>
          <div class="away-score">{away_score}</div>
          <div class="clock">{game_time}</div>
        </body>
        </html>
    """)


# ---------------------------------------------------------------------------
# ScoreboardState tests
# ---------------------------------------------------------------------------

class TestScoreboardState(unittest.TestCase):
    def test_equality_same_fields(self):
        a = ScoreboardState(
            home_team="Lions", away_team="Eagles",
            home_score="3", away_score="2", game_time="25:00",
        )
        b = ScoreboardState(
            home_team="Lions", away_team="Eagles",
            home_score="3", away_score="2", game_time="25:00",
        )
        self.assertEqual(a, b)

    def test_equality_raw_text_ignored(self):
        """raw_text should NOT affect equality (it's metadata)."""
        a = ScoreboardState(home_team="X", away_team="Y", home_score="1",
                            away_score="0", game_time="10:00", raw_text="foo")
        b = ScoreboardState(home_team="X", away_team="Y", home_score="1",
                            away_score="0", game_time="10:00", raw_text="bar")
        self.assertEqual(a, b)

    def test_inequality_different_score(self):
        a = ScoreboardState(home_score="1", away_score="0")
        b = ScoreboardState(home_score="2", away_score="0")
        self.assertNotEqual(a, b)

    def test_summary(self):
        state = ScoreboardState(
            home_team="Lions", away_team="Eagles",
            home_score="3", away_score="2", game_time="25:00",
        )
        self.assertIn("Lions", state.summary())
        self.assertIn("Eagles", state.summary())
        self.assertIn("3", state.summary())
        self.assertIn("2", state.summary())
        self.assertIn("25:00", state.summary())

    def test_not_equal_to_non_state(self):
        state = ScoreboardState()
        self.assertNotEqual(state, "not a state")


# ---------------------------------------------------------------------------
# parse_scoreboard_html tests
# ---------------------------------------------------------------------------

class TestParseScoreboardHtml(unittest.TestCase):
    def test_parses_home_and_away_teams(self):
        html = _make_html(home_team="Lions", away_team="Eagles")
        state = parse_scoreboard_html(html)
        self.assertEqual(state.home_team, "Lions")
        self.assertEqual(state.away_team, "Eagles")

    def test_parses_scores(self):
        html = _make_html(home_score="7", away_score="5")
        state = parse_scoreboard_html(html)
        self.assertEqual(state.home_score, "7")
        self.assertEqual(state.away_score, "5")

    def test_parses_game_time(self):
        html = _make_html(game_time="30:00")
        state = parse_scoreboard_html(html)
        self.assertEqual(state.game_time, "30:00")

    def test_empty_html_returns_empty_state(self):
        state = parse_scoreboard_html("<html><body></body></html>")
        self.assertEqual(state.home_team, "")
        self.assertEqual(state.away_team, "")
        self.assertEqual(state.home_score, "")
        self.assertEqual(state.away_score, "")
        self.assertEqual(state.game_time, "")

    def test_raw_text_populated(self):
        html = _make_html(home_team="Lions")
        state = parse_scoreboard_html(html)
        self.assertIn("Lions", state.raw_text)


# ---------------------------------------------------------------------------
# fetch_scoreboard tests
# ---------------------------------------------------------------------------

class TestFetchScoreboard(unittest.TestCase):
    @patch("scraper.requests.get")
    def test_returns_parsed_state(self, mock_get):
        mock_response = MagicMock()
        mock_response.text = _make_html(
            home_team="Lions", away_team="Eagles",
            home_score="3", away_score="2", game_time="25:00",
        )
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        state = fetch_scoreboard("https://app.overlays.uno/output/test123")

        self.assertEqual(state.home_team, "Lions")
        self.assertEqual(state.away_team, "Eagles")
        self.assertEqual(state.home_score, "3")
        self.assertEqual(state.away_score, "2")

    @patch("scraper.requests.get")
    def test_raises_on_http_error(self, mock_get):
        import requests as req
        mock_get.side_effect = req.exceptions.HTTPError("404")
        with self.assertRaises(req.exceptions.HTTPError):
            fetch_scoreboard("https://app.overlays.uno/output/bad")


# ---------------------------------------------------------------------------
# detect_changes tests
# ---------------------------------------------------------------------------

class TestDetectChanges(unittest.TestCase):
    def _state(self, **kwargs) -> ScoreboardState:
        defaults = dict(
            home_team="Lions", away_team="Eagles",
            home_score="0", away_score="0", game_time="00:00",
        )
        defaults.update(kwargs)
        return ScoreboardState(**defaults)

    def test_first_observation_returns_initial_message(self):
        current = self._state()
        changes = detect_changes(None, current)
        self.assertEqual(len(changes), 1)
        self.assertIn("Initial", changes[0])

    def test_no_change_returns_empty_list(self):
        state = self._state(home_score="2", away_score="1")
        changes = detect_changes(state, self._state(home_score="2", away_score="1"))
        self.assertEqual(changes, [])

    def test_score_change_detected(self):
        prev = self._state(home_score="1", away_score="0")
        curr = self._state(home_score="2", away_score="0")
        changes = detect_changes(prev, curr)
        self.assertTrue(any("Score" in c for c in changes))

    def test_time_change_detected(self):
        prev = self._state(game_time="10:00")
        curr = self._state(game_time="11:00")
        changes = detect_changes(prev, curr)
        self.assertTrue(any("Time" in c for c in changes))

    def test_home_team_change_detected(self):
        prev = self._state(home_team="Old Team")
        curr = self._state(home_team="New Team")
        changes = detect_changes(prev, curr)
        self.assertTrue(any("Home team" in c for c in changes))

    def test_away_team_change_detected(self):
        prev = self._state(away_team="Old Team")
        curr = self._state(away_team="New Team")
        changes = detect_changes(prev, curr)
        self.assertTrue(any("Away team" in c for c in changes))

    def test_multiple_changes_detected(self):
        prev = self._state(home_score="0", away_score="0", game_time="10:00")
        curr = self._state(home_score="1", away_score="0", game_time="11:00")
        changes = detect_changes(prev, curr)
        self.assertGreaterEqual(len(changes), 2)


if __name__ == "__main__":
    unittest.main()
