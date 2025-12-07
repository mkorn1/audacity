#!/usr/bin/env python3
"""
Unit tests for value_inference.py
"""

import sys
import os
import unittest

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from value_inference import (
    ValueInferenceEngine,
    InferredValue,
    InferenceResult,
    infer_missing_values,
)
from state_contracts import StateKey
from state_gap_analyzer import StateGap


class TestTimeParsingBasics(unittest.TestCase):
    """Test basic time reference parsing."""

    def setUp(self):
        self.engine = ValueInferenceEngine()

    def test_parse_at_x_seconds(self):
        """Parse 'at X seconds' pattern."""
        result = self.engine._parse_time_references("split at 20 seconds", {})
        self.assertEqual(result["point_time"], 20.0)

    def test_parse_at_x_s(self):
        """Parse 'at Xs' pattern."""
        result = self.engine._parse_time_references("split at 30s", {})
        self.assertEqual(result["point_time"], 30.0)

    def test_parse_standalone_seconds(self):
        """Parse standalone 'X seconds' pattern."""
        result = self.engine._parse_time_references("split 45 seconds", {})
        self.assertEqual(result["point_time"], 45.0)

    def test_parse_decimal_seconds(self):
        """Parse decimal seconds."""
        result = self.engine._parse_time_references("at 20.5 seconds", {})
        self.assertEqual(result["point_time"], 20.5)


class TestTimeParsingRanges(unittest.TestCase):
    """Test time range parsing."""

    def setUp(self):
        self.engine = ValueInferenceEngine()

    def test_parse_first_x_seconds(self):
        """Parse 'first X seconds' pattern."""
        result = self.engine._parse_time_references("trim first 30 seconds", {})
        self.assertEqual(result["start_time"], 0.0)
        self.assertEqual(result["end_time"], 30.0)

    def test_parse_last_x_seconds(self):
        """Parse 'last X seconds' pattern with project duration."""
        result = self.engine._parse_time_references(
            "delete last 10 seconds",
            {"total_project_time": 60.0}
        )
        self.assertEqual(result["start_time"], 50.0)
        self.assertEqual(result["end_time"], 60.0)
        self.assertTrue(result["is_relative"])

    def test_parse_from_x_to_y(self):
        """Parse 'from X to Y' pattern."""
        result = self.engine._parse_time_references("cut from 10 to 20 seconds", {})
        self.assertEqual(result["start_time"], 10.0)
        self.assertEqual(result["end_time"], 20.0)

    def test_parse_x_to_y(self):
        """Parse 'X to Y seconds' pattern."""
        result = self.engine._parse_time_references("delete 5 to 15 seconds", {})
        self.assertEqual(result["start_time"], 5.0)
        self.assertEqual(result["end_time"], 15.0)


class TestTimeParsingMMSS(unittest.TestCase):
    """Test MM:SS format parsing."""

    def setUp(self):
        self.engine = ValueInferenceEngine()

    def test_parse_mmss_point(self):
        """Parse 'M:SS' format as point time."""
        result = self.engine._parse_time_references("split at 1:30", {})
        self.assertEqual(result["point_time"], 90.0)

    def test_parse_mmss_range(self):
        """Parse 'M:SS to M:SS' format as range."""
        result = self.engine._parse_time_references("cut from 1:00 to 2:30", {})
        self.assertEqual(result["start_time"], 60.0)
        self.assertEqual(result["end_time"], 150.0)


