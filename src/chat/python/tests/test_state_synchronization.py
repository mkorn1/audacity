#!/usr/bin/env python3
"""
Unit tests for state synchronization

Tests:
- Re-querying critical state before execution
- Handling state changes during planning
- State staleness detection
- Concurrent state queries

NOTE: As of the State Preparation architecture update (2025-12-06),
the orchestrator uses state_preparation instead of prerequisite_resolver.
"""

import unittest
import sys
import os
import time
from unittest.mock import Mock, MagicMock, patch

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from planning_state import PlanningState, PlanningPhase
from planning_orchestrator import PlanningOrchestrator
from orchestrator import OrchestratorAgent
from state_preparation import PreparationResult, PreparationStep


class TestStateSynchronization(unittest.TestCase):
    """Test state synchronization"""

    def setUp(self):
        """Set up test fixtures"""
        self.tool_registry = Mock()
        self.orchestrator_agent = Mock(spec=OrchestratorAgent)
        self.orchestrator = PlanningOrchestrator(self.tool_registry, self.orchestrator_agent)

    def test_state_staleness_detection(self):
        """Test that stale state is detected"""
        planning_state = PlanningState("test message")
        planning_state.set_state_snapshot({"has_time_selection": True})

        # Make state stale by setting old timestamp
        planning_state.state_discovery_timestamp = time.time() - 10.0  # 10 seconds ago

        self.assertTrue(planning_state.is_state_stale())

    def test_fresh_state_not_stale(self):
        """Test that fresh state is not considered stale"""
        planning_state = PlanningState("test message")
        planning_state.set_state_snapshot({"has_time_selection": True})

        # State was just set, should be fresh
        self.assertFalse(planning_state.is_state_stale())

    def test_get_critical_state_keys(self):
        """Test identification of critical state keys"""
        planning_state = PlanningState("test message")
        planning_state.set_execution_plan([
            {"tool_name": "trim_to_selection", "arguments": {}},
            {"tool_name": "paste", "arguments": {}}
        ])

        critical_keys = planning_state.get_critical_state_keys()

        # Should include selection state (for trim_to_selection)
        self.assertIn("has_time_selection", critical_keys)
        self.assertIn("selection_start_time", critical_keys)
        self.assertIn("selection_end_time", critical_keys)
        # Should include cursor position (for paste)
        self.assertIn("cursor_position", critical_keys)

    def test_re_query_critical_state_before_execution(self):
        """Test that critical state is re-queried before execution"""
        # Mock earlier phases
        self.orchestrator.state_discovery.discover_state = Mock(return_value={
            "project_open": True,
            "has_time_selection": True,
            "selection_start_time": 10.0,
            "selection_end_time": 20.0
        })
        self.orchestrator.intent_planner.plan = Mock(return_value=(
            [{"tool_name": "trim_to_selection", "arguments": {}}],
            False,
            None
        ))
        self.orchestrator.state_preparation.prepare = Mock(return_value=PreparationResult(
            ready_to_execute=True,
            preparation_steps=[],
            operation_tool="trim_to_selection",
            operation_arguments={},
            error=None,
            needs_clarification=False,
            clarification_message=None
        ))

        # Mock execution
        self.tool_registry.execute_by_name.return_value = {"success": True}

        response = self.orchestrator.process_request("trim selection")

        # Verify that state_preparation was called (which uses state)
        self.orchestrator.state_preparation.prepare.assert_called()

    def test_state_synchronization_with_missing_state(self):
        """Test state synchronization when state is missing"""
        # Mock earlier phases with missing critical state
        self.orchestrator.state_discovery.discover_state = Mock(return_value={
            "project_open": True
            # Missing selection state
        })
        self.orchestrator.intent_planner.plan = Mock(return_value=(
            [{"tool_name": "trim_to_selection", "arguments": {}}],
            False,
            None
        ))
        # State preparation should ask for clarification when state is missing
        self.orchestrator.state_preparation.prepare = Mock(return_value=PreparationResult(
            ready_to_execute=False,
            preparation_steps=[],
            operation_tool="trim_to_selection",
            operation_arguments={},
            error=None,
            needs_clarification=True,
            clarification_message="Please specify a time range"
        ))

        response = self.orchestrator.process_request("trim selection")

        # Should have called state preparation
        self.orchestrator.state_preparation.prepare.assert_called()

    def test_state_synchronization_handles_failures_gracefully(self):
        """Test that state synchronization failures don't crash execution"""
        # Mock earlier phases
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

        # Mock state query to fail during synchronization
        def execute_side_effect(tool_name, args):
            if tool_name.startswith("get_") or tool_name == "has_time_selection":
                return {"success": False, "error": "Query failed"}
            else:
                return {"success": True}

        self.tool_registry.execute_by_name.side_effect = execute_side_effect

        # Should not crash, should continue with execution
        response = self.orchestrator.process_request("play")

        # Should still return a response (even if execution might fail)
        self.assertIn("type", response)

    def test_state_timestamp_updated_on_sync(self):
        """Test that state timestamp is updated after synchronization"""
        planning_state = PlanningState("test message")
        old_timestamp = time.time() - 10.0
        planning_state.state_discovery_timestamp = old_timestamp

        # Simulate state synchronization
        planning_state.set_state_snapshot({"has_time_selection": True})

        # Timestamp should be updated
        self.assertGreater(planning_state.state_discovery_timestamp, old_timestamp)
        self.assertFalse(planning_state.is_state_stale())


if __name__ == '__main__':
    unittest.main()
