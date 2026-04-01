"""Tests for scraper.py."""

from __future__ import annotations

import json
import unittest
from unittest.mock import MagicMock, patch

from scraper import (
    ScoreboardState,
    build_api_url,
    detect_changes,
    fetch_scoreboard,
    parse_scoreboard_json,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_api_response(
    home_team: str = "Team A",
    away_team: str = "Team B",
    home_score: int = 0,
    away_score: int = 0,
    game_time: str = "00:00",
    period: str = "p1",
) -> list[dict]:
    """Return a minimal Singular.live control-app JSON response."""
    return [
        {
            "subCompositionId": "main-id",
            "subCompositionName": "mainComposition",
            "mainComposition": True,
            "state": "Out1",
            "payload": {},
        },
        {
            "subCompositionId": "content-id",
            "subCompositionName": "Content",
            "mainComposition": False,
            "state": "Out1",
            "payload": {
                "NameTeam1": home_team,
                "NameTeam2": away_team,
                "GoalsTeam1": home_score,
                "GoalsTeam2": away_score,
                "MatchTimeText": game_time,
                "Period": period,
                "PeriodSetupP1Name": "1st",
                "PeriodSetupP2Name": "2nd",
                "PeriodSetupOT1Name": "OT",
                "PeriodSetupOT2Name": "OT2",
            },
        },
    ]


# ---------------------------------------------------------------------------
# build_api_url tests
# ---------------------------------------------------------------------------

class TestBuildApiUrl(unittest.TestCase):
    def test_builds_correct_url(self):
        url = build_api_url("abc123")
        self.assertEqual(
            url,
            "https://app.singular.live/apiv2/controlapps/abc123/control",
        )

    def test_token_with_special_chars(self):
        url = build_api_url("-OMfUoxr9YGFLw3zp9pu")
        self.assertIn("-OMfUoxr9YGFLw3zp9pu", url)


# ---------------------------------------------------------------------------
# ScoreboardState tests
# ---------------------------------------------------------------------------

class TestScoreboardState(unittest.TestCase):
    def test_equality_same_fields(self):
        a = ScoreboardState(
            home_team="Lions", away_team="Eagles",
            home_score="3", away_score="2", game_time="25:00", period="1st",
        )
        b = ScoreboardState(
            home_team="Lions", away_team="Eagles",
            home_score="3", away_score="2", game_time="25:00", period="1st",
        )
        self.assertEqual(a, b)

    def test_equality_raw_payload_ignored(self):
        """raw_payload should NOT affect equality (it's metadata)."""
        a = ScoreboardState(home_team="X", away_team="Y", home_score="1",
                            away_score="0", game_time="10:00",
                            raw_payload={"foo": 1})
        b = ScoreboardState(home_team="X", away_team="Y", home_score="1",
                            away_score="0", game_time="10:00",
                            raw_payload={"bar": 2})
        self.assertEqual(a, b)

    def test_inequality_different_score(self):
        a = ScoreboardState(home_score="1", away_score="0")
        b = ScoreboardState(home_score="2", away_score="0")
        self.assertNotEqual(a, b)

    def test_summary(self):
        state = ScoreboardState(
            home_team="Lions", away_team="Eagles",
            home_score="3", away_score="2", game_time="25:00", period="1st",
        )
        self.assertIn("Lions", state.summary())
        self.assertIn("Eagles", state.summary())
        self.assertIn("3", state.summary())
        self.assertIn("2", state.summary())
        self.assertIn("25:00", state.summary())
        self.assertIn("1st", state.summary())

    def test_not_equal_to_non_state(self):
        state = ScoreboardState()
        self.assertNotEqual(state, "not a state")


# ---------------------------------------------------------------------------
# parse_scoreboard_json tests
# ---------------------------------------------------------------------------

class TestParseScoreboardJson(unittest.TestCase):
    def test_parses_home_and_away_teams(self):
        data = _make_api_response(home_team="CROATIA", away_team="GREECE")
        state = parse_scoreboard_json(data)
        self.assertEqual(state.home_team, "CROATIA")
        self.assertEqual(state.away_team, "GREECE")

    def test_parses_scores(self):
        data = _make_api_response(home_score=7, away_score=5)
        state = parse_scoreboard_json(data)
        self.assertEqual(state.home_score, "7")
        self.assertEqual(state.away_score, "5")

    def test_parses_game_time(self):
        data = _make_api_response(game_time="30:00")
        state = parse_scoreboard_json(data)
        self.assertEqual(state.game_time, "30:00")

    def test_parses_period(self):
        data = _make_api_response(period="p2")
        state = parse_scoreboard_json(data)
        self.assertEqual(state.period, "2nd")

    def test_parses_overtime_period(self):
        data = _make_api_response(period="ot1")
        state = parse_scoreboard_json(data)
        self.assertEqual(state.period, "OT")

    def test_empty_content_returns_empty_state(self):
        data = [
            {
                "subCompositionId": "some-id",
                "subCompositionName": "SomethingElse",
                "payload": {},
            }
        ]
        state = parse_scoreboard_json(data)
        self.assertEqual(state.home_team, "")
        self.assertEqual(state.away_team, "")
        self.assertEqual(state.home_score, "")
        self.assertEqual(state.away_score, "")
        self.assertEqual(state.game_time, "")

    def test_raw_payload_populated(self):
        data = _make_api_response(home_team="Lions")
        state = parse_scoreboard_json(data)
        self.assertEqual(state.raw_payload["NameTeam1"], "Lions")

    def test_no_content_composition(self):
        """When the Content sub-composition is missing entirely."""
        state = parse_scoreboard_json([])
        self.assertEqual(state.home_team, "")


# ---------------------------------------------------------------------------
# fetch_scoreboard tests
# ---------------------------------------------------------------------------

class TestFetchScoreboard(unittest.TestCase):
    @patch("scraper.requests.get")
    def test_returns_parsed_state(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = _make_api_response(
            home_team="CROATIA", away_team="GREECE",
            home_score=3, away_score=2, game_time="25:00",
        )
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        url = build_api_url("test-token")
        state = fetch_scoreboard(url)

        self.assertEqual(state.home_team, "CROATIA")
        self.assertEqual(state.away_team, "GREECE")
        self.assertEqual(state.home_score, "3")
        self.assertEqual(state.away_score, "2")

    @patch("scraper.requests.get")
    def test_raises_on_http_error(self, mock_get):
        import requests as req
        mock_get.side_effect = req.exceptions.HTTPError("404")
        with self.assertRaises(req.exceptions.HTTPError):
            fetch_scoreboard(build_api_url("bad-token"))

    @patch("scraper.requests.get")
    def test_raises_on_non_list_response(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {"error": "not found"}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        with self.assertRaises(ValueError):
            fetch_scoreboard(build_api_url("bad-token"))


# ---------------------------------------------------------------------------
# detect_changes tests
# ---------------------------------------------------------------------------

class TestDetectChanges(unittest.TestCase):
    def _state(self, **kwargs) -> ScoreboardState:
        defaults = dict(
            home_team="Lions", away_team="Eagles",
            home_score="0", away_score="0", game_time="00:00", period="1st",
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

    def test_period_change_detected(self):
        prev = self._state(period="1st")
        curr = self._state(period="2nd")
        changes = detect_changes(prev, curr)
        self.assertTrue(any("Period" in c for c in changes))

    def test_multiple_changes_detected(self):
        prev = self._state(home_score="0", away_score="0", game_time="10:00")
        curr = self._state(home_score="1", away_score="0", game_time="11:00")
        changes = detect_changes(prev, curr)
        self.assertGreaterEqual(len(changes), 2)


if __name__ == "__main__":
    unittest.main()
