"""Flask web application that serves the live game dashboard."""

from __future__ import annotations

import os
from typing import Optional

from flask import Flask, jsonify, render_template, request

from game_log import GameLog

# ---------------------------------------------------------------------------
# Module-level log reference – set by app.py before starting the server.
# ---------------------------------------------------------------------------
_game_log: Optional[GameLog] = None


def create_app(game_log: Optional[GameLog] = None) -> Flask:
    """Create and configure the Flask application.

    Parameters
    ----------
    game_log:
        The shared :class:`GameLog` instance written to by the analyzer loop.
        If *None*, the module-level ``_game_log`` is used (set via
        :func:`set_game_log`).

    Returns
    -------
    Flask
        Configured Flask application.
    """
    app = Flask(__name__, template_folder="templates")

    log = game_log or _game_log

    @app.route("/")
    def index():  # type: ignore[return]
        return render_template("index.html")

    @app.route("/api/events")
    def api_events():  # type: ignore[return]
        nonlocal log
        if log is None:
            log = _game_log
        if log is None:
            return jsonify({"events": [], "total": 0, "game_number": 0})

        since = request.args.get("since", 0, type=int)
        game = request.args.get("game", None, type=int)
        events = log.get_events(since_index=since, game_number=game)
        return jsonify(
            {
                "events": [
                    {
                        "timestamp": e.timestamp,
                        "type": e.event_type.value,
                        "message": e.message,
                        "game_number": e.game_number,
                    }
                    for e in events
                ],
                "total": len(log),
                "game_number": log.game_number,
            }
        )

    @app.route("/health")
    def health():  # type: ignore[return]
        return jsonify({"status": "ok"})

    return app


def set_game_log(log: GameLog) -> None:
    """Set the module-level game log reference."""
    global _game_log
    _game_log = log
