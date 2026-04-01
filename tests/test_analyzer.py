"""Tests for analyzer.py."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from analyzer import build_prompt, get_insight
from scraper import ScoreboardState


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _state(
    home_team: str = "Lions",
    away_team: str = "Eagles",
    home_score: str = "3",
    away_score: str = "2",
    game_time: str = "25:00",
) -> ScoreboardState:
    return ScoreboardState(
        home_team=home_team,
        away_team=away_team,
        home_score=home_score,
        away_score=away_score,
        game_time=game_time,
    )


# ---------------------------------------------------------------------------
# build_prompt tests
# ---------------------------------------------------------------------------

class TestBuildPrompt(unittest.TestCase):
    def test_prompt_contains_current_score(self):
        current = _state(home_score="5", away_score="3")
        prompt = build_prompt(current, ["Score update: Lions 5 x 3 Eagles"])
        self.assertIn("5", prompt)
        self.assertIn("3", prompt)

    def test_prompt_contains_changes(self):
        changes = ["Score update: Lions 2 x 1 Eagles", "Time update: 20:00"]
        prompt = build_prompt(_state(), changes)
        for change in changes:
            self.assertIn(change, prompt)

    def test_prompt_includes_history_when_provided(self):
        history = [_state(home_score="0", away_score="0", game_time="00:00")]
        prompt = build_prompt(_state(), ["Some change"], history=history)
        self.assertIn("history", prompt.lower())

    def test_prompt_limits_history_to_last_five(self):
        history = [_state(game_time=f"{i:02d}:00") for i in range(10)]
        prompt = build_prompt(_state(), ["change"], history=history)
        # Only the last 5 entries should appear
        self.assertNotIn("00:00", prompt)
        self.assertIn("09:00", prompt)

    def test_prompt_without_history(self):
        prompt = build_prompt(_state(), ["Initial scoreboard"])
        self.assertIn("Initial scoreboard", prompt)
        self.assertNotIn("history", prompt.lower())


# ---------------------------------------------------------------------------
# get_insight tests
# ---------------------------------------------------------------------------

class TestGetInsight(unittest.TestCase):
    def _make_client(self, response_text: str) -> MagicMock:
        """Return a mock OpenAI client that yields *response_text*."""
        mock_client = MagicMock()
        mock_message = MagicMock()
        mock_message.content = response_text
        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_client.chat.completions.create.return_value = mock_response
        return mock_client

    def test_returns_insight_string(self):
        client = self._make_client("  Great goal by Lions!  ")
        result = get_insight(_state(), ["Score update"], client=client)
        self.assertEqual(result, "Great goal by Lions!")

    def test_calls_openai_with_correct_model(self):
        client = self._make_client("insight")
        get_insight(_state(), ["change"], model="gpt-4o", client=client)
        call_kwargs = client.chat.completions.create.call_args
        self.assertEqual(call_kwargs.kwargs["model"], "gpt-4o")

    def test_passes_history_to_prompt(self):
        client = self._make_client("insight")
        history = [_state(game_time="10:00")]
        get_insight(_state(), ["change"], history=history, client=client)
        call_kwargs = client.chat.completions.create.call_args
        messages = call_kwargs.kwargs["messages"]
        user_content = next(m["content"] for m in messages if m["role"] == "user")
        self.assertIn("history", user_content.lower())

    def test_system_prompt_is_included(self):
        client = self._make_client("insight")
        get_insight(_state(), ["change"], client=client)
        call_kwargs = client.chat.completions.create.call_args
        messages = call_kwargs.kwargs["messages"]
        system_msgs = [m for m in messages if m["role"] == "system"]
        self.assertTrue(len(system_msgs) > 0)
        self.assertIn("handball", system_msgs[0]["content"].lower())


if __name__ == "__main__":
    unittest.main()
