"""Entry point for the UNO Scoreboard Analyzer.

Usage:
    python main.py <uno_token>

Example:
    python main.py 0ZtIYoE5lp1X1rceb5MV5s
"""

from __future__ import annotations

import os
import sys
import time
from typing import Optional

from dotenv import load_dotenv

from analyzer import get_insight
from scraper import ScoreboardState, build_api_url, detect_changes, fetch_scoreboard

load_dotenv()

# ---------------------------------------------------------------------------
# Configuration (can be overridden via environment variables in .env)
# ---------------------------------------------------------------------------
POLL_INTERVAL: int = int(os.getenv("POLL_INTERVAL", "10"))
REQUEST_TIMEOUT: int = int(os.getenv("REQUEST_TIMEOUT", "15"))
OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-5.4-mini")
UNO_TICKER_TOKEN: str = os.getenv("UNO_TICKER_TOKEN", "")

# Maximum number of scoreboard states retained in the rolling history buffer.
# build_prompt() will use only the last PROMPT_HISTORY_LIMIT of these.
MAX_HISTORY_SIZE: int = 20


def run(url: str) -> None:
    """Main monitoring loop.

    Polls *url* every :data:`POLL_INTERVAL` seconds, detects scoreboard
    changes, and prints LLM-generated insights to stdout.

    Parameters
    ----------
    url:
        Full Singular.live control-app API URL.
    """

    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        print(
            "WARNING: OPENAI_API_KEY is not set. "
            "LLM insights will not be generated.\n"
            "Set the key in a .env file (see .env.example) to enable insights.",
            file=sys.stderr,
        )

    print(f"🏁 Monitoring scoreboard: {url}")
    print(f"   Poll interval : {POLL_INTERVAL}s")
    print(f"   Model         : {OPENAI_MODEL}")
    if UNO_TICKER_TOKEN:
        print("   Ticker overlay: configured")
    print("   Press Ctrl+C to stop.\n")

    previous: Optional[ScoreboardState] = None
    history: list[ScoreboardState] = []

    while True:
        try:
            current = fetch_scoreboard(url, timeout=REQUEST_TIMEOUT)
        except Exception as exc:
            print(f"[ERROR] Failed to fetch scoreboard: {exc}", file=sys.stderr)
            time.sleep(POLL_INTERVAL)
            continue

        changes = detect_changes(previous, current)

        if changes:
            timestamp = time.strftime("%H:%M:%S")
            print(f"[{timestamp}] 📊 {current.summary()}")
            for change in changes:
                print(f"   ↳ {change}")

            if api_key:
                try:
                    insight = get_insight(
                        current,
                        changes,
                        history=history if history else None,
                        model=OPENAI_MODEL,
                        uno_ticker_token=UNO_TICKER_TOKEN or None,
                    )
                    print(f"\n💡 Insight: {insight}\n")
                except Exception as exc:
                    print(f"[ERROR] LLM call failed: {exc}", file=sys.stderr)
            else:
                print()

            # Keep a rolling history of observed states
            history.append(current)
            if len(history) > MAX_HISTORY_SIZE:
                history = history[-MAX_HISTORY_SIZE:]

        previous = current
        time.sleep(POLL_INTERVAL)


def main() -> None:
    """Parse CLI arguments and start the monitoring loop."""
    token = os.getenv("UNO_TOKEN", "")
    if not token:
        if len(sys.argv) == 2:
            token = sys.argv[1]
        else:
            print(
                "Usage: python main.py <uno_token>\n"
                "Example: python main.py 0ZtIYoE5lp1X1rceb5MV5s\n"
                "Or set the UNO_TOKEN environment variable.",
                file=sys.stderr,
            )
            sys.exit(1)

    url = build_api_url(token)
    try:
        run(url)
    except KeyboardInterrupt:
        print("\n👋 Monitoring stopped.")


if __name__ == "__main__":
    main()
