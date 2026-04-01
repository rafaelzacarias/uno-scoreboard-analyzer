"""Analyzer module: calls an LLM to produce real-time handball game insights."""

from __future__ import annotations

import os
from typing import Optional

from openai import OpenAI

from scraper import ScoreboardState

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
    model: str = "gpt-4o-mini",
    client: Optional[OpenAI] = None,
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
        OpenAI model identifier to use.
    client:
        Optional pre-configured :class:`openai.OpenAI` instance. If omitted,
        one is created automatically using the ``OPENAI_API_KEY`` environment
        variable.

    Returns
    -------
    str
        The LLM-generated insight text.

    Raises
    ------
    openai.OpenAIError
        If the API call fails.
    """
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

    return response.choices[0].message.content.strip()
