"""Module for pushing insights to an overlays.uno ticker overlay via its control API."""

from __future__ import annotations

import logging

import requests

_BASE_URL = "https://app.overlays.uno/apiv2/controlapps/{token}/api"
_TIMEOUT = 10

logger = logging.getLogger(__name__)


def push_ticker_messages(token: str, messages: list[str]) -> None:
    """Send messages to an overlays.uno ticker overlay.

    Builds the API URL from *token*, then sends an HTTP PUT request with the
    ``SetMessages`` command.  The messages are joined into a single
    newline-separated string.

    If the request fails for any reason the error is logged but no exception
    is raised so the caller's main loop is not interrupted.

    Parameters
    ----------
    token:
        The control token for the ticker overlay (the ID portion of the
        overlay's control URL).
    messages:
        List of message strings to display in the ticker.  They will be
        joined with ``\\n``.
    """
    url = _BASE_URL.format(token=token)
    payload = {
        "command": "SetMessages",
        "value": "\n".join(messages),
    }
    try:
        response = requests.put(url, json=payload, timeout=_TIMEOUT)
        response.raise_for_status()
    except requests.RequestException as exc:
        logger.error("Failed to push messages to ticker overlay: %s", exc)
