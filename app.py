"""Combined entry point: runs the scoreboard analyzer loop and the web
dashboard in a single process.

Usage (container / Azure):
    python app.py

Required environment variables:
    SCOREBOARD_URL   – overlays.uno output URL
    OPENAI_API_KEY   – OpenAI API key  (or set AZURE_OPENAI_* vars)

Optional Azure OpenAI variables (used instead of OPENAI_API_KEY when set):
    AZURE_OPENAI_ENDPOINT    – e.g. https://<resource>.openai.azure.com
    AZURE_OPENAI_KEY         – key for the Azure OpenAI resource
    AZURE_OPENAI_DEPLOYMENT  – deployment name (defaults to gpt-5.4-mini)
    AZURE_OPENAI_API_VERSION – API version (defaults to 2024-12-01-preview)
"""

from __future__ import annotations

import os
import sys
import threading
import time
from typing import Optional

from dotenv import load_dotenv

from analyzer import get_insight
from game_log import EventType, GameLog
from scraper import ScoreboardState, detect_changes, fetch_scoreboard
from web_app import create_app, set_game_log

load_dotenv()

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
POLL_INTERVAL: int = int(os.getenv("POLL_INTERVAL", "10"))
REQUEST_TIMEOUT: int = int(os.getenv("REQUEST_TIMEOUT", "15"))
OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-5.4-mini")
WEB_PORT: int = int(os.getenv("WEB_PORT", "8080"))
UNO_TICKER_TOKEN: str = os.getenv("UNO_TICKER_TOKEN", "")
MAX_HISTORY_SIZE: int = 20

# Scores that indicate a game reset
_ZERO_SCORES = {"0", "00", ""}


def _is_game_reset(
    previous: Optional[ScoreboardState], current: ScoreboardState
) -> bool:
    """Return True when the scoreboard appears to have reset for a new game.

    A reset is detected when:
    * Both scores drop to zero (or empty) AND
    * Previously at least one score was non-zero.
    """
    if previous is None:
        return False
    prev_has_score = (
        previous.home_score not in _ZERO_SCORES
        or previous.away_score not in _ZERO_SCORES
    )
    curr_is_zero = (
        current.home_score in _ZERO_SCORES
        and current.away_score in _ZERO_SCORES
    )
    return prev_has_score and curr_is_zero


def _build_openai_client():
    """Return an OpenAI or AzureOpenAI client depending on env vars."""
    azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "")
    azure_key = os.getenv("AZURE_OPENAI_KEY", "")

    if azure_endpoint and azure_key:
        from openai import AzureOpenAI

        api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview")
        return AzureOpenAI(
            azure_endpoint=azure_endpoint,
            api_key=azure_key,
            api_version=api_version,
        )

    api_key = os.getenv("OPENAI_API_KEY", "")
    if api_key:
        from openai import OpenAI

        return OpenAI(api_key=api_key)

    return None


def analyzer_loop(url: str, game_log: GameLog) -> None:
    """Polling loop that monitors the scoreboard and writes events to *game_log*."""
    client = _build_openai_client()
    model = os.getenv("AZURE_OPENAI_DEPLOYMENT", OPENAI_MODEL)

    if client is None:
        game_log.add(
            EventType.ERROR,
            "No OpenAI or Azure OpenAI credentials configured. "
            "LLM insights will not be generated.",
        )

    game_log.add(EventType.INFO, f"Monitoring scoreboard: {url}")
    game_log.add(EventType.INFO, f"Poll interval: {POLL_INTERVAL}s | Model: {model}")

    if UNO_TICKER_TOKEN:
        game_log.add(EventType.INFO, "UNO ticker overlay integration configured.")

    previous: Optional[ScoreboardState] = None
    history: list[ScoreboardState] = []

    while True:
        try:
            current = fetch_scoreboard(url, timeout=REQUEST_TIMEOUT)
        except Exception as exc:
            game_log.add(EventType.ERROR, f"Failed to fetch scoreboard: {exc}")
            time.sleep(POLL_INTERVAL)
            continue

        # --- Game reset detection ---
        if _is_game_reset(previous, current):
            new_num = game_log.new_game()
            game_log.add(
                EventType.GAME_RESET,
                f"Scoreboard reset detected – starting Game #{new_num}. "
                f"Previous: {previous.summary() if previous else 'N/A'}",
            )
            previous = None
            history = []

        changes = detect_changes(previous, current)

        if changes:
            if previous is None:
                game_log.add(EventType.GAME_START, current.summary())
            else:
                for change in changes:
                    if "Score" in change:
                        game_log.add(EventType.SCORE_UPDATE, change)
                    elif "Time" in change:
                        game_log.add(EventType.TIME_UPDATE, change)
                    elif "team" in change.lower():
                        game_log.add(EventType.TEAM_CHANGE, change)

            if client is not None:
                try:
                    insight = get_insight(
                        current,
                        changes,
                        history=history if history else None,
                        model=model,
                        client=client,
                        uno_ticker_token=UNO_TICKER_TOKEN or None,
                    )
                    game_log.add(EventType.INSIGHT, insight)
                except Exception as exc:
                    game_log.add(EventType.ERROR, f"LLM call failed: {exc}")

            history.append(current)
            if len(history) > MAX_HISTORY_SIZE:
                history = history[-MAX_HISTORY_SIZE:]

        previous = current
        time.sleep(POLL_INTERVAL)


def main() -> None:
    """Start both the analyzer loop and the web dashboard."""
    url = os.getenv("SCOREBOARD_URL", "")
    if not url:
        if len(sys.argv) >= 2:
            url = sys.argv[1]
        else:
            print(
                "ERROR: Set the SCOREBOARD_URL environment variable or pass it as "
                "a CLI argument.\n"
                "  python app.py <scoreboard_url>",
                file=sys.stderr,
            )
            sys.exit(1)

    if not url.startswith("http"):
        print(f"ERROR: Invalid URL: {url!r}", file=sys.stderr)
        sys.exit(1)

    game_log = GameLog()
    set_game_log(game_log)
    app = create_app(game_log)

    # Start the analyzer in a background daemon thread
    t = threading.Thread(target=analyzer_loop, args=(url, game_log), daemon=True)
    t.start()

    print(f"🌐 Dashboard running on http://0.0.0.0:{WEB_PORT}")
    print(f"🏁 Monitoring scoreboard: {url}")
    app.run(host="0.0.0.0", port=WEB_PORT, debug=False)


if __name__ == "__main__":
    main()
