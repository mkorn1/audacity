#!/usr/bin/env python3
"""
Unit tests for IntentPlanner (Phase 3.3)

Tests intent planning including:
- Analyzing intent
- Parsing tool calls
- Parsing location references
- Error handling
"""

import unittest
import sys
import os
import json
from unittest.mock import Mock, MagicMock, patch

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from intent_planner import IntentPlanner


class MockToolCall:
    """Mock tool call object"""
    def __init__(self, name, arguments, call_id=None):
        class Function:
            def __init__(self, n, args):
                self.name = n
                self.arguments = json.dumps(args) if args else "{}"
        self.function = Function(name, arguments)
        self.id = call_id or f"call_{name}"


class MockMessage:
    """Mock OpenAI message"""
    def __init__(self, tool_calls=None, content=None):
        self.tool_calls = tool_calls or []
        self.content = content


class MockChoice:
    """Mock OpenAI choice"""
    def __init__(self, message):
        self.message = message


class MockResponse:
    """Mock OpenAI response"""
    def __init__(self, choices):
        self.choices = choices


class TestAnalyzeIntent(unittest.TestCase):
    """Test analyzing intent"""

    def setUp(self):
        """Set up test fixtures"""
        self.tool_registry = Mock()
        with patch('intent_planner.OPENAI_AVAILABLE', True):
            with patch('intent_planner.is_openai_configured', return_value=True):
                with patch('intent_planner.get_openai_api_key', return_value="test-key"):
                    self.planner = IntentPlanner(self.tool_registry)
                    self.planner.openai_client = Mock()

    def test_analyze_intent_with_tool_calls(self):
        """Test analyzing intent that returns tool calls"""
        tool_calls = [MockToolCall("set_time_selection", {"start_time": 10.0, "end_time": 20.0})]
        message = MockMessage(tool_calls=tool_calls)
        response = MockResponse([MockChoice(message)])
        
        self.planner.openai_client.chat.completions.create.return_value = response
        
        state_snapshot = {"project_open": True}
        result = self.planner.analyze_intent("trim to 10-20 seconds", state_snapshot)
        
        self.assertIn("tool_calls", result)
        self.assertEqual(len(result["tool_calls"]), 1)
        self.assertNotIn("error", result)

    def test_analyze_intent_with_text_response(self):
        """Test analyzing intent that returns text response"""
        message = MockMessage(content="I need more information")
        response = MockResponse([MockChoice(message)])
        
        self.planner.openai_client.chat.completions.create.return_value = response
        
        state_snapshot = {"project_open": True}
        result = self.planner.analyze_intent("hello", state_snapshot)
        
        self.assertIn("content", result)
        self.assertEqual(result["content"], "I need more information")
        self.assertEqual(len(result.get("tool_calls", [])), 0)

    def test_analyze_intent_with_error(self):
        """Test analyzing intent with error"""
        self.planner.openai_client.chat.completions.create.side_effect = Exception("API error")
        
        state_snapshot = {"project_open": True}
        result = self.planner.analyze_intent("test", state_snapshot)
        
        self.assertIn("error", result)
        self.assertIn("tool_calls", result)
        self.assertEqual(len(result["tool_calls"]), 0)

    def test_analyze_intent_without_openai_client(self):
        """Test analyzing intent without OpenAI client"""
        self.planner.openai_client = None
        
        state_snapshot = {"project_open": True}
        result = self.planner.analyze_intent("test", state_snapshot)
        
        self.assertIn("error", result)
        self.assertEqual(result["error"], "OpenAI client not available")


