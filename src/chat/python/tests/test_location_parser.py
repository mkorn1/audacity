#!/usr/bin/env python3
"""
Unit tests for LocationParser (Phase 3.4)

Tests location parsing including:
- Explicit time parsing
- Time range parsing
- Relative time parsing
- Current state references
- Cursor references
- Label references
- Time format parsing
"""

import unittest
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from location_parser import LocationParser


class TestTimeStringParsing(unittest.TestCase):
    """Test parsing time strings"""

    def test_parse_seconds(self):
        """Test parsing seconds format"""
        self.assertEqual(LocationParser.parse_time_string("2s"), 2.0)
        self.assertEqual(LocationParser.parse_time_string("2 seconds"), 2.0)
        self.assertEqual(LocationParser.parse_time_string("2sec"), 2.0)
        self.assertEqual(LocationParser.parse_time_string("10.5s"), 10.5)

    def test_parse_minutes_seconds(self):
        """Test parsing minutes:seconds format"""
        self.assertEqual(LocationParser.parse_time_string("1:30"), 90.0)
        self.assertEqual(LocationParser.parse_time_string("2:15"), 135.0)
        self.assertEqual(LocationParser.parse_time_string("0:30"), 30.0)

    def test_parse_hours_minutes_seconds(self):
        """Test parsing hours:minutes:seconds format"""
        self.assertEqual(LocationParser.parse_time_string("2:15:30"), 8130.0)
        self.assertEqual(LocationParser.parse_time_string("1:0:0"), 3600.0)
        self.assertEqual(LocationParser.parse_time_string("0:1:30"), 90.0)

    def test_parse_minutes(self):
        """Test parsing minutes format"""
        self.assertEqual(LocationParser.parse_time_string("2 minutes"), 120.0)
        self.assertEqual(LocationParser.parse_time_string("1.5 min"), 90.0)

    def test_parse_hours(self):
        """Test parsing hours format"""
        self.assertEqual(LocationParser.parse_time_string("2 hours"), 7200.0)
        self.assertEqual(LocationParser.parse_time_string("1.5 hr"), 5400.0)

    def test_parse_bare_number(self):
        """Test parsing bare number (assumed seconds)"""
        self.assertEqual(LocationParser.parse_time_string("5"), 5.0)
        self.assertEqual(LocationParser.parse_time_string("10.5"), 10.5)

    def test_parse_invalid(self):
        """Test parsing invalid time strings"""
        self.assertIsNone(LocationParser.parse_time_string("invalid"))
        self.assertIsNone(LocationParser.parse_time_string(""))


