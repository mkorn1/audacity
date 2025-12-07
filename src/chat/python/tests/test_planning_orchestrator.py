#!/usr/bin/env python3
"""
Unit tests for PlanningOrchestrator

Tests planning orchestrator including:
- Full request flow
- Conditional routing
- Error handling
- Integration with OrchestratorAgent

NOTE: As of the State Preparation architecture update (2025-12-06),
the orchestrator now uses state_preparation instead of prerequisite_resolver.
"""

import unittest
import sys
import os
import json
from unittest.mock import Mock, MagicMock, patch

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from planning_orchestrator import PlanningOrchestrator
from planning_state import PlanningPhase
from orchestrator import OrchestratorAgent
from state_preparation import PreparationResult, PreparationStep


class TestPlanningOrchestratorFullFlow(unittest.TestCase):
    """Test full planning orchestrator flow"""

    def setUp(self):
        """Set up test fixtures"""
        self.tool_registry = Mock()
        self.orchestrator_agent = Mock(spec=OrchestratorAgent)
        self.orchestrator = PlanningOrchestrator(self.tool_registry, self.orchestrator_agent)

        # Mock state discovery
        self.orchestrator.state_discovery.discover_state = Mock(return_value={
            "project_open": True,
            "has_time_selection": False
        })

        # Mock intent planner
        self.orchestrator.intent_planner.plan = Mock(return_value=(
            [{"tool_name": "set_time_selection", "arguments": {"start_time": 10.0, "end_time": 20.0}}],
            False,
            None
        ))

        # Mock state preparation
        self.orchestrator.state_preparation.prepare = Mock(return_value=PreparationResult(
            ready_to_execute=True,
            preparation_steps=[],
            operation_tool="set_time_selection",
            operation_arguments={"start_time": 10.0, "end_time": 20.0},
            error=None,
            needs_clarification=False,
            clarification_message=None
        ))

    def test_process_request_simple_flow(self):
        """Test processing simple request"""
        self.tool_registry.execute_by_name.return_value = {"success": True}

        response = self.orchestrator.process_request("trim to 10-20 seconds")

        self.assertIn("type", response)
        # Should execute tools directly (no approval needed for set_time_selection)
        self.tool_registry.execute_by_name.assert_called()

    def test_process_request_with_state_discovery(self):
        """Test processing request that needs state discovery"""
        self.orchestrator.state_discovery.discover_state.return_value = {
            "project_open": True,
            "has_time_selection": True,
            "selection_start_time": 10.0,
            "selection_end_time": 20.0
        }

        self.tool_registry.execute_by_name.return_value = {"success": True}

        response = self.orchestrator.process_request("trim this")

        # Should have called state discovery
        self.orchestrator.state_discovery.discover_state.assert_called()

    def test_process_request_with_state_preparation(self):
        """Test processing request that needs state preparation"""
        self.orchestrator.intent_planner.plan.return_value = (
            [{"tool_name": "trim_to_selection", "arguments": {}}],
            False,
            None
        )

        # Mock state preparation with preparation steps
        self.orchestrator.state_preparation.prepare.return_value = PreparationResult(
            ready_to_execute=True,
            preparation_steps=[
                PreparationStep(
                    tool_name="set_time_selection",
                    arguments={"start_time": 10.0, "end_time": 20.0},
                    purpose="Set selection from 10s to 20s"
                )
            ],
            operation_tool="trim_to_selection",
            operation_arguments={},
            error=None,
            needs_clarification=False,
            clarification_message=None
        )

        self.tool_registry.execute_by_name.return_value = {"success": True}

        response = self.orchestrator.process_request("trim to selection")

        # Should have called state preparation
        self.orchestrator.state_preparation.prepare.assert_called()

    def test_process_request_with_approval_required(self):
        """Test processing request that requires approval"""
        self.orchestrator.intent_planner.plan.return_value = (
            [{"tool_name": "delete_selection", "arguments": {}}],
            False,
            None
        )

        self.orchestrator.state_preparation.prepare.return_value = PreparationResult(
            ready_to_execute=True,
            preparation_steps=[
                PreparationStep(
                    tool_name="set_time_selection",
                    arguments={"start_time": 10.0, "end_time": 20.0},
                    purpose="Set selection from 10s to 20s"
                )
            ],
            operation_tool="delete_selection",
            operation_arguments={},
            error=None,
            needs_clarification=False,
            clarification_message=None
        )

        # Mock orchestrator's _execute_tool_calls to return approval request
        self.orchestrator_agent._execute_tool_calls = Mock(return_value={
            "type": "approval_request",
            "approval_id": "test_id"
        })

        response = self.orchestrator.process_request("delete selection")

        # Should delegate to orchestrator agent for approval
        self.assertEqual(response["type"], "approval_request")