class TestParameterInference(unittest.TestCase):
    """Test parameter inference."""

    def setUp(self):
        self.engine = ValueInferenceEngine()

    def test_infer_time_from_message(self):
        """Infer time parameter from user message."""
        result = self.engine.infer_values(
            gaps=[],
            missing_parameters=["time"],
            user_message="split at 20 seconds",
            current_state={},
            tool_name="split_at_time"
        )
        self.assertIn("time", result.inferred_values)
        self.assertEqual(result.inferred_values["time"].value, 20.0)
        self.assertEqual(result.inferred_values["time"].source, "user_message")
        self.assertFalse(result.needs_user_clarification)

    def test_infer_time_from_cursor_keyword(self):
        """Infer time from 'here' keyword using cursor."""
        result = self.engine.infer_values(
            gaps=[],
            missing_parameters=["time"],
            user_message="split here",
            current_state={"cursor_position": 15.0},
            tool_name="split_at_time"
        )
        self.assertIn("time", result.inferred_values)
        self.assertEqual(result.inferred_values["time"].value, 15.0)
        self.assertEqual(result.inferred_values["time"].source, "current_state:cursor_position")

    def test_infer_time_fallback_to_cursor(self):
        """Fallback to cursor position when no explicit time."""
        result = self.engine.infer_values(
            gaps=[],
            missing_parameters=["time"],
            user_message="split",
            current_state={"cursor_position": 25.0},
            tool_name="split_at_time"
        )
        self.assertIn("time", result.inferred_values)
        self.assertEqual(result.inferred_values["time"].value, 25.0)
        self.assertEqual(result.inferred_values["time"].source, "fallback:cursor_position")
        self.assertEqual(result.inferred_values["time"].confidence, 0.5)

    def test_cannot_infer_time_without_any_info(self):
        """Cannot infer time without message or state."""
        result = self.engine.infer_values(
            gaps=[],
            missing_parameters=["time"],
            user_message="split",
            current_state={},  # No cursor
            tool_name="split_at_time"
        )
        self.assertNotIn("time", result.inferred_values)
        self.assertIn("parameter:time", result.unresolved)
        self.assertTrue(result.needs_user_clarification)


class TestStateInference(unittest.TestCase):
    """Test state gap inference."""

    def setUp(self):
        self.engine = ValueInferenceEngine()

    def test_infer_selection_from_first_x_seconds(self):
        """Infer time selection from 'first X seconds'."""
        gaps = [
            StateGap(
                state_key=StateKey.HAS_TIME_SELECTION,
                required=True,
                current_value=False,
                needs_value=True,
                suggested_tool="set_time_selection"
            ),
            StateGap(
                state_key=StateKey.SELECTION_START_TIME,
                required=True,
                current_value=None,
                needs_value=True,
                suggested_tool="set_time_selection"
            ),
            StateGap(
                state_key=StateKey.SELECTION_END_TIME,
                required=True,
                current_value=None,
                needs_value=True,
                suggested_tool="set_time_selection"
            ),
        ]
        result = self.engine.infer_values(
            gaps=gaps,
            missing_parameters=[],
            user_message="trim first 30 seconds",
            current_state={},
            tool_name="trim_to_selection"
        )
        self.assertIn("has_time_selection", result.inferred_values)
        self.assertIn("selection_start_time", result.inferred_values)
        self.assertIn("selection_end_time", result.inferred_values)
        self.assertEqual(result.inferred_values["selection_start_time"].value, 0.0)
        self.assertEqual(result.inferred_values["selection_end_time"].value, 30.0)

    def test_infer_selection_from_range(self):
        """Infer time selection from time range."""
        gaps = [
            StateGap(StateKey.HAS_TIME_SELECTION, True, False, True, "set_time_selection"),
            StateGap(StateKey.SELECTION_START_TIME, True, None, True, "set_time_selection"),
            StateGap(StateKey.SELECTION_END_TIME, True, None, True, "set_time_selection"),
        ]
        result = self.engine.infer_values(
            gaps=gaps,
            missing_parameters=[],
            user_message="delete from 10 to 20 seconds",
            current_state={},
            tool_name="delete_selection"
        )
        self.assertEqual(result.inferred_values["selection_start_time"].value, 10.0)
        self.assertEqual(result.inferred_values["selection_end_time"].value, 20.0)

    def test_infer_track_selection_from_all_tracks(self):
        """Infer track selection from 'all tracks' keyword."""
        gap = StateGap(
            state_key=StateKey.SELECTED_TRACKS,
            required=True,
            current_value=[],
            needs_value=True,
            suggested_tool="select_all_tracks"
        )
        result = self.engine.infer_values(
            gaps=[gap],
            missing_parameters=[],
            user_message="normalize all tracks",
            current_state={"track_list": [1, 2, 3]},
            tool_name="apply_normalize"
        )
        self.assertIn("selected_tracks", result.inferred_values)
        self.assertEqual(result.inferred_values["selected_tracks"].value, "all")

    def test_infer_track_selection_default(self):
        """Default to all tracks (common audio editor behavior)."""
        gap = StateGap(
            state_key=StateKey.SELECTED_TRACKS,
            required=True,
            current_value=[],
            needs_value=True,
            suggested_tool="select_all_tracks"
        )
        result = self.engine.infer_values(
            gaps=[gap],
            missing_parameters=[],
            user_message="trim first 30 seconds",
            current_state={"track_list": [1, 2]},
            tool_name="trim_to_selection"
        )
        self.assertIn("selected_tracks", result.inferred_values)
        self.assertEqual(result.inferred_values["selected_tracks"].value, "all")
        # Default is 0.8 confidence - reasonable default matching audio editor behavior
        self.assertEqual(result.inferred_values["selected_tracks"].confidence, 0.8)


