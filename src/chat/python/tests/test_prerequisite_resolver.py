#!/usr/bin/env python3
"""
Unit tests for PrerequisiteResolver (Phase 3.5)

Tests prerequisite resolution including:
- Checking prerequisites
- Resolving missing prerequisites
- Ordering by dependencies
- Edge cases
"""

import unittest
import sys
import os
from unittest.mock import Mock

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from prerequisite_resolver import PrerequisiteResolver
from tool_schemas import TOOL_PREREQUISITES


class TestCheckPrerequisites(unittest.TestCase):
    """Test checking prerequisites"""

    def setUp(self):
        """Set up test fixtures"""
        self.tool_registry = Mock()
        self.resolver = PrerequisiteResolver(self.tool_registry)

    def test_check_prerequisites_all_met(self):
        """Test checking prerequisites when all are met"""
        current_state = {
            "project_open": True,
            "has_time_selection": True,
            "selected_clips": ["clip1"],
            "selected_tracks": ["track1"],
            "cursor_position": 10.0
        }
        
        all_met, missing = self.resolver.check_prerequisites("trim_to_selection", current_state)
        self.assertTrue(all_met)
        self.assertEqual(len(missing), 0)

    def test_check_prerequisites_missing_required(self):
        """Test checking prerequisites when required prerequisite is missing"""
        current_state = {
            "project_open": True,
            "has_time_selection": False  # Missing required
        }
        
        all_met, missing = self.resolver.check_prerequisites("trim_to_selection", current_state)
        self.assertFalse(all_met)
        self.assertIn("time_selection", missing)

    def test_check_prerequisites_missing_project_open(self):
        """Test checking prerequisites when project is not open"""
        current_state = {
            "project_open": False
        }
        
        all_met, missing = self.resolver.check_prerequisites("trim_to_selection", current_state)
        self.assertFalse(all_met)
        self.assertIn("project_open", missing)

    def test_check_prerequisites_optional_prerequisite(self):
        """Test checking prerequisites with optional prerequisite"""
        current_state = {
            "project_open": True,
            "has_time_selection": False  # Optional, so should pass
        }
        
        all_met, missing = self.resolver.check_prerequisites("clear_selection", current_state)
        # clear_selection has optional time_selection, so should pass
        self.assertTrue(all_met)

    def test_check_prerequisites_tool_not_in_prerequisites(self):
        """Test checking prerequisites for tool not in TOOL_PREREQUISITES"""
        current_state = {}
        all_met, missing = self.resolver.check_prerequisites("unknown_tool", current_state)
        # Should pass (no prerequisites defined)
        self.assertTrue(all_met)
        self.assertEqual(len(missing), 0)


class TestResolveMissingPrerequisites(unittest.TestCase):
    """Test resolving missing prerequisites"""

    def setUp(self):
        """Set up test fixtures"""
        self.tool_registry = Mock()
        self.resolver = PrerequisiteResolver(self.tool_registry)

    def test_resolve_missing_prerequisites_adds_set_time_selection(self):
        """Test resolving missing time_selection prerequisite"""
        execution_plan = [
            {"tool_name": "trim_to_selection", "arguments": {}}
        ]
        current_state = {
            "project_open": True,
            "has_time_selection": False,
            "selection_start_time": 10.0,
            "selection_end_time": 20.0
        }
        
        resolved_plan, errors = self.resolver.resolve_missing_prerequisites(
            execution_plan, current_state
        )
        
        self.assertEqual(len(errors), 0)
        self.assertEqual(len(resolved_plan), 2)  # Should add set_time_selection
        self.assertEqual(resolved_plan[0]["tool_name"], "set_time_selection")
        self.assertEqual(resolved_plan[1]["tool_name"], "trim_to_selection")

    def test_resolve_missing_prerequisites_adds_select_all(self):
        """Test resolving missing selected_clips prerequisite"""
        execution_plan = [
            {"tool_name": "join", "arguments": {}}
        ]
        current_state = {
            "project_open": True,
            "selected_clips": []  # Missing required
        }
        
        resolved_plan, errors = self.resolver.resolve_missing_prerequisites(
            execution_plan, current_state
        )
        
        self.assertEqual(len(errors), 0)
        self.assertEqual(len(resolved_plan), 2)  # Should add select_all
        self.assertEqual(resolved_plan[0]["tool_name"], "select_all")
        self.assertEqual(resolved_plan[1]["tool_name"], "join")

    def test_resolve_missing_prerequisites_no_duplicates(self):
        """Test resolving missing prerequisites doesn't duplicate"""
        execution_plan = [
            {"tool_name": "trim_to_selection", "arguments": {}},
            {"tool_name": "cut", "arguments": {}}  # Also needs time_selection
        ]
        current_state = {
            "project_open": True,
            "has_time_selection": False,
            "selection_start_time": 10.0,
            "selection_end_time": 20.0
        }
        
        resolved_plan, errors = self.resolver.resolve_missing_prerequisites(
            execution_plan, current_state
        )
        
        self.assertEqual(len(errors), 0)
        # Should only add set_time_selection once
        set_time_selection_count = sum(
            1 for tc in resolved_plan if tc["tool_name"] == "set_time_selection"
        )
        self.assertEqual(set_time_selection_count, 1)

    def test_resolve_missing_prerequisites_cannot_resolve(self):
        """Test resolving missing prerequisites when can't resolve"""
        execution_plan = [
            {"tool_name": "trim_to_selection", "arguments": {}}
        ]
        current_state = {
            "project_open": True,
            "has_time_selection": False,
            # No selection_start_time or selection_end_time
        }
        
        resolved_plan, errors = self.resolver.resolve_missing_prerequisites(
            execution_plan, current_state
        )
        
        # Should have error because can't determine selection times
        self.assertGreater(len(errors), 0)
        self.assertIn("time_selection", errors[0])

    def test_resolve_missing_prerequisites_uses_state_for_arguments(self):
        """Test resolving missing prerequisites uses state to determine arguments"""
        execution_plan = [
            {"tool_name": "trim_to_selection", "arguments": {}}
        ]
        current_state = {
            "project_open": True,
            "has_time_selection": False,
            "selection_start_time": 15.0,
            "selection_end_time": 25.0
        }
        
        resolved_plan, errors = self.resolver.resolve_missing_prerequisites(
            execution_plan, current_state
        )
        
        self.assertEqual(len(errors), 0)
        self.assertEqual(resolved_plan[0]["tool_name"], "set_time_selection")
        self.assertEqual(resolved_plan[0]["arguments"]["start_time"], 15.0)
        self.assertEqual(resolved_plan[0]["arguments"]["end_time"], 25.0)


