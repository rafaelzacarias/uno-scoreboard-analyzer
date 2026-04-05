"""Analyzer module: calls an LLM to produce real-time handball game insights."""

from __future__ import annotations

import os
from typing import Optional

from openai import OpenAI

from scraper import ScoreboardState
from uno_ticker import push_ticker_messages

_SYSTEM_PROMPT = """\
You are a sports analyst specialising in handball. You are watching a live \
handball match and receiving real-time scoreboard updates. \
Your task is to provide concise, insightful commentary about what is happening \
in the game based on each scoreboard update.

Guidelines:
- Keep your analysis short (2-4 sentences).
- Focus on momentum shifts, score differences, critical moments, and time pressure.
- Use dynamic, engaging language appropriate for a live broadcast.
- Do not invent facts beyond what is provided in the scoreboard data.
"""


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

    if history:
        lines.append("=== Match history (oldest → newest) ===")
        for state in history[-5:]:  # Send at most the last 5 states
            lines.append(f"  {state.summary()}")
        lines.append("")

    lines.append("=== Latest update ===")
    lines.append(f"Current score: {current.summary()}")
    lines.append("")
    lines.append("=== Changes detected ===")
    for change in changes:
        lines.append(f"  - {change}")

    lines.append("")
    lines.append(
        "Please provide a brief real-time insight about the handball game based on "
        "the above information."
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

    prompt = build_prompt(current, changes, history)

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        max_tokens=300,
        temperature=0.7,
    )

    insight = response.choices[0].message.content.strip()

    if uno_ticker_token:
        push_ticker_messages(uno_ticker_token, [insight])

    return insight
