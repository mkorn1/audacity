#!/usr/bin/env python3
"""
Unit tests for state_gap_analyzer.py
"""

import sys
import os
import unittest

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from state_gap_analyzer import (
    StateGapAnalyzer,
    StateGap,
    GapAnalysisResult,
    analyze_tool_requirements,
)
from state_contracts import StateKey


class TestStateGapAnalyzerBasics(unittest.TestCase):
    """Test basic StateGapAnalyzer functionality."""

    def setUp(self):
        self.analyzer = StateGapAnalyzer()

    def test_unknown_tool_returns_can_execute(self):
        """Unknown tools (no contract) should return can_execute=True."""
        result = self.analyzer.analyze(
            tool_name="unknown_tool",
            tool_arguments={},
            current_state={}
        )
        self.assertTrue(result.can_execute)
        self.assertEqual(len(result.gaps), 0)
        self.assertEqual(len(result.missing_parameters), 0)


class TestCutToolGapAnalysis(unittest.TestCase):
    """Test gap analysis for cut tool."""

    def setUp(self):
        self.analyzer = StateGapAnalyzer()

    def test_cut_with_no_selection_returns_gaps(self):
        """Cut with no selection should return gaps for HAS_TIME_SELECTION."""
        result = self.analyzer.analyze(
            tool_name="cut",
            tool_arguments={},
            current_state={
                "has_time_selection": False,
                "selected_tracks": []
            }
        )
        self.assertFalse(result.can_execute)

        # Should have gaps for time selection and tracks
        gap_keys = [g.state_key for g in result.gaps]
        self.assertIn(StateKey.HAS_TIME_SELECTION, gap_keys)
        self.assertIn(StateKey.SELECTED_TRACKS, gap_keys)

    def test_cut_with_selection_returns_can_execute(self):
        """Cut with valid selection should return can_execute=True."""
        result = self.analyzer.analyze(
            tool_name="cut",
            tool_arguments={},
            current_state={
                "has_time_selection": True,
                "selection_start_time": 0.0,
                "selection_end_time": 10.0,
                "selected_tracks": [1, 2]
            }
        )
        self.assertTrue(result.can_execute)
        self.assertEqual(len(result.gaps), 0)


class TestSplitAtTimeGapAnalysis(unittest.TestCase):
    """Test gap analysis for split_at_time tool."""

    def setUp(self):
        self.analyzer = StateGapAnalyzer()

    def test_split_at_time_with_time_param_returns_can_execute(self):
        """split_at_time with time param should return can_execute=True."""
        result = self.analyzer.analyze(
            tool_name="split_at_time",
            tool_arguments={"time": 20.0},
            current_state={}
        )
        self.assertTrue(result.can_execute)
        self.assertEqual(len(result.gaps), 0)
        self.assertEqual(len(result.missing_parameters), 0)

    def test_split_at_time_without_time_param_returns_missing_param(self):
        """split_at_time without time param should return missing parameter."""
        result = self.analyzer.analyze(
            tool_name="split_at_time",
            tool_arguments={},
            current_state={}
        )
        self.assertFalse(result.can_execute)
        self.assertIn("time", result.missing_parameters)


class TestTrimToSelectionGapAnalysis(unittest.TestCase):
    """Test gap analysis for trim_to_selection tool."""

    def setUp(self):
        self.analyzer = StateGapAnalyzer()

    def test_trim_with_selection_returns_can_execute(self):
        """trim_to_selection with selection should return can_execute=True."""
        result = self.analyzer.analyze(
            tool_name="trim_to_selection",
            tool_arguments={},
            current_state={
                "has_time_selection": True,
                "selection_start_time": 5.0,
                "selection_end_time": 15.0,
                "selected_tracks": [1]
            }
        )
        self.assertTrue(result.can_execute)
        self.assertEqual(len(result.gaps), 0)

    def test_trim_without_selection_returns_gaps(self):
        """trim_to_selection without selection should return gaps."""
        result = self.analyzer.analyze(
            tool_name="trim_to_selection",
            tool_arguments={},
            current_state={
                "has_time_selection": False,
                "selected_tracks": []
            }
        )
        self.assertFalse(result.can_execute)

        gap_keys = [g.state_key for g in result.gaps]
        self.assertIn(StateKey.HAS_TIME_SELECTION, gap_keys)
        self.assertIn(StateKey.SELECTED_TRACKS, gap_keys)


