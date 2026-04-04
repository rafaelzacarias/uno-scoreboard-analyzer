"""Tests for uno_ticker.py."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from uno_ticker import push_ticker_messages


_EXPECTED_URL_PREFIX = "https://app.overlays.uno/apiv2/controlapps/"


class TestPushTickerMessages(unittest.TestCase):
    def test_builds_correct_url(self):
        token = "abc123"
        with patch("uno_ticker.requests.put") as mock_put:
            mock_put.return_value = MagicMock(status_code=200)
            push_ticker_messages(token, ["Hello"])
        mock_put.assert_called_once()
        actual_url = mock_put.call_args[0][0]
        self.assertTrue(actual_url.startswith(_EXPECTED_URL_PREFIX))
        self.assertIn(token, actual_url)

    def test_sends_set_messages_command(self):
        with patch("uno_ticker.requests.put") as mock_put:
            mock_put.return_value = MagicMock(status_code=200)
            push_ticker_messages("token", ["Hello"])
        call_kwargs = mock_put.call_args[1]
        self.assertEqual(call_kwargs["json"]["command"], "SetMessages")

    def test_joins_messages_with_newline(self):
        with patch("uno_ticker.requests.put") as mock_put:
            mock_put.return_value = MagicMock(status_code=200)
            push_ticker_messages("token", ["Line 1", "Line 2", "Line 3"])
        call_kwargs = mock_put.call_args[1]
        self.assertEqual(call_kwargs["json"]["value"], "Line 1\nLine 2\nLine 3")

    def test_single_message_no_trailing_newline(self):
        with patch("uno_ticker.requests.put") as mock_put:
            mock_put.return_value = MagicMock(status_code=200)
            push_ticker_messages("token", ["Only one message"])
        call_kwargs = mock_put.call_args[1]
        self.assertEqual(call_kwargs["json"]["value"], "Only one message")

    def test_uses_put_method(self):
        with patch("uno_ticker.requests.put") as mock_put:
            mock_put.return_value = MagicMock(status_code=200)
            push_ticker_messages("token", ["msg"])
        mock_put.assert_called_once()

    def test_uses_timeout(self):
        with patch("uno_ticker.requests.put") as mock_put:
            mock_put.return_value = MagicMock(status_code=200)
            push_ticker_messages("token", ["msg"])
        call_kwargs = mock_put.call_args[1]
        self.assertIn("timeout", call_kwargs)
        self.assertGreater(call_kwargs["timeout"], 0)

    def test_http_error_does_not_raise(self):
        """A non-2xx response must not raise an exception."""
        import requests as req

        with patch("uno_ticker.requests.put") as mock_put:
            mock_response = MagicMock()
            mock_response.raise_for_status.side_effect = req.HTTPError("500 Server Error")
            mock_put.return_value = mock_response
            # Should not raise
            push_ticker_messages("token", ["msg"])

    def test_connection_error_does_not_raise(self):
        """A network-level error must not raise an exception."""
        import requests as req

        with patch("uno_ticker.requests.put", side_effect=req.ConnectionError("unreachable")):
            # Should not raise
            push_ticker_messages("token", ["msg"])

    def test_timeout_error_does_not_raise(self):
        """A timeout must not raise an exception."""
        import requests as req

        with patch("uno_ticker.requests.put", side_effect=req.Timeout("timed out")):
            # Should not raise
            push_ticker_messages("token", ["msg"])

    def test_token_embedded_in_url(self):
        """The token must appear in the request URL."""
        token = "3PKwawvsiVKfJQRTkyJTDB"
        with patch("uno_ticker.requests.put") as mock_put:
            mock_put.return_value = MagicMock(status_code=200)
            push_ticker_messages(token, ["test"])
        actual_url = mock_put.call_args[0][0]
        self.assertIn(token, actual_url)


if __name__ == "__main__":
    unittest.main()
