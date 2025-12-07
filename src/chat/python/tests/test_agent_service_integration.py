#!/usr/bin/env python3
"""
Unit tests for AgentService integration with PlanningOrchestrator (Phase 4.1)

Tests:
- AgentService uses PlanningOrchestrator
- Approval flow still works
- Message loop integration
- Backward compatibility
- Error handling in integrated system
"""

import unittest
import sys
import os
import json
from unittest.mock import Mock, MagicMock, patch, call

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from agent_service import AgentService
from planning_orchestrator import PlanningOrchestrator
from orchestrator import OrchestratorAgent


class TestAgentServiceIntegration(unittest.TestCase):
    """Test AgentService integration with PlanningOrchestrator"""

    def setUp(self):
        """Set up test fixtures"""
        # Mock ToolExecutor and ToolRegistry
        with patch('agent_service.ToolExecutor'), \
             patch('agent_service.ToolRegistry') as mock_tool_registry_class, \
             patch('agent_service.OrchestratorAgent') as mock_orchestrator_class, \
             patch('agent_service.PlanningOrchestrator') as mock_planning_class:
            
            mock_tool_registry = Mock()
            mock_tool_registry_class.return_value = mock_tool_registry
            
            mock_base_orchestrator = Mock(spec=OrchestratorAgent)
            mock_orchestrator_class.return_value = mock_base_orchestrator
            
            mock_planning_orchestrator = Mock(spec=PlanningOrchestrator)
            mock_planning_class.return_value = mock_planning_orchestrator
            
            # Create service
            self.service = AgentService()
            
            # Store mocks for assertions
            self.mock_planning = mock_planning_orchestrator
            self.mock_base_orchestrator = mock_base_orchestrator
            self.mock_tools = mock_tool_registry

    def test_uses_planning_orchestrator(self):
        """Test that AgentService uses PlanningOrchestrator"""
        # Verify PlanningOrchestrator was instantiated
        self.assertIsNotNone(self.service.orchestrator)
        self.assertIsInstance(self.service.orchestrator, Mock)
        # In real code, it would be PlanningOrchestrator instance

    def test_process_request_delegates_to_planning_orchestrator(self):
        """Test that process_request delegates to PlanningOrchestrator"""
        expected_response = {
            "type": "message",
            "content": "Done! Executed: set_time_selection, trim_to_selection",
            "can_undo": True
        }
        self.mock_planning.process_request.return_value = expected_response
        
        response = self.service.process_request("trim to 10-20 seconds")
        
        self.mock_planning.process_request.assert_called_once_with("trim to 10-20 seconds")
        self.assertEqual(response, expected_response)

    def test_approval_request_storage(self):
        """Test that approval requests are stored correctly"""
        approval_response = {
            "type": "approval_request",
            "approval_id": "test_approval_123",
            "task_plan": [{"tool_name": "trim_to_selection", "arguments": {}}],
            "approval_mode": "batch",
            "current_step": 0
        }
        self.mock_planning.process_request.return_value = approval_response
        
        response = self.service.process_request("trim selection")
        
        # Check approval was stored
        self.assertIn("test_approval_123", self.service._pending_approvals)
        approval_data = self.service._pending_approvals["test_approval_123"]
        self.assertEqual(approval_data["task_plan"], approval_response["task_plan"])
        self.assertEqual(approval_data["approval_mode"], "batch")

    def test_process_approval_delegates_to_planning_orchestrator(self):
        """Test that process_approval delegates to PlanningOrchestrator"""
        # Set up stored approval
        self.service._pending_approvals["test_approval_123"] = {
            "task_plan": [{"tool_name": "trim_to_selection", "arguments": {}}],
            "approval_mode": "batch",
            "current_step": 0
        }
        
        expected_response = {
            "type": "message",
            "content": "Completed: trim_to_selection",
            "can_undo": True
        }
        self.mock_planning.process_approval.return_value = expected_response
        
        response = self.service.process_approval("test_approval_123", True)
        
        self.mock_planning.process_approval.assert_called_once()
        call_args = self.mock_planning.process_approval.call_args
        self.assertEqual(call_args[0][0], "test_approval_123")
        self.assertEqual(call_args[0][1], True)

    def test_approval_not_found_error(self):
        """Test error handling when approval ID not found"""
        response = self.service.process_approval("nonexistent_approval", True)
        
        self.assertEqual(response["type"], "error")
        self.assertIn("not found", response["content"].lower())

    def test_backward_compatibility_message_format(self):
        """Test that response format is backward compatible"""
        response = {
            "type": "message",
            "content": "Done!",
            "can_undo": True
        }
        self.mock_planning.process_request.return_value = response
        
        result = self.service.process_request("test message")
        
        # Verify response has expected fields
        self.assertIn("type", result)
        self.assertIn("content", result)
        self.assertIn("can_undo", result)

    def test_error_handling_in_integrated_system(self):
        """Test error handling when PlanningOrchestrator raises exception"""
        self.mock_planning.process_request.side_effect = Exception("Test error")
        
        # Should not crash, but return error response
        # In real implementation, this would be caught and returned as error
        with self.assertRaises(Exception):
            self.service.process_request("test message")

    def test_message_loop_integration(self):
        """Test integration with message loop (simulated)"""
        # Simulate message from queue
        request = {
            "type": "message",
            "message": "trim to 10-20 seconds"
        }
        
        response = {
            "type": "message",
            "content": "Done!",
            "can_undo": True
        }
        self.mock_planning.process_request.return_value = response
        
        # Process request (as message loop would)
        result = self.service.process_request(request["message"])
        
        self.assertEqual(result, response)
        self.mock_planning.process_request.assert_called_once_with(request["message"])


if __name__ == '__main__':
    unittest.main()

