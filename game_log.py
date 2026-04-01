"""Thread-safe in-memory game event log.

Stores timestamped game events (score changes, insights, game resets) so
they can be read by the web dashboard while the analyzer loop writes them.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class EventType(Enum):
    """Categories for game log events."""

    GAME_START = "game_start"
    GAME_RESET = "game_reset"
    SCORE_UPDATE = "score_update"
    TIME_UPDATE = "time_update"
    TEAM_CHANGE = "team_change"
    INSIGHT = "insight"
    ERROR = "error"
    INFO = "info"


@dataclass
class GameEvent:
    """A single timestamped entry in the game log."""

    timestamp: str
    event_type: EventType
    message: str
    game_number: int = 1


class GameLog:
    """Thread-safe append-only event log with game numbering.

    Parameters
    ----------
    max_events:
        Maximum number of events to retain. Older events are discarded
        when this limit is exceeded.
    """

    def __init__(self, max_events: int = 2000) -> None:
        self._events: list[GameEvent] = []
        self._lock = threading.Lock()
        self._max_events = max_events
        self._game_number = 1

    @property
    def game_number(self) -> int:
        with self._lock:
            return self._game_number

    def new_game(self) -> int:
        """Increment the game counter and return the new game number."""
        with self._lock:
            self._game_number += 1
            return self._game_number

    def add(self, event_type: EventType, message: str) -> GameEvent:
        """Append an event to the log and return it.

        Parameters
        ----------
        event_type:
            Category of the event.
        message:
            Human-readable event description.

        Returns
        -------
        GameEvent
            The newly created event.
        """
        with self._lock:
            event = GameEvent(
                timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
                event_type=event_type,
                message=message,
                game_number=self._game_number,
            )
            self._events.append(event)
            if len(self._events) > self._max_events:
                self._events = self._events[-self._max_events :]
            return event

    def get_events(
        self,
        since_index: int = 0,
        game_number: Optional[int] = None,
    ) -> list[GameEvent]:
        """Return events starting from *since_index*.

        Parameters
        ----------
        since_index:
            Return only events with an index >= this value.
        game_number:
            If provided, return only events for this game number.

        Returns
        -------
        list[GameEvent]
            Matching events in chronological order.
        """
        with self._lock:
            events = self._events[since_index:]
            if game_number is not None:
                events = [e for e in events if e.game_number == game_number]
            return list(events)

    def __len__(self) -> int:
        with self._lock:
            return len(self._events)