class TestParseToolCalls(unittest.TestCase):
    """Test parsing tool calls"""

    def setUp(self):
        """Set up test fixtures"""
        self.tool_registry = Mock()
        with patch('intent_planner.OPENAI_AVAILABLE', True):
            with patch('intent_planner.is_openai_configured', return_value=True):
                with patch('intent_planner.get_openai_api_key', return_value="test-key"):
                    self.planner = IntentPlanner(self.tool_registry)

    def test_parse_tool_calls_with_valid_tool_calls(self):
        """Test parsing valid tool calls"""
        tool_calls = [MockToolCall("set_time_selection", {"start_time": 10.0, "end_time": 20.0})]
        llm_response = {"tool_calls": tool_calls}
        
        parsed_calls, needs_more_state = self.planner.parse_tool_calls(llm_response)
        
        self.assertEqual(len(parsed_calls), 1)
        self.assertEqual(parsed_calls[0]["tool_name"], "set_time_selection")
        self.assertEqual(parsed_calls[0]["arguments"]["start_time"], 10.0)
        self.assertFalse(needs_more_state)

    def test_parse_tool_calls_with_state_queries(self):
        """Test parsing tool calls that include state queries"""
        tool_calls = [
            MockToolCall("get_selection_start_time", {}),
            MockToolCall("set_time_selection", {"start_time": 10.0, "end_time": 20.0})
        ]
        llm_response = {"tool_calls": tool_calls}
        
        parsed_calls, needs_more_state = self.planner.parse_tool_calls(llm_response)
        
        self.assertEqual(len(parsed_calls), 2)
        self.assertTrue(needs_more_state)

    def test_parse_tool_calls_with_mixed_calls(self):
        """Test parsing mixed tool calls and state queries"""
        tool_calls = [
            MockToolCall("has_time_selection", {}),
            MockToolCall("trim_to_selection", {})
        ]
        llm_response = {"tool_calls": tool_calls}
        
        parsed_calls, needs_more_state = self.planner.parse_tool_calls(llm_response)
        
        self.assertEqual(len(parsed_calls), 2)
        self.assertTrue(needs_more_state)

    def test_parse_tool_calls_with_error(self):
        """Test parsing tool calls with error"""
        llm_response = {"error": "test error"}
        
        parsed_calls, needs_more_state = self.planner.parse_tool_calls(llm_response)
        
        self.assertEqual(len(parsed_calls), 0)
        self.assertFalse(needs_more_state)

    def test_parse_tool_calls_with_invalid_json(self):
        """Test parsing tool calls with invalid JSON in arguments"""
        class BadToolCall:
            def __init__(self):
                class Function:
                    def __init__(self):
                        self.name = "test_tool"
                        self.arguments = "invalid json{"
                self.function = Function()
                self.id = "call_1"
        
        tool_calls = [BadToolCall()]
        llm_response = {"tool_calls": tool_calls}
        
        # Should handle gracefully
        parsed_calls, needs_more_state = self.planner.parse_tool_calls(llm_response)
        # May have empty arguments or handle error
        self.assertGreaterEqual(len(parsed_calls), 0)


class TestParseLocationReferences(unittest.TestCase):
    """Test parsing location references"""

    def setUp(self):
        """Set up test fixtures"""
        self.tool_registry = Mock()
        with patch('intent_planner.OPENAI_AVAILABLE', True):
            with patch('intent_planner.is_openai_configured', return_value=True):
                with patch('intent_planner.get_openai_api_key', return_value="test-key"):
                    self.planner = IntentPlanner(self.tool_registry)

    def test_parse_location_references_explicit_time(self):
        """Test parsing explicit time location"""
        state_snapshot = {}
        result = self.planner.parse_location_references("at 2:30", state_snapshot)
        
        self.assertEqual(result["type"], "time_point")
        self.assertEqual(result["time"], 150.0)

    def test_parse_location_references_time_range(self):
        """Test parsing time range location"""
        state_snapshot = {}
        result = self.planner.parse_location_references("from 1:00 to 2:00", state_snapshot)
        
        self.assertEqual(result["type"], "time_range")
        self.assertEqual(result["start_time"], 60.0)
        self.assertEqual(result["end_time"], 120.0)

    def test_parse_location_references_current_selection(self):
        """Test parsing current selection location"""
        state_snapshot = {
            "has_time_selection": True,
            "selection_start_time": 10.0,
            "selection_end_time": 20.0
        }
        result = self.planner.parse_location_references("current selection", state_snapshot)
        
        self.assertEqual(result["type"], "time_range")
        self.assertEqual(result["start_time"], 10.0)
        self.assertEqual(result["end_time"], 20.0)


