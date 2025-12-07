#!/usr/bin/env python3
"""
Unit tests for state_verification.py
"""

import sys
import os
import unittest
from unittest.mock import Mock

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from state_verification import (
    StateVerifier,
    VerificationResult,
    verify_tool_execution,
)


class TestStateVerifierBasics(unittest.TestCase):
    """Test basic StateVerifier functionality."""

    def setUp(self):
        self.verifier = StateVerifier()

    def test_unknown_tool_returns_success(self):
        """Unknown tools (no contract) should return success."""
        result = self.verifier.verify_state_change(
            tool_name="unknown_tool",
            expected_state={},
            pre_execution_state={}
        )
        self.assertTrue(result.success)
        self.assertEqual(len(result.discrepancies), 0)

    def test_tool_without_state_writes_returns_success(self):
        """Tools without state_writes should return success."""
        result = self.verifier.verify_state_change(
            tool_name="play",
            expected_state={},
            pre_execution_state={}
        )
        self.assertTrue(result.success)


class TestValueMatching(unittest.TestCase):
    """Test value matching logic."""

    def setUp(self):
        self.verifier = StateVerifier()

    def test_boolean_match(self):
        """Boolean values should match exactly."""
        self.assertTrue(self.verifier._values_match("has_time_selection", True, True))
        self.assertFalse(self.verifier._values_match("has_time_selection", True, False))

    def test_numeric_match_with_tolerance(self):
        """Numeric values should match within tolerance."""
        self.assertTrue(self.verifier._values_match("cursor_position", 10.0, 10.005))
        self.assertTrue(self.verifier._values_match("selection_start_time", 0.0, 0.001))
        self.assertFalse(self.verifier._values_match("cursor_position", 10.0, 10.02))

    def test_list_match(self):
        """List values should match (order independent)."""
        self.assertTrue(self.verifier._values_match("selected_tracks", [1, 2], [2, 1]))
        self.assertFalse(self.verifier._values_match("selected_tracks", [1, 2], [1, 2, 3]))

    def test_any_marker(self):
        """'any' marker should match any non-empty value."""
        self.assertTrue(self.verifier._values_match("selected_tracks", "any", [1, 2]))
        self.assertFalse(self.verifier._values_match("selected_tracks", "any", []))


class TestVerificationWithMockRegistry(unittest.TestCase):
    """Test verification with mock tool registry."""

    def setUp(self):
        self.mock_registry = Mock()
        self.verifier = StateVerifier(self.mock_registry)

    def test_verify_set_time_selection(self):
        """Verify set_time_selection sets selection state correctly."""
        # Mock the state queries
        def mock_execute(tool_name, args):
            if tool_name == "has_time_selection":
                return {"success": True, "value": True}
            elif tool_name == "get_selection_start_time":
                return {"success": True, "value": 10.0}
            elif tool_name == "get_selection_end_time":
                return {"success": True, "value": 20.0}
            return {"success": False}

        self.mock_registry.execute_by_name.side_effect = mock_execute

        result = self.verifier.verify_state_change(
            tool_name="set_time_selection",
            expected_state={
                "has_time_selection": True,
                "selection_start_time": 10.0,
                "selection_end_time": 20.0
            },
            pre_execution_state={}
        )

        self.assertTrue(result.success)
        self.assertEqual(len(result.discrepancies), 0)

    def test_verify_set_time_selection_detects_mismatch(self):
        """Verify detection of state mismatch after set_time_selection."""
        # Mock the state queries to return wrong values
        def mock_execute(tool_name, args):
            if tool_name == "has_time_selection":
                return {"success": True, "value": False}  # Wrong!
            return {"success": True, "value": 0.0}

        self.mock_registry.execute_by_name.side_effect = mock_execute

        result = self.verifier.verify_state_change(
            tool_name="set_time_selection",
            expected_state={
                "has_time_selection": True,
                "selection_start_time": 10.0,
                "selection_end_time": 20.0
            },
            pre_execution_state={}
        )

        self.assertFalse(result.success)
        self.assertIn("has_time_selection", result.discrepancies)


class TestVerifyPreparationStep(unittest.TestCase):
    """Test verify_preparation_step method."""

    def setUp(self):
        self.mock_registry = Mock()
        self.verifier = StateVerifier(self.mock_registry)

    def test_verify_preparation_step_set_time_selection(self):
        """Verify preparation step for set_time_selection."""
        # Mock successful state queries
        def mock_execute(tool_name, args):
            if tool_name == "has_time_selection":
                return {"success": True, "value": True}
            elif tool_name == "get_selection_start_time":
                return {"success": True, "value": 5.0}
            elif tool_name == "get_selection_end_time":
                return {"success": True, "value": 15.0}
            return {"success": False}

        self.mock_registry.execute_by_name.side_effect = mock_execute

        result = self.verifier.verify_preparation_step(
            step_tool_name="set_time_selection",
            step_arguments={"start_time": 5.0, "end_time": 15.0}
        )

        self.assertTrue(result.success)

    def test_verify_preparation_step_seek(self):
        """Verify preparation step for seek."""
        def mock_execute(tool_name, args):
            if tool_name == "get_cursor_position":
                return {"success": True, "value": 25.0}
            return {"success": False}

        self.mock_registry.execute_by_name.side_effect = mock_execute

        result = self.verifier.verify_preparation_step(
            step_tool_name="seek",
            step_arguments={"time": 25.0}
        )

        self.assertTrue(result.success)


class TestGetStateSnapshot(unittest.TestCase):
    """Test get_state_snapshot method."""

    def setUp(self):
        self.mock_registry = Mock()
        self.verifier = StateVerifier(self.mock_registry)

    def test_get_state_snapshot(self):
        """Get full state snapshot."""
        def mock_execute(tool_name, args):
            values = {
                "has_time_selection": True,
                "get_selection_start_time": 0.0,
                "get_selection_end_time": 10.0,
                "get_cursor_position": 5.0,
                "get_selected_tracks": [1, 2],
                "get_selected_clips": [],
                "get_track_list": [1, 2, 3],
                "get_total_project_time": 120.0,
            }
            return {"success": True, "value": values.get(tool_name)}

        self.mock_registry.execute_by_name.side_effect = mock_execute

        snapshot = self.verifier.get_state_snapshot()

        self.assertIn("has_time_selection", snapshot)
        self.assertIn("cursor_position", snapshot)
        self.assertIn("track_list", snapshot)


class TestConvenienceFunction(unittest.TestCase):
    """Test convenience function."""

    def test_verify_tool_execution(self):
        """Test verify_tool_execution convenience function."""
        result = verify_tool_execution(
            tool_name="play",  # No state writes
            expected_state={},
            tool_registry=None
        )
        self.assertIsInstance(result, VerificationResult)
        self.assertTrue(result.success)


if __name__ == "__main__":
    unittest.main()
