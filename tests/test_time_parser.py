import unittest
from datetime import date
from unittest.mock import patch

from app.utils.time_parser import format_time_range_label, month_range, parse_time_range

FROZEN_DATE = date(2026, 4, 30)


def _patch_today():
    return patch("app.utils.time_parser.date") 


class TestParseTimeRange(unittest.TestCase):

    def test_last_month(self):
        with _patch_today() as mock_date:
            mock_date.today.return_value = FROZEN_DATE
            self.assertEqual(parse_time_range("上月"), [(20260301, 20260331)])
            self.assertEqual(parse_time_range("上个月"), [(20260301, 20260331)])

    def test_last_quarter(self):
        with _patch_today() as mock_date:
            mock_date.today.return_value = FROZEN_DATE
            expected = [
                (20260101, 20260131),
                (20260201, 20260228),
                (20260301, 20260331),
            ]
            self.assertEqual(parse_time_range("上季度"), expected)
            self.assertEqual(parse_time_range("上个季度"), expected)

    def test_specific_month_short(self):
        with _patch_today() as mock_date:
            mock_date.today.return_value = FROZEN_DATE
            self.assertEqual(parse_time_range("3月"), [(20260301, 20260331)])

    def test_specific_month_year_zh(self):
        with _patch_today() as mock_date:
            mock_date.today.return_value = FROZEN_DATE
            self.assertEqual(parse_time_range("2026年3月"), [(20260301, 20260331)])

    def test_specific_month_dash(self):
        with _patch_today() as mock_date:
            mock_date.today.return_value = FROZEN_DATE
            self.assertEqual(parse_time_range("2026-03"), [(20260301, 20260331)])

    def test_quarter_q1(self):
        with _patch_today() as mock_date:
            mock_date.today.return_value = FROZEN_DATE
            expected = [
                (20260101, 20260131),
                (20260201, 20260228),
                (20260301, 20260331),
            ]
            self.assertEqual(parse_time_range("Q1"), expected)

    def test_quarter_q2(self):
        with _patch_today() as mock_date:
            mock_date.today.return_value = FROZEN_DATE
            expected = [
                (20260401, 20260430),
                (20260501, 20260531),
                (20260601, 20260630),
            ]
            self.assertEqual(parse_time_range("Q2"), expected)

    def test_year_quarter(self):
        with _patch_today() as mock_date:
            mock_date.today.return_value = FROZEN_DATE
            expected = [
                (20260101, 20260131),
                (20260201, 20260228),
                (20260301, 20260331),
            ]
            self.assertEqual(parse_time_range("2026Q1"), expected)

    def test_unknown_defaults_to_last_month(self):
        with _patch_today() as mock_date:
            mock_date.today.return_value = FROZEN_DATE
            self.assertEqual(parse_time_range("你好"), [(20260301, 20260331)])

    def test_format_label_month(self):
        result = format_time_range_label([(20260301, 20260331)])
        self.assertEqual(result, "2026年3月")

    def test_format_label_quarter(self):
        ranges = [
            (20260101, 20260131),
            (20260201, 20260228),
            (20260301, 20260331),
        ]
        result = format_time_range_label(ranges)
        self.assertEqual(result, "2026年Q1（1-3月）")

    def test_february_leap_year(self):
        start, end = month_range(2024, 2)
        self.assertEqual(start, 20240201)
        self.assertEqual(end, 20240229)

    def test_february_non_leap_year(self):
        start, end = month_range(2025, 2)
        self.assertEqual(start, 20250201)
        self.assertEqual(end, 20250228)


if __name__ == "__main__":
    unittest.main()
