"""Tests for web_app.py – Flask routes."""

from __future__ import annotations

import json
import unittest

from game_log import EventType, GameLog
from web_app import create_app


class TestWebApp(unittest.TestCase):
    def setUp(self):
        self.log = GameLog()
        self.app = create_app(game_log=self.log)
        self.client = self.app.test_client()

    def test_index_returns_html(self):
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"UNO", resp.data)

    def test_health_endpoint(self):
        resp = self.client.get("/health")
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertEqual(data["status"], "ok")

    def test_api_events_empty(self):
        resp = self.client.get("/api/events")
        data = json.loads(resp.data)
        self.assertEqual(data["events"], [])
        self.assertEqual(data["total"], 0)

    def test_api_events_returns_events(self):
        self.log.add(EventType.INFO, "test event")
        resp = self.client.get("/api/events")
        data = json.loads(resp.data)
        self.assertEqual(len(data["events"]), 1)
        self.assertEqual(data["events"][0]["message"], "test event")
        self.assertEqual(data["events"][0]["type"], "info")

    def test_api_events_since_param(self):
        self.log.add(EventType.INFO, "first")
        self.log.add(EventType.INFO, "second")
        resp = self.client.get("/api/events?since=1")
        data = json.loads(resp.data)
        self.assertEqual(len(data["events"]), 1)
        self.assertEqual(data["events"][0]["message"], "second")

    def test_api_events_game_filter(self):
        self.log.add(EventType.INFO, "game 1 event")
        self.log.new_game()
        self.log.add(EventType.INFO, "game 2 event")
        resp = self.client.get("/api/events?game=2")
        data = json.loads(resp.data)
        self.assertEqual(len(data["events"]), 1)
        self.assertIn("game 2", data["events"][0]["message"])

    def test_api_events_game_number_in_response(self):
        resp = self.client.get("/api/events")
        data = json.loads(resp.data)
        self.assertEqual(data["game_number"], 1)


if __name__ == "__main__":
    unittest.main()