class TestOrderByDependencies(unittest.TestCase):
    """Test ordering by dependencies"""

    def setUp(self):
        """Set up test fixtures"""
        self.tool_registry = Mock()
        self.resolver = PrerequisiteResolver(self.tool_registry)

    def test_order_by_dependencies_state_setters_first(self):
        """Test ordering puts state setters first"""
        execution_plan = [
            {"tool_name": "trim_to_selection", "arguments": {}},
            {"tool_name": "set_time_selection", "arguments": {"start_time": 10.0, "end_time": 20.0}}
        ]
        
        ordered_plan, errors = self.resolver.order_by_dependencies(execution_plan)
        
        self.assertEqual(len(errors), 0)
        # set_time_selection should come before trim_to_selection
        self.assertEqual(ordered_plan[0]["tool_name"], "set_time_selection")
        self.assertEqual(ordered_plan[1]["tool_name"], "trim_to_selection")

    def test_order_by_dependencies_multiple_state_setters(self):
        """Test ordering with multiple state setters"""
        execution_plan = [
            {"tool_name": "apply_normalize", "arguments": {}},
            {"tool_name": "set_time_selection", "arguments": {"start_time": 10.0, "end_time": 20.0}},
            {"tool_name": "select_all", "arguments": {}}
        ]
        
        ordered_plan, errors = self.resolver.order_by_dependencies(execution_plan)
        
        self.assertEqual(len(errors), 0)
        # State setters should come first
        first_tool = ordered_plan[0]["tool_name"]
        self.assertIn(first_tool, ["set_time_selection", "select_all"])

    def test_order_by_dependencies_handles_multiple_dependencies(self):
        """Test ordering handles multiple dependencies"""
        execution_plan = [
            {"tool_name": "apply_normalize", "arguments": {}},
            {"tool_name": "set_time_selection", "arguments": {"start_time": 10.0, "end_time": 20.0}},
            {"tool_name": "select_all", "arguments": {}}
        ]
        
        ordered_plan, errors = self.resolver.order_by_dependencies(execution_plan)
        
        self.assertEqual(len(errors), 0)
        # Should have all tools
        self.assertEqual(len(ordered_plan), 3)


class TestCompleteResolution(unittest.TestCase):
    """Test complete prerequisite resolution process"""

    def setUp(self):
        """Set up test fixtures"""
        self.tool_registry = Mock()
        self.resolver = PrerequisiteResolver(self.tool_registry)

    def test_resolve_complete_flow(self):
        """Test complete resolution flow"""
        execution_plan = [
            {"tool_name": "trim_to_selection", "arguments": {}}
        ]
        current_state = {
            "project_open": True,
            "has_time_selection": False,
            "selection_start_time": 10.0,
            "selection_end_time": 20.0
        }
        
        resolved_plan, errors = self.resolver.resolve(execution_plan, current_state)
        
        self.assertEqual(len(errors), 0)
        # Should have set_time_selection before trim_to_selection
        self.assertEqual(resolved_plan[0]["tool_name"], "set_time_selection")
        self.assertEqual(resolved_plan[1]["tool_name"], "trim_to_selection")

    def test_resolve_with_no_prerequisites_needed(self):
        """Test resolve when no prerequisites needed"""
        execution_plan = [
            {"tool_name": "play", "arguments": {}}
        ]
        current_state = {
            "project_open": True
        }
        
        resolved_plan, errors = self.resolver.resolve(execution_plan, current_state)
        
        self.assertEqual(len(errors), 0)
        self.assertEqual(len(resolved_plan), 1)
        self.assertEqual(resolved_plan[0]["tool_name"], "play")


if __name__ == '__main__':
    unittest.main()

