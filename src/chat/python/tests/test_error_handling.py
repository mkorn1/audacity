#!/usr/bin/env python3
"""
Unit tests for error handling across all phases

Tests:
- State discovery errors
- Intent planning errors
- State preparation errors (replaced prerequisite resolution)
- Execution errors
- Partial execution failures
- Error messages are helpful

NOTE: As of the State Preparation architecture update (2025-12-06),
prerequisite_resolver has been replaced by state_preparation.
"""

import unittest
import sys
import os
from unittest.mock import Mock, MagicMock, patch

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from planning_orchestrator import PlanningOrchestrator
from planning_state import PlanningPhase
from orchestrator import OrchestratorAgent


class TestErrorHandling(unittest.TestCase):
    """Test error handling across all phases"""

    def setUp(self):
        """Set up test fixtures"""
        self.tool_registry = Mock()
        self.orchestrator_agent = Mock(spec=OrchestratorAgent)
        self.orchestrator = PlanningOrchestrator(self.tool_registry, self.orchestrator_agent)

    def test_state_discovery_error(self):
        """Test error handling when state discovery fails"""
        # Mock state discovery to raise exception
        self.orchestrator.state_discovery.discover_state = Mock(side_effect=Exception("C++ bridge failure"))

        response = self.orchestrator.process_request("test message")

        self.assertEqual(response["type"], "error")
        self.assertIn("State discovery failed", response["content"])

    def test_intent_planning_error(self):
        """Test error handling when intent planning fails"""
        # Mock state discovery to succeed
        self.orchestrator.state_discovery.discover_state = Mock(return_value={"project_open": True})

        # Mock intent planner to raise exception
        self.orchestrator.intent_planner.plan = Mock(side_effect=Exception("LLM API failure"))

        response = self.orchestrator.process_request("test message")

        self.assertEqual(response["type"], "error")
        self.assertIn("Intent planning failed", response["content"])

    def test_state_preparation_error(self):
        """Test error handling when state preparation fails"""
        # Mock earlier phases to succeed
        self.orchestrator.state_discovery.discover_state = Mock(return_value={"project_open": True})
        self.orchestrator.intent_planner.plan = Mock(return_value=(
            [{"tool_name": "trim_to_selection", "arguments": {}}],
            False,
            None
        ))

        # Mock state preparation to raise exception
        self.orchestrator.state_preparation.prepare = Mock(side_effect=Exception("State preparation error"))

        response = self.orchestrator.process_request("trim selection")

        self.assertEqual(response["type"], "error")
        # Could be state preparation or prerequisite error depending on fallback
        self.assertIn("error", response["content"].lower())

    def test_state_preparation_needs_clarification(self):
        """Test handling when state preparation needs user clarification"""
        from state_preparation import PreparationResult

        # Mock earlier phases
        self.orchestrator.state_discovery.discover_state = Mock(return_value={"project_open": True, "has_time_selection": False})
        self.orchestrator.intent_planner.plan = Mock(return_value=(
            [{"tool_name": "trim_to_selection", "arguments": {}}],
            False,
            None
        ))

        # Mock state preparation to need clarification
        self.orchestrator.state_preparation.prepare = Mock(return_value=PreparationResult(
            ready_to_execute=False,
            preparation_steps=[],
            operation_tool="trim_to_selection",
            operation_arguments={},
            error=None,
            needs_clarification=True,
            clarification_message="Please specify what portion to trim (e.g., 'first 30 seconds', 'from 10 to 20 seconds')"
        ))

        response = self.orchestrator.process_request("trim selection")

        self.assertEqual(response["type"], "clarification_needed")
        self.assertIn("specify", response["content"].lower())

    def test_execution_error(self):
        """Test error handling when tool execution fails"""
        from state_preparation import PreparationResult

        # Mock earlier phases to succeed
        self.orchestrator.state_discovery.discover_state = Mock(return_value={"project_open": True})
        self.orchestrator.intent_planner.plan = Mock(return_value=(
            [{"tool_name": "play", "arguments": {}}],
            False,
            None
        ))
        self.orchestrator.state_preparation.prepare = Mock(return_value=PreparationResult(
            ready_to_execute=True,
            preparation_steps=[],
            operation_tool="play",
            operation_arguments={},
            error=None,
            needs_clarification=False,
            clarification_message=None
        ))

        # Mock tool execution to fail
        self.tool_registry.execute_by_name.return_value = {
            "success": False,
            "error": "Playback device not available"
        }

        response = self.orchestrator.process_request("play")

        self.assertEqual(response["type"], "message")
        self.assertIn("error", response["content"].lower())
        self.assertFalse(response["can_undo"])

    def test_partial_execution_failure(self):
        """Test handling of partial execution failures"""
        from state_preparation import PreparationResult, PreparationStep

        # Mock earlier phases
        self.orchestrator.state_discovery.discover_state = Mock(return_value={"project_open": True})
        self.orchestrator.intent_planner.plan = Mock(return_value=(
            [{"tool_name": "trim_to_selection", "arguments": {}}],
            False,
            None
        ))

        # Mock state preparation with preparation steps
        self.orchestrator.state_preparation.prepare = Mock(return_value=PreparationResult(
            ready_to_execute=True,
            preparation_steps=[
                PreparationStep(
                    tool_name="set_time_selection",
                    arguments={"start_time": 0, "end_time": 10},
                    purpose="Set selection from 0s to 10s"
                )
            ],
            operation_tool="trim_to_selection",
            operation_arguments={},
            error=None,
            needs_clarification=False,
            clarification_message=None
        ))

        # Mock orchestrator agent to return execution results
        self.orchestrator_agent._execute_tool_calls = Mock(return_value={
            "type": "message",
            "content": "Error: No selection found",
            "can_undo": False
        })

        # Mock first tool to succeed, second to fail
        def execute_side_effect(tool_name, args):
            if tool_name == "set_time_selection":
                return {"success": True}
            else:
                return {"success": False, "error": "No selection found"}

        self.tool_registry.execute_by_name.side_effect = execute_side_effect

        response = self.orchestrator.process_request("trim to 0-10 seconds")

        self.assertEqual(response["type"], "message")
        self.assertIn("error", response["content"].lower())
        self.assertFalse(response["can_undo"])

    def test_error_messages_are_helpful(self):
        """Test that error messages are helpful and actionable"""
        from state_preparation import PreparationResult

        # Test clarification error message
        self.orchestrator.state_discovery.discover_state = Mock(return_value={"project_open": True})
        self.orchestrator.intent_planner.plan = Mock(return_value=(
            [{"tool_name": "trim_to_selection", "arguments": {}}],
            False,
            None
        ))
        self.orchestrator.state_preparation.prepare = Mock(return_value=PreparationResult(
            ready_to_execute=False,
            preparation_steps=[],
            operation_tool="trim_to_selection",
            operation_arguments={},
            error=None,
            needs_clarification=True,
            clarification_message="Please specify a time range for the trim operation (e.g., 'first 30 seconds')"
        ))

        response = self.orchestrator.process_request("trim")

        self.assertEqual(response["type"], "clarification_needed")
        # Error message should be user-friendly
        self.assertIn("time range", response["content"].lower())

    def test_unexpected_error_handling(self):
        """Test handling of unexpected errors"""
        # Mock to raise unexpected exception
        self.orchestrator.state_discovery.discover_state = Mock(side_effect=KeyError("Unexpected key"))

        response = self.orchestrator.process_request("test")

        self.assertEqual(response["type"], "error")
        self.assertIn("error", response["content"].lower())


if __name__ == '__main__':
    unittest.main()
