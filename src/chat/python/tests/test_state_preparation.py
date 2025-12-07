#!/usr/bin/env python3
"""
Unit tests for state_preparation.py
"""

import sys
import os
import unittest

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from state_preparation import (
    StatePreparationOrchestrator,
    PreparationStep,
    PreparationResult,
    prepare_tool_execution,
)


class TestStatePreparationBasics(unittest.TestCase):
    """Test basic StatePreparationOrchestrator functionality."""

    def setUp(self):
        self.orchestrator = StatePreparationOrchestrator()

    def test_tool_with_no_requirements_ready_immediately(self):
        """Tools with no requirements should be ready immediately."""
        result = self.orchestrator.prepare(
            tool_name="play",
            tool_arguments={},
            user_message="play",
            initial_state={}
        )
        self.assertTrue(result.ready_to_execute)
        self.assertEqual(len(result.preparation_steps), 0)
        self.assertFalse(result.needs_clarification)


class TestSplitAtTimePreparation(unittest.TestCase):
    """Test state preparation for split_at_time."""

    def setUp(self):
        self.orchestrator = StatePreparationOrchestrator()

    def test_split_at_time_with_time_ready(self):
        """split_at_time with time argument should be ready."""
        result = self.orchestrator.prepare(
            tool_name="split_at_time",
            tool_arguments={"time": 20.0},
            user_message="split at 20 seconds",
            initial_state={}
        )
        self.assertTrue(result.ready_to_execute)
        self.assertEqual(len(result.preparation_steps), 0)
        self.assertEqual(result.operation_arguments["time"], 20.0)

    def test_split_at_time_infers_from_message(self):
        """split_at_time without time should infer from message."""
        result = self.orchestrator.prepare(
            tool_name="split_at_time",
            tool_arguments={},
            user_message="split at 25 seconds",
            initial_state={}
        )
        self.assertTrue(result.ready_to_execute)
        self.assertEqual(result.operation_arguments["time"], 25.0)

    def test_split_at_time_infers_from_cursor(self):
        """split_at_time without explicit time uses cursor as fallback."""
        result = self.orchestrator.prepare(
            tool_name="split_at_time",
            tool_arguments={},
            user_message="split",
            initial_state={"cursor_position": 15.0}
        )
        self.assertTrue(result.ready_to_execute)
        self.assertEqual(result.operation_arguments["time"], 15.0)

    def test_split_at_time_needs_clarification_without_info(self):
        """split_at_time without time or cursor needs clarification."""
        result = self.orchestrator.prepare(
            tool_name="split_at_time",
            tool_arguments={},
            user_message="split",
            initial_state={}
        )
        self.assertFalse(result.ready_to_execute)
        self.assertTrue(result.needs_clarification)
        self.assertIn("time", result.clarification_message.lower())


class TestTrimToSelectionPreparation(unittest.TestCase):
    """Test state preparation for trim_to_selection."""

    def setUp(self):
        self.orchestrator = StatePreparationOrchestrator()

    def test_trim_with_selection_ready(self):
        """trim_to_selection with existing selection should be ready."""
        result = self.orchestrator.prepare(
            tool_name="trim_to_selection",
            tool_arguments={},
            user_message="trim",
            initial_state={
                "has_time_selection": True,
                "selection_start_time": 5.0,
                "selection_end_time": 15.0,
                "selected_tracks": [1, 2]
            }
        )
        self.assertTrue(result.ready_to_execute)
        self.assertEqual(len(result.preparation_steps), 0)

    def test_trim_first_30_seconds_generates_steps(self):
        """'trim first 30 seconds' should generate set_time_selection and select_all_tracks."""
        result = self.orchestrator.prepare(
            tool_name="trim_to_selection",
            tool_arguments={},
            user_message="trim first 30 seconds",
            initial_state={
                "track_list": [1, 2, 3],
                "total_project_time": 120.0
            }
        )
        self.assertTrue(result.ready_to_execute)

        # Should have preparation steps
        self.assertGreater(len(result.preparation_steps), 0)

        # Should have set_time_selection step
        time_step = next((s for s in result.preparation_steps if s.tool_name == "set_time_selection"), None)
        self.assertIsNotNone(time_step)
        self.assertEqual(time_step.arguments["start_time"], 0.0)
        self.assertEqual(time_step.arguments["end_time"], 30.0)

        # Should have select_all_tracks step
        track_step = next((s for s in result.preparation_steps if s.tool_name == "select_all_tracks"), None)
        self.assertIsNotNone(track_step)

    def test_trim_without_info_needs_clarification(self):
        """'trim' without selection or time range needs clarification."""
        result = self.orchestrator.prepare(
            tool_name="trim_to_selection",
            tool_arguments={},
            user_message="trim",
            initial_state={"track_list": [1]}
        )
        self.assertFalse(result.ready_to_execute)
        self.assertTrue(result.needs_clarification)