class TestLocationParsing(unittest.TestCase):
    """Test parsing location references"""

    def test_parse_explicit_time_point(self):
        """Test parsing explicit time point"""
        result = LocationParser.parse_location("at 2:30")
        self.assertEqual(result["type"], "time_point")
        self.assertEqual(result["time"], 150.0)

    def test_parse_time_range_from_to(self):
        """Test parsing time range 'from X to Y'"""
        result = LocationParser.parse_location("from 1:00 to 2:00")
        self.assertEqual(result["type"], "time_range")
        self.assertEqual(result["start_time"], 60.0)
        self.assertEqual(result["end_time"], 120.0)

    def test_parse_first_seconds(self):
        """Test parsing 'first N seconds'"""
        result = LocationParser.parse_location("first 10 seconds")
        self.assertEqual(result["type"], "time_range")
        self.assertEqual(result["start_time"], 0.0)
        self.assertEqual(result["end_time"], 10.0)

    def test_parse_last_seconds_with_state(self):
        """Test parsing 'last N seconds' with state"""
        state = {"total_project_time": 100.0}
        result = LocationParser.parse_location("last 30 seconds", state)
        self.assertEqual(result["type"], "time_range")
        self.assertEqual(result["start_time"], 70.0)
        self.assertEqual(result["end_time"], 100.0)

    def test_parse_last_seconds_without_state(self):
        """Test parsing 'last N seconds' without state"""
        result = LocationParser.parse_location("last 30 seconds")
        self.assertEqual(result["type"], "error")
        self.assertIn("error", result)

    def test_parse_current_selection_with_state(self):
        """Test parsing 'current selection' with state"""
        state = {
            "has_time_selection": True,
            "selection_start_time": 10.0,
            "selection_end_time": 20.0
        }
        result = LocationParser.parse_location("current selection", state)
        self.assertEqual(result["type"], "time_range")
        self.assertEqual(result["start_time"], 10.0)
        self.assertEqual(result["end_time"], 20.0)

    def test_parse_current_selection_without_state(self):
        """Test parsing 'current selection' without state"""
        result = LocationParser.parse_location("current selection")
        self.assertEqual(result["type"], "error")
        self.assertIn("error", result)

    def test_parse_at_cursor_with_state(self):
        """Test parsing 'at cursor' with state"""
        state = {"cursor_position": 15.0}
        result = LocationParser.parse_location("at cursor", state)
        self.assertEqual(result["type"], "time_point")
        self.assertEqual(result["time"], 15.0)

    def test_parse_at_cursor_without_state(self):
        """Test parsing 'at cursor' without state"""
        result = LocationParser.parse_location("at cursor")
        self.assertEqual(result["type"], "error")
        self.assertIn("error", result)

    def test_parse_label_reference(self):
        """Test parsing label reference"""
        state = {
            "all_labels": [
                {"name": "intro", "start_time": 0.0, "end_time": 10.0},
                {"name": "outro", "start_time": 90.0, "end_time": 100.0}
            ]
        }
        result = LocationParser.parse_location("intro", state)
        self.assertEqual(result["type"], "time_range")
        self.assertEqual(result["start_time"], 0.0)
        self.assertEqual(result["end_time"], 10.0)
        self.assertEqual(result["label_name"], "intro")

    def test_parse_bare_time_range(self):
        """Test parsing bare time range 'X to Y'"""
        result = LocationParser.parse_location("10 to 20")
        self.assertEqual(result["type"], "time_range")
        self.assertEqual(result["start_time"], 10.0)
        self.assertEqual(result["end_time"], 20.0)

    def test_parse_bare_time_range_with_colon(self):
        """Test parsing bare time range with colon format"""
        result = LocationParser.parse_location("1:00-2:00")
        self.assertEqual(result["type"], "time_range")
        self.assertEqual(result["start_time"], 60.0)
        self.assertEqual(result["end_time"], 120.0)

    def test_parse_single_time_in_message(self):
        """Test parsing single time in message"""
        result = LocationParser.parse_location("go to 5 seconds")
        self.assertEqual(result["type"], "time_point")
        self.assertEqual(result["time"], 5.0)

    def test_parse_invalid_location(self):
        """Test parsing invalid location"""
        result = LocationParser.parse_location("invalid location reference")
        self.assertEqual(result["type"], "error")
        self.assertIn("error", result)


class TestFindLabelByName(unittest.TestCase):
    """Test finding labels by name"""

    def test_find_label_exact_match(self):
        """Test finding label with exact match"""
        state = {
            "all_labels": [
                {"name": "intro", "start_time": 0.0, "end_time": 10.0},
                {"name": "outro", "start_time": 90.0, "end_time": 100.0}
            ]
        }
        label = LocationParser.find_label_by_name("intro", state)
        self.assertIsNotNone(label)
        self.assertEqual(label["name"], "intro")
        self.assertEqual(label["start_time"], 0.0)

    def test_find_label_case_insensitive(self):
        """Test finding label case-insensitive"""
        state = {
            "all_labels": [
                {"name": "Intro", "start_time": 0.0, "end_time": 10.0}
            ]
        }
        label = LocationParser.find_label_by_name("intro", state)
        self.assertIsNotNone(label)
        self.assertEqual(label["name"], "Intro")

    def test_find_label_partial_match(self):
        """Test finding label with partial match"""
        state = {
            "all_labels": [
                {"name": "introduction", "start_time": 0.0, "end_time": 10.0}
            ]
        }
        label = LocationParser.find_label_by_name("intro", state)
        self.assertIsNotNone(label)
        self.assertEqual(label["name"], "introduction")

    def test_find_label_not_found(self):
        """Test finding label that doesn't exist"""
        state = {
            "all_labels": [
                {"name": "outro", "start_time": 90.0, "end_time": 100.0}
            ]
        }
        label = LocationParser.find_label_by_name("intro", state)
        self.assertIsNone(label)

    def test_find_label_without_state(self):
        """Test finding label without state"""
        label = LocationParser.find_label_by_name("intro", None)
        self.assertIsNone(label)


if __name__ == '__main__':
    unittest.main()