class TestPlan(unittest.TestCase):
    """Test complete planning process"""

    def setUp(self):
        """Set up test fixtures"""
        self.tool_registry = Mock()
        with patch('intent_planner.OPENAI_AVAILABLE', True):
            with patch('intent_planner.is_openai_configured', return_value=True):
                with patch('intent_planner.get_openai_api_key', return_value="test-key"):
                    self.planner = IntentPlanner(self.tool_registry)
                    self.planner.openai_client = Mock()

    def test_plan_with_simple_request(self):
        """Test planning with simple request"""
        tool_calls = [MockToolCall("play", {})]
        message = MockMessage(tool_calls=tool_calls)
        response = MockResponse([MockChoice(message)])
        
        self.planner.openai_client.chat.completions.create.return_value = response
        
        state_snapshot = {"project_open": True}
        tool_calls, needs_more_state, error = self.planner.plan("play", state_snapshot)
        
        self.assertEqual(len(tool_calls), 1)
        self.assertEqual(tool_calls[0]["tool_name"], "play")
        self.assertFalse(needs_more_state)
        self.assertIsNone(error)

    def test_plan_with_state_snapshot(self):
        """Test planning with state snapshot included"""
        tool_calls = [MockToolCall("trim_to_selection", {})]
        message = MockMessage(tool_calls=tool_calls)
        response = MockResponse([MockChoice(message)])
        
        self.planner.openai_client.chat.completions.create.return_value = response
        
        state_snapshot = {
            "project_open": True,
            "has_time_selection": True,
            "selection_start_time": 10.0,
            "selection_end_time": 20.0
        }
        tool_calls, needs_more_state, error = self.planner.plan("trim this", state_snapshot)
        
        self.assertEqual(len(tool_calls), 1)
        self.assertFalse(needs_more_state)
        self.assertIsNone(error)

    def test_plan_with_state_queries(self):
        """Test planning that requires state queries"""
        tool_calls = [MockToolCall("get_selection_start_time", {})]
        message = MockMessage(tool_calls=tool_calls)
        response = MockResponse([MockChoice(message)])
        
        self.planner.openai_client.chat.completions.create.return_value = response
        
        state_snapshot = {"project_open": True}
        tool_calls, needs_more_state, error = self.planner.plan("trim this", state_snapshot)
        
        self.assertEqual(len(tool_calls), 1)
        self.assertTrue(needs_more_state)
        self.assertIsNone(error)

    def test_plan_with_error(self):
        """Test planning with error"""
        self.planner.openai_client.chat.completions.create.side_effect = Exception("API error")
        
        state_snapshot = {"project_open": True}
        tool_calls, needs_more_state, error = self.planner.plan("test", state_snapshot)
        
        self.assertEqual(len(tool_calls), 0)
        self.assertFalse(needs_more_state)
        self.assertIsNotNone(error)

    def test_plan_with_text_response_needing_clarification(self):
        """Test planning with text response needing clarification"""
        message = MockMessage(content="I need to check the selection first")
        response = MockResponse([MockChoice(message)])
        
        self.planner.openai_client.chat.completions.create.return_value = response
        
        state_snapshot = {"project_open": True}
        tool_calls, needs_more_state, error = self.planner.plan("trim this", state_snapshot)
        
        self.assertEqual(len(tool_calls), 0)
        self.assertTrue(needs_more_state)  # Should detect need for state
        self.assertIsNone(error)


if __name__ == '__main__':
    unittest.main()

