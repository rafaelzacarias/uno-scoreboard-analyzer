"""Analyzer module: calls an LLM to produce real-time handball game insights."""

from __future__ import annotations

import logging
import os
from typing import Optional

from openai import OpenAI

from scraper import ScoreboardState
from uno_ticker import push_ticker_messages

logger = logging.getLogger(__name__)

_debug_initialized = False


def _ensure_debug_logging() -> None:
    """Enable DEBUG-level logging when the ``DEBUG_PROMPT`` env var is truthy.

    Called lazily on first use so that ``load_dotenv()`` in the entry points
    has already run.
    """
    global _debug_initialized
    if _debug_initialized:
        return
    _debug_initialized = True

    flag = os.getenv("DEBUG_PROMPT", "").strip().lower()
    if flag in ("1", "true", "yes"):
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s [%(name)s] %(message)s"))
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)

_SYSTEM_PROMPT = """\
You are a sports analyst specialising in handball. You are watching a live \
handball match and receiving real-time scoreboard updates including the full \
scoring timeline for the current game. \
Your task is to provide concise, insightful commentary about what is happening \
in the game based on each scoreboard update.

Guidelines:
- Keep your analysis short (2-4 sentences).
- Analyse the full scoring timeline to identify momentum shifts, scoring runs, \
  lead changes, and dominant stretches.
- Comment on the current gap, whether a team is closing in or pulling away, \
  and any pressure from the clock or period.
- Use dynamic, engaging language appropriate for a live broadcast.
- Do not invent facts beyond what is provided in the scoreboard data.
"""


def _build_timeline(history: list[ScoreboardState]) -> list[str]:
    """Build a chronological scoring timeline from the full game history.

    Returns a list of human-readable lines describing each scoring change,
    lead changes, and runs.
    """
    timeline: list[str] = []
    prev_leader = ""

    for i, state in enumerate(history):
        try:
            h = int(state.home_score) if state.home_score else 0
            a = int(state.away_score) if state.away_score else 0
        except ValueError:
            h, a = 0, 0

        diff = h - a
        if diff > 0:
            leader = state.home_team or "Home"
        elif diff < 0:
            leader = state.away_team or "Away"
        else:
            leader = "Tied"

        period_str = f" [{state.period}]" if state.period else ""
        time_str = state.game_time or "?"
        line = f"  {time_str}{period_str}  {state.home_team} {h} – {a} {state.away_team}"

        if leader != prev_leader and i > 0:
            if leader == "Tied":
                line += "  ⚖️ TIED"
            else:
                line += f"  🔄 LEAD CHANGE → {leader}"
        prev_leader = leader

        timeline.append(line)

    return timeline


def _detect_runs(history: list[ScoreboardState]) -> list[str]:
    """Detect unanswered scoring runs in the game history."""
    runs: list[str] = []
    if len(history) < 2:
        return runs

    run_team = ""
    run_count = 0

    for i in range(1, len(history)):
        try:
            prev_h = int(history[i - 1].home_score) if history[i - 1].home_score else 0
            prev_a = int(history[i - 1].away_score) if history[i - 1].away_score else 0
            cur_h = int(history[i].home_score) if history[i].home_score else 0
            cur_a = int(history[i].away_score) if history[i].away_score else 0
        except ValueError:
            continue

        home_scored = cur_h - prev_h
        away_scored = cur_a - prev_a

        if home_scored > 0 and away_scored == 0:
            team = history[i].home_team or "Home"
            if team == run_team:
                run_count += home_scored
            else:
                if run_count >= 3:
                    runs.append(f"{run_team}: {run_count}-0 run")
                run_team = team
                run_count = home_scored
        elif away_scored > 0 and home_scored == 0:
            team = history[i].away_team or "Away"
            if team == run_team:
                run_count += away_scored
            else:
                if run_count >= 3:
                    runs.append(f"{run_team}: {run_count}-0 run")
                run_team = team
                run_count = away_scored
        else:
            if run_count >= 3:
                runs.append(f"{run_team}: {run_count}-0 run")
            run_team = ""
            run_count = 0

    # Capture any active run at the end
    if run_count >= 3:
        runs.append(f"{run_team}: {run_count}-0 run (active)")

    return runs


