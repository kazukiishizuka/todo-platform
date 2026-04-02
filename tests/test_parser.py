import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from app.services.parser import NaturalLanguageParser


class ParserTests(unittest.TestCase):
    def setUp(self):
        self.parser = NaturalLanguageParser()
        self.now = datetime(2026, 4, 1, 10, 0, tzinfo=ZoneInfo("Asia/Tokyo"))

    def test_parse_explicit_datetime(self):
        result = self.parser.parse("4月5日15時に面談", "Asia/Tokyo", now=self.now)
        self.assertEqual(result.parse_status, "confirmed")
        self.assertEqual(result.title, "面談")
        self.assertEqual(result.start_datetime.isoformat(), "2026-04-05T15:00:00+09:00")
        self.assertEqual(result.end_datetime.isoformat(), "2026-04-05T16:00:00+09:00")

    def test_parse_relative_date(self):
        result = self.parser.parse("明日の15:00に歯医者", "Asia/Tokyo", now=self.now)
        self.assertEqual(result.start_datetime.isoformat(), "2026-04-02T15:00:00+09:00")
        self.assertEqual(result.title, "歯医者")

    def test_parse_ambiguous(self):
        result = self.parser.parse("金曜3時 会議", "Asia/Tokyo", now=self.now)
        self.assertEqual(result.parse_status, "needs_confirmation")
        self.assertIn("weekday_needs_week_scope", result.ambiguity_flags)

    def test_parse_on_hold(self):
        result = self.parser.parse("来週 会議", "Asia/Tokyo", now=self.now)
        self.assertEqual(result.parse_status, "on_hold")


if __name__ == "__main__":
    unittest.main()