class TestConditionalRouting(unittest.TestCase):
    """Test conditional routing"""

    def setUp(self):
        """Set up test fixtures"""
        self.tool_registry = Mock()
        self.orchestrator_agent = Mock(spec=OrchestratorAgent)
        self.orchestrator = PlanningOrchestrator(self.tool_registry, self.orchestrator_agent)

    def test_routing_state_missing(self):
        """Test routing when state is missing"""
        self.orchestrator.state_discovery.discover_state = Mock(return_value={})
        self.orchestrator.intent_planner.plan = Mock(return_value=([], False, None))

        response = self.orchestrator.process_request("test")

        # Should have attempted state discovery
        self.orchestrator.state_discovery.discover_state.assert_called()

    def test_routing_plan_incomplete(self):
        """Test routing when plan is incomplete"""
        self.orchestrator.state_discovery.discover_state = Mock(return_value={"project_open": True})
        self.orchestrator.intent_planner.plan = Mock(return_value=([], False, None))

        response = self.orchestrator.process_request("test")

        # Should return message asking for clarification
        self.assertIn("type", response)
        self.assertIn("content", response)

    def test_routing_needs_clarification(self):
        """Test routing when state preparation needs clarification"""
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
            clarification_message="Please specify a time range"
        ))

        response = self.orchestrator.process_request("trim")

        # Should need clarification
        self.assertEqual(response["type"], "clarification_needed")

    def test_routing_all_ready(self):
        """Test routing when all ready for execution"""
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
        self.tool_registry.execute_by_name.return_value = {"success": True}

        response = self.orchestrator.process_request("play")

        # Should execute
        self.tool_registry.execute_by_name.assert_called()


class TestErrorHandling(unittest.TestCase):
    """Test error handling"""

    def setUp(self):
        """Set up test fixtures"""
        self.tool_registry = Mock()
        self.orchestrator_agent = Mock(spec=OrchestratorAgent)
        self.orchestrator = PlanningOrchestrator(self.tool_registry, self.orchestrator_agent)

    def test_error_handling_state_discovery_fails(self):
        """Test error handling when state discovery fails"""
        self.orchestrator.state_discovery.discover_state = Mock(side_effect=Exception("State discovery error"))

        response = self.orchestrator.process_request("test")

        self.assertEqual(response["type"], "error")
        self.assertIn("error", response["content"].lower())

    def test_error_handling_intent_planning_fails(self):
        """Test error handling when intent planning fails"""
        self.orchestrator.state_discovery.discover_state = Mock(return_value={"project_open": True})
        self.orchestrator.intent_planner.plan = Mock(side_effect=Exception("Planning error"))

        response = self.orchestrator.process_request("test")

        self.assertEqual(response["type"], "error")

    def test_error_handling_state_preparation_fails(self):
        """Test error handling when state preparation fails"""
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
            error="Cannot determine how to prepare state for trim_to_selection",
            needs_clarification=False,
            clarification_message=None
        ))

        response = self.orchestrator.process_request("trim")

        self.assertEqual(response["type"], "error")

    def test_error_handling_execution_fails(self):
        """Test error handling when execution fails"""
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
        self.tool_registry.execute_by_name.return_value = {"success": False, "error": "Execution failed"}

        response = self.orchestrator.process_request("play")

        # Should return response with error indication
        self.assertIn("type", response)
        self.assertIn("content", response)


class TestIntegrationWithOrchestratorAgent(unittest.TestCase):
    """Test integration with OrchestratorAgent"""

    def setUp(self):
        """Set up test fixtures"""
        self.tool_registry = Mock()
        self.orchestrator_agent = Mock(spec=OrchestratorAgent)
        self.orchestrator = PlanningOrchestrator(self.tool_registry, self.orchestrator_agent)

    def test_process_approval_delegates_to_orchestrator(self):
        """Test process_approval delegates to OrchestratorAgent"""
        self.orchestrator_agent.process_approval.return_value = {
            "type": "message",
            "content": "Approved"
        }

        response = self.orchestrator.process_approval("test_id", True, [])

        self.orchestrator_agent.process_approval.assert_called_once()
        self.assertEqual(response["type"], "message")

    def test_approval_flow_integration(self):
        """Test approval flow integration"""
        # Set up for approval-required operation
        self.orchestrator.state_discovery.discover_state = Mock(return_value={"project_open": True})
        self.orchestrator.intent_planner.plan = Mock(return_value=(
            [{"tool_name": "delete_selection", "arguments": {}}],
            False,
            None
        ))
        self.orchestrator.state_preparation.prepare = Mock(return_value=PreparationResult(
            ready_to_execute=True,
            preparation_steps=[],
            operation_tool="delete_selection",
            operation_arguments={},
            error=None,
            needs_clarification=False,
            clarification_message=None
        ))

        # Mock orchestrator's approval request
        self.orchestrator_agent._execute_tool_calls = Mock(return_value={
            "type": "approval_request",
            "approval_id": "test_id",
            "task_plan": [{"tool_name": "delete_selection", "arguments": {}}]
        })

        response = self.orchestrator.process_request("delete selection")

        self.assertEqual(response["type"], "approval_request")


if __name__ == '__main__':
    unittest.main()