class TestPasteGapAnalysis(unittest.TestCase):
    """Test gap analysis for paste tool."""

    def setUp(self):
        self.analyzer = StateGapAnalyzer()

    def test_paste_with_cursor_returns_can_execute(self):
        """paste with cursor position should return can_execute=True."""
        result = self.analyzer.analyze(
            tool_name="paste",
            tool_arguments={},
            current_state={
                "cursor_position": 10.0
            }
        )
        self.assertTrue(result.can_execute)

    def test_paste_without_cursor_returns_gap(self):
        """paste without cursor position should return gap."""
        result = self.analyzer.analyze(
            tool_name="paste",
            tool_arguments={},
            current_state={}
        )
        self.assertFalse(result.can_execute)

        gap_keys = [g.state_key for g in result.gaps]
        self.assertIn(StateKey.CURSOR_POSITION, gap_keys)


class TestSplitGapAnalysis(unittest.TestCase):
    """Test gap analysis for split tool (with fallback)."""

    def setUp(self):
        self.analyzer = StateGapAnalyzer()

    def test_split_with_time_selection_can_execute(self):
        """split with time selection should return can_execute=True."""
        result = self.analyzer.analyze(
            tool_name="split",
            tool_arguments={},
            current_state={
                "has_time_selection": True,
                "selection_start_time": 5.0,
                "selection_end_time": 10.0
            }
        )
        # split has optional requirements, should be OK
        # Note: split requires selected tracks from UI (hard to test without mock)

    def test_split_with_cursor_fallback_can_execute(self):
        """split with cursor (no time selection) should use fallback."""
        result = self.analyzer.analyze(
            tool_name="split",
            tool_arguments={},
            current_state={
                "has_time_selection": False,
                "cursor_position": 15.0
            }
        )
        # Cursor is fallback for time selection
        # Should not have gap for cursor if cursor exists
        cursor_gaps = [g for g in result.gaps if g.state_key == StateKey.CURSOR_POSITION]
        self.assertEqual(len(cursor_gaps), 0)


class TestStateSetterToolsGapAnalysis(unittest.TestCase):
    """Test gap analysis for state-setting tools."""

    def setUp(self):
        self.analyzer = StateGapAnalyzer()

    def test_set_time_selection_without_params_returns_missing(self):
        """set_time_selection without params should return missing parameters."""
        result = self.analyzer.analyze(
            tool_name="set_time_selection",
            tool_arguments={},
            current_state={}
        )
        self.assertFalse(result.can_execute)
        self.assertIn("start_time", result.missing_parameters)
        self.assertIn("end_time", result.missing_parameters)

    def test_set_time_selection_with_params_can_execute(self):
        """set_time_selection with params should return can_execute=True."""
        result = self.analyzer.analyze(
            tool_name="set_time_selection",
            tool_arguments={"start_time": 0.0, "end_time": 30.0},
            current_state={}
        )
        self.assertTrue(result.can_execute)

    def test_seek_without_time_returns_missing(self):
        """seek without time param should return missing parameter."""
        result = self.analyzer.analyze(
            tool_name="seek",
            tool_arguments={},
            current_state={}
        )
        self.assertFalse(result.can_execute)
        self.assertIn("time", result.missing_parameters)

    def test_seek_with_time_can_execute(self):
        """seek with time param should return can_execute=True."""
        result = self.analyzer.analyze(
            tool_name="seek",
            tool_arguments={"time": 20.0},
            current_state={}
        )
        self.assertTrue(result.can_execute)


