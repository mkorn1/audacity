#!/usr/bin/env python3
"""
Unit tests for PlanningState (Phase 3.1)

Tests the planning state management including:
- State initialization
- State transitions
- State validation
- State dictionary updates
- State persistence across phases
"""

import unittest
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from planning_state import PlanningState, PlanningPhase


class TestPlanningStateInitialization(unittest.TestCase):
    """Test PlanningState initialization"""

    def test_state_initialization(self):
        """Test state initialization with user message"""
        state = PlanningState("test message")
        self.assertEqual(state.user_message, "test message")
        self.assertEqual(state.discovered_state, {})
        self.assertEqual(state.execution_plan, [])
        self.assertFalse(state.prerequisites_resolved)
        self.assertEqual(state.execution_results, [])
        self.assertEqual(state.current_phase, PlanningPhase.INITIAL)
        self.assertIsNone(state.error_message)

    def test_state_initialization_with_empty_message(self):
        """Test state initialization with empty message"""
        state = PlanningState("")
        self.assertEqual(state.user_message, "")
        self.assertEqual(state.current_phase, PlanningPhase.INITIAL)


class TestPlanningStateTransitions(unittest.TestCase):
    """Test PlanningState transitions"""

    def test_valid_transition_initial_to_state_discovery(self):
        """Test valid transition from INITIAL to STATE_DISCOVERY"""
        state = PlanningState("test")
        result = state.transition_to(PlanningPhase.STATE_DISCOVERY)
        self.assertTrue(result)
        self.assertEqual(state.current_phase, PlanningPhase.STATE_DISCOVERY)

    def test_valid_transition_state_discovery_to_planning(self):
        """Test valid transition from STATE_DISCOVERY to PLANNING"""
        state = PlanningState("test")
        state.transition_to(PlanningPhase.STATE_DISCOVERY)
        result = state.transition_to(PlanningPhase.PLANNING)
        self.assertTrue(result)
        self.assertEqual(state.current_phase, PlanningPhase.PLANNING)

    def test_valid_transition_planning_to_prerequisite_resolution(self):
        """Test valid transition from PLANNING to PREREQUISITE_RESOLUTION"""
        state = PlanningState("test")
        state.transition_to(PlanningPhase.STATE_DISCOVERY)
        state.transition_to(PlanningPhase.PLANNING)
        result = state.transition_to(PlanningPhase.PREREQUISITE_RESOLUTION)
        self.assertTrue(result)
        self.assertEqual(state.current_phase, PlanningPhase.PREREQUISITE_RESOLUTION)

    def test_valid_transition_prerequisite_resolution_to_execution(self):
        """Test valid transition from PREREQUISITE_RESOLUTION to EXECUTION"""
        state = PlanningState("test")
        state.transition_to(PlanningPhase.STATE_DISCOVERY)
        state.transition_to(PlanningPhase.PLANNING)
        state.transition_to(PlanningPhase.PREREQUISITE_RESOLUTION)
        result = state.transition_to(PlanningPhase.EXECUTION)
        self.assertTrue(result)
        self.assertEqual(state.current_phase, PlanningPhase.EXECUTION)

    def test_valid_transition_execution_to_complete(self):
        """Test valid transition from EXECUTION to COMPLETE"""
        state = PlanningState("test")
        state.transition_to(PlanningPhase.STATE_DISCOVERY)
        state.transition_to(PlanningPhase.PLANNING)
        state.transition_to(PlanningPhase.PREREQUISITE_RESOLUTION)
        state.transition_to(PlanningPhase.EXECUTION)
        result = state.transition_to(PlanningPhase.COMPLETE)
        self.assertTrue(result)
        self.assertEqual(state.current_phase, PlanningPhase.COMPLETE)

    def test_invalid_transition_initial_to_execution(self):
        """Test invalid transition from INITIAL directly to EXECUTION"""
        state = PlanningState("test")
        result = state.transition_to(PlanningPhase.EXECUTION)
        self.assertFalse(result)
        self.assertEqual(state.current_phase, PlanningPhase.INITIAL)

    def test_invalid_transition_complete_to_planning(self):
        """Test invalid transition from COMPLETE to PLANNING"""
        state = PlanningState("test")
        state.transition_to(PlanningPhase.STATE_DISCOVERY)
        state.transition_to(PlanningPhase.PLANNING)
        state.transition_to(PlanningPhase.PREREQUISITE_RESOLUTION)
        state.transition_to(PlanningPhase.EXECUTION)
        state.transition_to(PlanningPhase.COMPLETE)
        result = state.transition_to(PlanningPhase.PLANNING)
        self.assertFalse(result)
        self.assertEqual(state.current_phase, PlanningPhase.COMPLETE)

    def test_valid_transition_to_error(self):
        """Test valid transition to ERROR from any phase"""
        state = PlanningState("test")
        result = state.transition_to(PlanningPhase.ERROR)
        self.assertTrue(result)
        self.assertEqual(state.current_phase, PlanningPhase.ERROR)

    def test_valid_transition_error_to_initial(self):
        """Test valid transition from ERROR to INITIAL (restart)"""
        state = PlanningState("test")
        state.transition_to(PlanningPhase.ERROR)
        result = state.transition_to(PlanningPhase.INITIAL)
        self.assertTrue(result)
        self.assertEqual(state.current_phase, PlanningPhase.INITIAL)