class TestCutPreparation(unittest.TestCase):
    """Test state preparation for cut."""

    def setUp(self):
        self.orchestrator = StatePreparationOrchestrator()

    def test_cut_with_selection_ready(self):
        """cut with existing selection should be ready."""
        result = self.orchestrator.prepare(
            tool_name="cut",
            tool_arguments={},
            user_message="cut",
            initial_state={
                "has_time_selection": True,
                "selection_start_time": 10.0,
                "selection_end_time": 20.0,
                "selected_tracks": [1]
            }
        )
        self.assertTrue(result.ready_to_execute)
        self.assertEqual(len(result.preparation_steps), 0)

    def test_cut_from_10_to_20_generates_steps(self):
        """'cut from 10 to 20 seconds' should generate preparation steps."""
        result = self.orchestrator.prepare(
            tool_name="cut",
            tool_arguments={},
            user_message="cut from 10 to 20 seconds",
            initial_state={"track_list": [1, 2]}
        )
        self.assertTrue(result.ready_to_execute)

        # Should have set_time_selection step
        time_step = next((s for s in result.preparation_steps if s.tool_name == "set_time_selection"), None)
        self.assertIsNotNone(time_step)
        self.assertEqual(time_step.arguments["start_time"], 10.0)
        self.assertEqual(time_step.arguments["end_time"], 20.0)


class TestDeleteLastXSecondsPreparation(unittest.TestCase):
    """Test state preparation for delete with relative time."""

    def setUp(self):
        self.orchestrator = StatePreparationOrchestrator()

    def test_delete_last_10_seconds(self):
        """'delete last 10 seconds' should calculate from project duration."""
        result = self.orchestrator.prepare(
            tool_name="delete_selection",
            tool_arguments={},
            user_message="delete last 10 seconds",
            initial_state={
                "total_project_time": 60.0,
                "track_list": [1]
            }
        )
        self.assertTrue(result.ready_to_execute)

        time_step = next((s for s in result.preparation_steps if s.tool_name == "set_time_selection"), None)
        self.assertIsNotNone(time_step)
        self.assertEqual(time_step.arguments["start_time"], 50.0)
        self.assertEqual(time_step.arguments["end_time"], 60.0)


class TestPastePreparation(unittest.TestCase):
    """Test state preparation for paste."""

    def setUp(self):
        self.orchestrator = StatePreparationOrchestrator()

    def test_paste_with_cursor_ready(self):
        """paste with cursor position should be ready."""
        result = self.orchestrator.prepare(
            tool_name="paste",
            tool_arguments={},
            user_message="paste",
            initial_state={"cursor_position": 10.0}
        )
        self.assertTrue(result.ready_to_execute)
        self.assertEqual(len(result.preparation_steps), 0)


class TestPreparationStepGeneration(unittest.TestCase):
    """Test preparation step generation details."""

    def setUp(self):
        self.orchestrator = StatePreparationOrchestrator()

    def test_steps_have_purpose(self):
        """All preparation steps should have a purpose description."""
        result = self.orchestrator.prepare(
            tool_name="trim_to_selection",
            tool_arguments={},
            user_message="trim first 30 seconds",
            initial_state={"track_list": [1]}
        )

        for step in result.preparation_steps:
            self.assertIsInstance(step.purpose, str)
            self.assertGreater(len(step.purpose), 0)

    def test_steps_have_tool_name(self):
        """All preparation steps should have tool_name."""
        result = self.orchestrator.prepare(
            tool_name="cut",
            tool_arguments={},
            user_message="cut from 5 to 10 seconds",
            initial_state={"track_list": [1]}
        )

        for step in result.preparation_steps:
            self.assertIsInstance(step.tool_name, str)
            self.assertGreater(len(step.tool_name), 0)


class TestConvenienceFunction(unittest.TestCase):
    """Test convenience function."""

    def test_prepare_tool_execution(self):
        """Test prepare_tool_execution convenience function."""
        result = prepare_tool_execution(
            tool_name="play",
            tool_arguments={},
            user_message="play",
            current_state={}
        )
        self.assertIsInstance(result, PreparationResult)
        self.assertTrue(result.ready_to_execute)


class TestMultipleToolPreparation(unittest.TestCase):
    """Test preparing multiple tools in sequence."""

    def setUp(self):
        self.orchestrator = StatePreparationOrchestrator()

    def test_prepare_multiple_tools(self):
        """Test preparing multiple tools that build on each other."""
        tool_calls = [
            {"tool_name": "set_time_selection", "arguments": {"start_time": 0, "end_time": 30}},
            {"tool_name": "cut", "arguments": {}}
        ]

        results = self.orchestrator.prepare_multiple_tools(
            tool_calls=tool_calls,
            user_message="cut first 30 seconds",
            initial_state={"track_list": [1], "selected_tracks": [1]}
        )

        # Both should be ready
        self.assertEqual(len(results), 2)
        self.assertTrue(results[0].ready_to_execute)
        self.assertTrue(results[1].ready_to_execute)


class TestIterationLimit(unittest.TestCase):
    """Test iteration limit handling."""

    def setUp(self):
        self.orchestrator = StatePreparationOrchestrator()

    def test_max_iterations_error(self):
        """Should error if max iterations exceeded (edge case)."""
        # This is hard to trigger naturally, but we verify the limit exists
        self.assertEqual(self.orchestrator.MAX_ITERATIONS, 5)


if __name__ == "__main__":
    unittest.main()
