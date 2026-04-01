"""Scraper module for fetching and parsing UNO scoreboard overlay pages."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional

import requests
from bs4 import BeautifulSoup


@dataclass
class ScoreboardState:
    """Represents a single snapshot of the scoreboard."""

    home_team: str = ""
    away_team: str = ""
    home_score: str = ""
    away_score: str = ""
    game_time: str = ""
    raw_text: str = ""

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ScoreboardState):
            return NotImplemented
        return (
            self.home_team == other.home_team
            and self.away_team == other.away_team
            and self.home_score == other.home_score
            and self.away_score == other.away_score
            and self.game_time == other.game_time
        )

    def __repr__(self) -> str:
        return (
            f"ScoreboardState("
            f"home_team={self.home_team!r}, "
            f"away_team={self.away_team!r}, "
            f"home_score={self.home_score!r}, "
            f"away_score={self.away_score!r}, "
            f"game_time={self.game_time!r})"
        )

    def summary(self) -> str:
        """Return a human-readable summary of the current scoreboard state."""
        return (
            f"{self.home_team} {self.home_score} x {self.away_score} {self.away_team}"
            f" | Time: {self.game_time}"
        )


# CSS selectors used to locate scoreboard elements inside the overlay page.
# These defaults target common class names used by overlays.uno scoreboard
# templates. Override them if the page uses different identifiers.
DEFAULT_SELECTORS = {
    "home_team": [
        "[class*='home'][class*='name']",
        "[class*='team-home'] [class*='name']",
        "[class*='home-team']",
        "[data-team='home'] [class*='name']",
        "[class*='teamName']:first-child",
    ],
    "away_team": [
        "[class*='away'][class*='name']",
        "[class*='team-away'] [class*='name']",
        "[class*='away-team']",
        "[data-team='away'] [class*='name']",
        "[class*='teamName']:last-child",
    ],
    "home_score": [
        "[class*='home'][class*='score']",
        "[class*='team-home'] [class*='score']",
        "[class*='score-home']",
        "[data-team='home'] [class*='score']",
    ],
    "away_score": [
        "[class*='away'][class*='score']",
        "[class*='team-away'] [class*='score']",
        "[class*='score-away']",
        "[data-team='away'] [class*='score']",
    ],
    "game_time": [
        "[class*='clock']",
        "[class*='timer']",
        "[class*='time']",
        "[class*='period']",
    ],
}


def _first_text(soup: BeautifulSoup, selectors: list[str]) -> str:
    """Try each CSS selector in order and return the first non-empty text found."""
    for selector in selectors:
        try:
            element = soup.select_one(selector)
            if element:
                text = element.get_text(strip=True)
                if text:
                    return text
        except Exception:
            continue
    return ""


def fetch_scoreboard(url: str, timeout: int = 15) -> ScoreboardState:
    """Fetch the scoreboard overlay page and return a parsed :class:`ScoreboardState`.

    Parameters
    ----------
    url:
        Full URL to the overlays.uno output page, e.g.
        ``https://app.overlays.uno/output/0ZtIYoE5lp1X1rceb5MV5s``.
    timeout:
        HTTP request timeout in seconds.

    Returns
    -------
    ScoreboardState
        Parsed scoreboard data. Fields that could not be extracted will be
        empty strings.

    Raises
    ------
    requests.RequestException
        If the HTTP request fails.
    """
    headers = {
        # Standard browser User-Agent so the overlay page does not reject the request.
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    response = requests.get(url, headers=headers, timeout=timeout)
    response.raise_for_status()

    return parse_scoreboard_html(response.text)


def parse_scoreboard_html(html: str) -> ScoreboardState:
    """Parse raw HTML from an overlays.uno output page into a :class:`ScoreboardState`.

    Parameters
    ----------
    html:
        Raw HTML string returned by the overlay page.

    Returns
    -------
    ScoreboardState
        Extracted scoreboard data.
    """
    soup = BeautifulSoup(html, "html.parser")

    state = ScoreboardState(
        home_team=_first_text(soup, DEFAULT_SELECTORS["home_team"]),
        away_team=_first_text(soup, DEFAULT_SELECTORS["away_team"]),
        home_score=_first_text(soup, DEFAULT_SELECTORS["home_score"]),
        away_score=_first_text(soup, DEFAULT_SELECTORS["away_score"]),
        game_time=_first_text(soup, DEFAULT_SELECTORS["game_time"]),
        raw_text=soup.get_text(separator=" ", strip=True),
    )

    return state


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

    return changes