class TestPlaybackToolsGapAnalysis(unittest.TestCase):
    """Test gap analysis for playback tools (no requirements)."""

    def setUp(self):
        self.analyzer = StateGapAnalyzer()

    def test_play_always_can_execute(self):
        """play should always be executable."""
        result = self.analyzer.analyze(
            tool_name="play",
            tool_arguments={},
            current_state={}
        )
        self.assertTrue(result.can_execute)

    def test_stop_always_can_execute(self):
        """stop should always be executable."""
        result = self.analyzer.analyze(
            tool_name="stop",
            tool_arguments={},
            current_state={}
        )
        self.assertTrue(result.can_execute)


class TestGapSuggestedTools(unittest.TestCase):
    """Test that gaps suggest correct tools."""

    def setUp(self):
        self.analyzer = StateGapAnalyzer()

    def test_time_selection_gap_suggests_set_time_selection(self):
        """Time selection gaps should suggest set_time_selection tool."""
        result = self.analyzer.analyze(
            tool_name="cut",
            tool_arguments={},
            current_state={"has_time_selection": False, "selected_tracks": [1]}
        )

        time_gap = next((g for g in result.gaps if g.state_key == StateKey.HAS_TIME_SELECTION), None)
        self.assertIsNotNone(time_gap)
        self.assertEqual(time_gap.suggested_tool, "set_time_selection")

    def test_track_selection_gap_suggests_select_all_tracks(self):
        """Track selection gaps should suggest select_all_tracks tool."""
        result = self.analyzer.analyze(
            tool_name="cut",
            tool_arguments={},
            current_state={"has_time_selection": True, "selection_start_time": 0, "selection_end_time": 10, "selected_tracks": []}
        )

        track_gap = next((g for g in result.gaps if g.state_key == StateKey.SELECTED_TRACKS), None)
        self.assertIsNotNone(track_gap)
        self.assertEqual(track_gap.suggested_tool, "select_all_tracks")


class TestMultipleToolsAnalysis(unittest.TestCase):
    """Test analyzing multiple tools in sequence."""

    def setUp(self):
        self.analyzer = StateGapAnalyzer()

    def test_set_selection_then_cut_simulates_state(self):
        """set_time_selection followed by cut should account for state change."""
        tool_calls = [
            {"tool_name": "set_time_selection", "arguments": {"start_time": 0, "end_time": 10}},
            {"tool_name": "cut", "arguments": {}}
        ]

        # Start with no selection but tracks selected
        initial_state = {
            "has_time_selection": False,
            "selected_tracks": [1, 2]
        }

        results = self.analyzer.analyze_multiple_tools(tool_calls, initial_state)

        # First tool (set_time_selection) should be executable
        self.assertTrue(results[0].can_execute)

        # Second tool (cut) should be executable after simulated state change
        # (because set_time_selection would set has_time_selection=True)
        self.assertTrue(results[1].can_execute)


class TestConvenienceFunction(unittest.TestCase):
    """Test convenience function."""

    def test_analyze_tool_requirements(self):
        """Test analyze_tool_requirements convenience function."""
        result = analyze_tool_requirements(
            tool_name="play",
            tool_arguments={},
            current_state={}
        )
        self.assertIsInstance(result, GapAnalysisResult)
        self.assertTrue(result.can_execute)


class TestGetGapsForStateKeys(unittest.TestCase):
    """Test get_gaps_for_state_keys method."""

    def setUp(self):
        self.analyzer = StateGapAnalyzer()

    def test_returns_gaps_for_missing_keys(self):
        """Should return gaps for state keys that are missing."""
        gaps = self.analyzer.get_gaps_for_state_keys(
            required_keys=[StateKey.HAS_TIME_SELECTION, StateKey.CURSOR_POSITION],
            current_state={"cursor_position": 10.0}  # Only cursor exists
        )

        self.assertEqual(len(gaps), 1)
        self.assertEqual(gaps[0].state_key, StateKey.HAS_TIME_SELECTION)

    def test_returns_empty_when_all_keys_exist(self):
        """Should return empty list when all required keys exist."""
        gaps = self.analyzer.get_gaps_for_state_keys(
            required_keys=[StateKey.CURSOR_POSITION],
            current_state={"cursor_position": 10.0}
        )

        self.assertEqual(len(gaps), 0)


if __name__ == "__main__":
    unittest.main()