class TestClarificationMessages(unittest.TestCase):
    """Test clarification message generation."""

    def setUp(self):
        self.engine = ValueInferenceEngine()

    def test_clarification_for_missing_time(self):
        """Generate clarification for missing time parameter."""
        result = self.engine.infer_values(
            gaps=[],
            missing_parameters=["time"],
            user_message="split",
            current_state={},
            tool_name="split_at_time"
        )
        self.assertTrue(result.needs_user_clarification)
        self.assertIn("time", result.clarification_message.lower())

    def test_clarification_for_missing_selection(self):
        """Generate clarification for missing time selection."""
        gap = StateGap(
            state_key=StateKey.HAS_TIME_SELECTION,
            required=True,
            current_value=False,
            needs_value=True,
            suggested_tool="set_time_selection"
        )
        result = self.engine.infer_values(
            gaps=[gap],
            missing_parameters=[],
            user_message="cut",
            current_state={},
            tool_name="cut"
        )
        self.assertTrue(result.needs_user_clarification)
        self.assertIn("time range", result.clarification_message.lower())


class TestComplexInference(unittest.TestCase):
    """Test complex inference scenarios."""

    def setUp(self):
        self.engine = ValueInferenceEngine()

    def test_split_at_20_seconds_full_flow(self):
        """Test 'split at 20 seconds' - should infer time=20."""
        result = self.engine.infer_values(
            gaps=[],
            missing_parameters=["time"],
            user_message="split at 20 seconds",
            current_state={"cursor_position": 10.0},  # Ignored
            tool_name="split_at_time"
        )
        self.assertFalse(result.needs_user_clarification)
        self.assertEqual(result.inferred_values["time"].value, 20.0)
        # Should use message, not cursor
        self.assertEqual(result.inferred_values["time"].source, "user_message")

    def test_trim_first_30_seconds_full_flow(self):
        """Test 'trim first 30 seconds' - should infer selection and tracks."""
        gaps = [
            StateGap(StateKey.HAS_TIME_SELECTION, True, False, True, "set_time_selection"),
            StateGap(StateKey.SELECTION_START_TIME, True, None, True, "set_time_selection"),
            StateGap(StateKey.SELECTION_END_TIME, True, None, True, "set_time_selection"),
            StateGap(StateKey.SELECTED_TRACKS, True, [], True, "select_all_tracks"),
        ]
        result = self.engine.infer_values(
            gaps=gaps,
            missing_parameters=[],
            user_message="trim first 30 seconds",
            current_state={"track_list": [1, 2, 3], "total_project_time": 120.0},
            tool_name="trim_to_selection"
        )
        self.assertFalse(result.needs_user_clarification)
        self.assertEqual(result.inferred_values["selection_start_time"].value, 0.0)
        self.assertEqual(result.inferred_values["selection_end_time"].value, 30.0)
        self.assertEqual(result.inferred_values["selected_tracks"].value, "all")

    def test_delete_last_10_seconds_full_flow(self):
        """Test 'delete last 10 seconds' - should calculate from project duration."""
        gaps = [
            StateGap(StateKey.HAS_TIME_SELECTION, True, False, True, "set_time_selection"),
            StateGap(StateKey.SELECTION_START_TIME, True, None, True, "set_time_selection"),
            StateGap(StateKey.SELECTION_END_TIME, True, None, True, "set_time_selection"),
        ]
        result = self.engine.infer_values(
            gaps=gaps,
            missing_parameters=[],
            user_message="delete last 10 seconds",
            current_state={"total_project_time": 60.0, "track_list": [1]},
            tool_name="delete_selection"
        )
        self.assertEqual(result.inferred_values["selection_start_time"].value, 50.0)
        self.assertEqual(result.inferred_values["selection_end_time"].value, 60.0)


class TestConvenienceFunction(unittest.TestCase):
    """Test convenience function."""

    def test_infer_missing_values(self):
        """Test infer_missing_values convenience function."""
        result = infer_missing_values(
            gaps=[],
            missing_parameters=["time"],
            user_message="split at 25s",
            current_state={},
            tool_name="split_at_time"
        )
        self.assertIsInstance(result, InferenceResult)
        self.assertEqual(result.inferred_values["time"].value, 25.0)


if __name__ == "__main__":
    unittest.main()