class TestPlanningStateValidation(unittest.TestCase):
    """Test PlanningState validation"""

    def test_validate_initial_state(self):
        """Test validation of INITIAL state"""
        state = PlanningState("test")
        is_valid, error = state.validate()
        self.assertTrue(is_valid)
        self.assertIsNone(error)

    def test_validate_state_discovery(self):
        """Test validation of STATE_DISCOVERY phase"""
        state = PlanningState("test")
        state.transition_to(PlanningPhase.STATE_DISCOVERY)
        is_valid, error = state.validate()
        self.assertTrue(is_valid)
        self.assertIsNone(error)

    def test_validate_planning(self):
        """Test validation of PLANNING phase"""
        state = PlanningState("test")
        state.transition_to(PlanningPhase.STATE_DISCOVERY)
        state.transition_to(PlanningPhase.PLANNING)
        is_valid, error = state.validate()
        self.assertTrue(is_valid)
        self.assertIsNone(error)

    def test_validate_prerequisite_resolution_without_plan(self):
        """Test validation of PREREQUISITE_RESOLUTION without execution plan"""
        state = PlanningState("test")
        state.transition_to(PlanningPhase.STATE_DISCOVERY)
        state.transition_to(PlanningPhase.PLANNING)
        state.transition_to(PlanningPhase.PREREQUISITE_RESOLUTION)
        is_valid, error = state.validate()
        # Should be invalid without execution plan
        self.assertFalse(is_valid)
        self.assertIsNotNone(error)

    def test_validate_prerequisite_resolution_with_plan(self):
        """Test validation of PREREQUISITE_RESOLUTION with execution plan"""
        state = PlanningState("test")
        state.transition_to(PlanningPhase.STATE_DISCOVERY)
        state.transition_to(PlanningPhase.PLANNING)
        state.set_execution_plan([{"tool_name": "test_tool", "arguments": {}}])
        state.transition_to(PlanningPhase.PREREQUISITE_RESOLUTION)
        is_valid, error = state.validate()
        self.assertTrue(is_valid)
        self.assertIsNone(error)

    def test_validate_execution_without_plan(self):
        """Test validation of EXECUTION phase without execution plan"""
        state = PlanningState("test")
        state.transition_to(PlanningPhase.STATE_DISCOVERY)
        state.transition_to(PlanningPhase.PLANNING)
        state.transition_to(PlanningPhase.PREREQUISITE_RESOLUTION)
        state.transition_to(PlanningPhase.EXECUTION)
        is_valid, error = state.validate()
        # Should be invalid without execution plan
        self.assertFalse(is_valid)
        self.assertIsNotNone(error)

    def test_validate_execution_with_plan(self):
        """Test validation of EXECUTION phase with execution plan"""
        state = PlanningState("test")
        state.transition_to(PlanningPhase.STATE_DISCOVERY)
        state.transition_to(PlanningPhase.PLANNING)
        state.set_execution_plan([{"tool_name": "test_tool", "arguments": {}}])
        state.transition_to(PlanningPhase.PREREQUISITE_RESOLUTION)
        state.transition_to(PlanningPhase.EXECUTION)
        is_valid, error = state.validate()
        self.assertTrue(is_valid)
        self.assertIsNone(error)

    def test_validate_error_state(self):
        """Test validation of ERROR state"""
        state = PlanningState("test")
        state.set_error("test error")
        is_valid, error = state.validate()
        self.assertTrue(is_valid)  # Error state is valid if it has error message
        self.assertIsNone(error)  # validate() doesn't return the error message

    def test_validate_error_state_without_message(self):
        """Test validation of ERROR state without error message"""
        state = PlanningState("test")
        state.transition_to(PlanningPhase.ERROR)
        is_valid, error = state.validate()
        # Should be invalid without error message
        self.assertFalse(is_valid)
        self.assertIsNotNone(error)


