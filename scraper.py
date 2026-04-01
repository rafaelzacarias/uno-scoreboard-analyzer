"""Scraper module for fetching and parsing Singular.live control-app JSON."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Optional

import requests

# Base URL template – the token is inserted at runtime.
API_URL_TEMPLATE = "https://app.singular.live/apiv2/controlapps/{token}/control"


@dataclass
class ScoreboardState:
    """Represents a single snapshot of the scoreboard."""

    home_team: str = ""
    away_team: str = ""
    home_score: str = ""
    away_score: str = ""
    game_time: str = ""
    period: str = ""
    raw_payload: dict = field(default_factory=dict)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ScoreboardState):
            return NotImplemented
        return (
            self.home_team == other.home_team
            and self.away_team == other.away_team
            and self.home_score == other.home_score
            and self.away_score == other.away_score
            and self.game_time == other.game_time
            and self.period == other.period
        )

    def __repr__(self) -> str:
        return (
            f"ScoreboardState("
            f"home_team={self.home_team!r}, "
            f"away_team={self.away_team!r}, "
            f"home_score={self.home_score!r}, "
            f"away_score={self.away_score!r}, "
            f"game_time={self.game_time!r}, "
            f"period={self.period!r})"
        )

    def summary(self) -> str:
        """Return a human-readable summary of the current scoreboard state."""
        period_str = f" | Period: {self.period}" if self.period else ""
        return (
            f"{self.home_team} {self.home_score} x {self.away_score} {self.away_team}"
            f" | Time: {self.game_time}{period_str}"
        )


def build_api_url(token: str) -> str:
    """Build the Singular.live control-app API URL from a token.

    Parameters
    ----------
    token:
        The UNO / Singular.live control-app token.

    Returns
    -------
    str
        Fully-qualified API URL.
    """
    return API_URL_TEMPLATE.format(token=token)


def _resolve_period_name(payload: dict, period_key: str) -> str:
    """Map a period key like ``p1`` to its display name using the payload setup fields."""
    mapping = {
        "p1": payload.get("PeriodSetupP1Name", "1st"),
        "p2": payload.get("PeriodSetupP2Name", "2nd"),
        "ot1": payload.get("PeriodSetupOT1Name", "OT"),
        "ot2": payload.get("PeriodSetupOT2Name", "OT2"),
    }
    return mapping.get(period_key, period_key)


def parse_scoreboard_json(data: list[dict[str, Any]]) -> ScoreboardState:
    """Parse the Singular.live control-app JSON response.

    The response is a JSON array of sub-compositions.  The ``Content``
    sub-composition contains the scoreboard payload with keys such as
    ``NameTeam1``, ``GoalsTeam1``, ``MatchTimeText``, etc.

    Parameters
    ----------
    data:
        Parsed JSON list (array of sub-composition dicts).

    Returns
    -------
    ScoreboardState
        Extracted scoreboard data.  Fields that could not be found will be
        empty strings.
    """
    # Find the "Content" sub-composition
    payload: dict[str, Any] = {}
    for entry in data:
        if entry.get("subCompositionName") == "Content":
            payload = entry.get("payload", {})
            break

    period_key = str(payload.get("Period", ""))
    period_name = _resolve_period_name(payload, period_key)

    return ScoreboardState(
        home_team=str(payload.get("NameTeam1", "")),
        away_team=str(payload.get("NameTeam2", "")),
        home_score=str(payload.get("GoalsTeam1", "")),
        away_score=str(payload.get("GoalsTeam2", "")),
        game_time=str(payload.get("MatchTimeText", "")),
        period=period_name,
        raw_payload=payload,
    )


def fetch_scoreboard(url: str, timeout: int = 15) -> ScoreboardState:
    """Fetch the Singular.live control-app JSON and return a parsed state.

    Parameters
    ----------
    url:
        Full API URL, e.g.
        ``https://app.singular.live/apiv2/controlapps/<TOKEN>/control``.
    timeout:
        HTTP request timeout in seconds.

    Returns
    -------
    ScoreboardState
        Parsed scoreboard data.

    Raises
    ------
    requests.RequestException
        If the HTTP request fails.
    ValueError
        If the response is not valid JSON.
    """
    headers = {
        "Accept": "application/json",
    }

    response = requests.get(url, headers=headers, timeout=timeout)
    response.raise_for_status()

    data = response.json()
    if not isinstance(data, list):
        raise ValueError(f"Expected a JSON array, got {type(data).__name__}")

    return parse_scoreboard_json(data)


def detect_changes(
    previous: Optional[ScoreboardState], current: ScoreboardState
) -> list[str]:
    """Return a list of human-readable descriptions of what changed between two states.

    Parameters
    ----------
    previous:
        The previously observed scoreboard state. If *None*, the current state
        is treated as the first observation.
    current:
        The most recently fetched scoreboard state.

    Returns
    -------
    list[str]
        Descriptions of each detected change. An empty list means no changes.
    """
    if previous is None:
        return [f"Initial scoreboard: {current.summary()}"]

    changes: list[str] = []

    if previous.home_score != current.home_score or previous.away_score != current.away_score:
        changes.append(
            f"Score update: {current.home_team} {current.home_score} x "
            f"{current.away_score} {current.away_team} "
            f"(was {previous.home_score} x {previous.away_score})"
        )

    if previous.game_time != current.game_time:
        changes.append(
            f"Time update: {current.game_time} (was {previous.game_time})"
        )

    if previous.home_team != current.home_team:
        changes.append(
            f"Home team changed: {previous.home_team!r} → {current.home_team!r}"
        )

    if previous.away_team != current.away_team:
        changes.append(
            f"Away team changed: {previous.away_team!r} → {current.away_team!r}"
        )

    if previous.period != current.period:
        changes.append(
            f"Period changed: {previous.period!r} → {current.period!r}"
        )

    return changes