def build_prompt(
    current: ScoreboardState,
    changes: list[str],
    history: Optional[list[ScoreboardState]] = None,
) -> str:
    """Construct the user-facing prompt sent to the LLM.

    Parameters
    ----------
    current:
        The latest scoreboard state.
    changes:
        Human-readable list of what changed since the last observation.
    history:
        Optional list of previous states (most recent last) to give the LLM
        additional context.

    Returns
    -------
    str
        Formatted prompt string.
    """
    lines: list[str] = []

    if history and len(history) > 0:
        # Full scoring timeline
        all_states = history + [current]
        timeline = _build_timeline(all_states)

        lines.append(f"=== Full game scoring timeline ({len(all_states)} updates) ===")
        # Show all states if ≤ 30, otherwise show first 5 + last 20
        if len(timeline) <= 30:
            lines.extend(timeline)
        else:
            lines.extend(timeline[:5])
            lines.append(f"  ... ({len(timeline) - 25} updates omitted) ...")
            lines.extend(timeline[-20:])
        lines.append("")

        # Scoring runs
        runs = _detect_runs(all_states)
        if runs:
            lines.append("=== Scoring runs detected ===")
            for run in runs:
                lines.append(f"  🔥 {run}")
            lines.append("")

        # Quick stats
        try:
            first_h = int(all_states[0].home_score) if all_states[0].home_score else 0
            first_a = int(all_states[0].away_score) if all_states[0].away_score else 0
            cur_h = int(current.home_score) if current.home_score else 0
            cur_a = int(current.away_score) if current.away_score else 0
            home_name = current.home_team or "Home"
            away_name = current.away_team or "Away"
            lines.append("=== Game stats ===")
            lines.append(f"  Total goals: {cur_h + cur_a}")
            lines.append(f"  {home_name} scored {cur_h - first_h} goal(s) this game")
            lines.append(f"  {away_name} scored {cur_a - first_a} goal(s) this game")
            diff = cur_h - cur_a
            if diff > 0:
                lines.append(f"  Lead: {home_name} by {diff}")
            elif diff < 0:
                lines.append(f"  Lead: {away_name} by {-diff}")
            else:
                lines.append("  Game is TIED")
            lines.append("")
        except ValueError:
            pass

    lines.append("=== Latest update ===")
    lines.append(f"Current score: {current.summary()}")
    lines.append("")
    lines.append("=== Changes detected ===")
    for change in changes:
        lines.append(f"  - {change}")

    lines.append("")
    lines.append(
        "Based on the full game timeline and current state, provide a brief "
        "real-time insight about this handball match."
    )

    return "\n".join(lines)


def get_insight(
    current: ScoreboardState,
    changes: list[str],
    history: Optional[list[ScoreboardState]] = None,
    model: str = "",
    client: Optional[OpenAI] = None,
    uno_ticker_token: Optional[str] = None,
) -> str:
    """Call the OpenAI API and return a real-time game insight string.

    Parameters
    ----------
    current:
        The latest scoreboard state.
    changes:
        Human-readable list of what changed since the last observation.
    history:
        Optional list of previous states for additional context.
    model:
        OpenAI model identifier to use.  Falls back to the ``OPENAI_MODEL``
        environment variable, then ``gpt-5.4-mini``.
    client:
        Optional pre-configured :class:`openai.OpenAI` instance. If omitted,
        one is created automatically using the ``OPENAI_API_KEY`` environment
        variable.
    uno_ticker_token:
        Optional overlays.uno ticker overlay control token.  When set, the
        generated insight is pushed to the ticker overlay after a successful
        LLM call.

    Returns
    -------
    str
        The LLM-generated insight text.

    Raises
    ------
    openai.OpenAIError
        If the API call fails.
    """
    if not model:
        model = os.getenv("OPENAI_MODEL", "gpt-5.4-mini")

    if client is None:
        client = OpenAI()

    _ensure_debug_logging()
    prompt = build_prompt(current, changes, history)
    logger.debug("=== LLM PROMPT START ===\n%s\n=== LLM PROMPT END ===", prompt)

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        max_completion_tokens=300,
        temperature=0.7,
    )

    insight = response.choices[0].message.content.strip()

    if uno_ticker_token:
        push_ticker_messages(uno_ticker_token, [insight])

    return insight
