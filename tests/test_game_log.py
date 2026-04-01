"""Tests for game_log.py."""

from __future__ import annotations

import threading
import unittest

from game_log import EventType, GameEvent, GameLog


class TestGameLog(unittest.TestCase):
    def test_add_event(self):
        log = GameLog()
        event = log.add(EventType.INFO, "hello")
        self.assertEqual(event.event_type, EventType.INFO)
        self.assertEqual(event.message, "hello")
        self.assertEqual(event.game_number, 1)
        self.assertEqual(len(log), 1)

    def test_get_events_since(self):
        log = GameLog()
        log.add(EventType.INFO, "first")
        log.add(EventType.INFO, "second")
        log.add(EventType.INFO, "third")
        events = log.get_events(since_index=1)
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0].message, "second")

    def test_get_events_by_game_number(self):
        log = GameLog()
        log.add(EventType.GAME_START, "game 1 start")
        log.new_game()
        log.add(EventType.GAME_START, "game 2 start")
        events_g1 = log.get_events(game_number=1)
        events_g2 = log.get_events(game_number=2)
        self.assertEqual(len(events_g1), 1)
        self.assertEqual(len(events_g2), 1)
        self.assertIn("game 1", events_g1[0].message)
        self.assertIn("game 2", events_g2[0].message)

    def test_new_game_increments(self):
        log = GameLog()
        self.assertEqual(log.game_number, 1)
        self.assertEqual(log.new_game(), 2)
        self.assertEqual(log.new_game(), 3)

    def test_max_events_cap(self):
        log = GameLog(max_events=5)
        for i in range(10):
            log.add(EventType.INFO, f"event {i}")
        self.assertEqual(len(log), 5)
        events = log.get_events()
        self.assertEqual(events[0].message, "event 5")

    def test_thread_safety(self):
        log = GameLog()
        errors: list[str] = []

        def writer(start: int) -> None:
            try:
                for i in range(50):
                    log.add(EventType.INFO, f"writer-{start}-{i}")
            except Exception as exc:
                errors.append(str(exc))

        threads = [threading.Thread(target=writer, args=(n,)) for n in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(errors, [])
        self.assertEqual(len(log), 200)


class TestEventType(unittest.TestCase):
    def test_all_types_have_values(self):
        for et in EventType:
            self.assertTrue(len(et.value) > 0)


if __name__ == "__main__":
    unittest.main()