class TestPlanningStateDictionaryUpdates(unittest.TestCase):
    """Test PlanningState dictionary updates"""

    def test_set_state_snapshot(self):
        """Test setting state snapshot"""
        state = PlanningState("test")
        snapshot = {"selection_start_time": 10.0, "selection_end_time": 20.0}
        state.set_state_snapshot(snapshot)
        self.assertEqual(state.discovered_state, snapshot)

    def test_get_state_value(self):
        """Test getting state value"""
        state = PlanningState("test")
        state.set_state_snapshot({"key": "value"})
        self.assertEqual(state.get_state_value("key"), "value")
        self.assertIsNone(state.get_state_value("missing"))
        self.assertEqual(state.get_state_value("missing", "default"), "default")

    def test_set_execution_plan(self):
        """Test setting execution plan"""
        state = PlanningState("test")
        plan = [{"tool_name": "tool1", "arguments": {}}, {"tool_name": "tool2", "arguments": {}}]
        state.set_execution_plan(plan)
        self.assertEqual(state.execution_plan, plan)

    def test_add_execution_result(self):
        """Test adding execution result"""
        state = PlanningState("test")
        result1 = {"tool_name": "tool1", "result": {"success": True}}
        result2 = {"tool_name": "tool2", "result": {"success": False}}
        state.add_execution_result(result1)
        state.add_execution_result(result2)
        self.assertEqual(len(state.execution_results), 2)
        self.assertEqual(state.execution_results[0], result1)
        self.assertEqual(state.execution_results[1], result2)

    def test_mark_prerequisites_resolved(self):
        """Test marking prerequisites as resolved"""
        state = PlanningState("test")
        self.assertFalse(state.prerequisites_resolved)
        state.mark_prerequisites_resolved()
        self.assertTrue(state.prerequisites_resolved)

    def test_set_error(self):
        """Test setting error state"""
        state = PlanningState("test")
        state.set_error("test error")
        self.assertEqual(state.error_message, "test error")
        self.assertEqual(state.current_phase, PlanningPhase.ERROR)


class TestPlanningStatePersistence(unittest.TestCase):
    """Test PlanningState persistence across phases"""

    def test_state_persistence_across_phases(self):
        """Test state persists across phase transitions"""
        state = PlanningState("test")
        snapshot = {"key": "value"}
        state.set_state_snapshot(snapshot)
        
        state.transition_to(PlanningPhase.STATE_DISCOVERY)
        self.assertEqual(state.discovered_state, snapshot)
        
        state.transition_to(PlanningPhase.PLANNING)
        self.assertEqual(state.discovered_state, snapshot)
        
        plan = [{"tool_name": "tool1", "arguments": {}}]
        state.set_execution_plan(plan)
        
        state.transition_to(PlanningPhase.PREREQUISITE_RESOLUTION)
        self.assertEqual(state.discovered_state, snapshot)
        self.assertEqual(state.execution_plan, plan)

    def test_is_ready_for_execution(self):
        """Test is_ready_for_execution check"""
        state = PlanningState("test")
        self.assertFalse(state.is_ready_for_execution())
        
        state.transition_to(PlanningPhase.STATE_DISCOVERY)
        state.transition_to(PlanningPhase.PLANNING)
        state.set_execution_plan([{"tool_name": "test", "arguments": {}}])
        state.transition_to(PlanningPhase.PREREQUISITE_RESOLUTION)
        state.mark_prerequisites_resolved()
        
        self.assertTrue(state.is_ready_for_execution())

    def test_to_dict(self):
        """Test converting state to dictionary"""
        state = PlanningState("test message")
        state.set_state_snapshot({"key": "value"})
        state.set_execution_plan([{"tool_name": "tool1", "arguments": {}}])
        state.mark_prerequisites_resolved()
        # Valid transition path: INITIAL -> STATE_DISCOVERY -> PLANNING
        state.transition_to(PlanningPhase.STATE_DISCOVERY)
        state.transition_to(PlanningPhase.PLANNING)

        state_dict = state.to_dict()
        self.assertEqual(state_dict["user_message"], "test message")
        self.assertEqual(state_dict["discovered_state"], {"key": "value"})
        self.assertEqual(state_dict["execution_plan"], [{"tool_name": "tool1", "arguments": {}}])
        self.assertTrue(state_dict["prerequisites_resolved"])
        self.assertEqual(state_dict["current_phase"], "planning")
        self.assertIsNone(state_dict["error_message"])


if __name__ == '__main__':
    unittest.main()

