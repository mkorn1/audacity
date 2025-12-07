#!/usr/bin/env python3
"""
Unit tests for state query tools (Phase 1)

Tests the state query infrastructure including:
- StateQueryTools class
- ToolRegistry integration
- Tool schemas
- Mock C++ bridge communication
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import sys
import os
import json
import threading
import queue

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from tools import ToolExecutor, StateQueryTools, ToolRegistry
from tool_schemas import TOOL_DEFINITIONS, FUNCTION_CALLING_SYSTEM_PROMPT


class MockStdout:
    """Mock stdout that captures written data"""
    def __init__(self):
        self.written_data = []
        self.flush_called = False

    def write(self, data):
        self.written_data.append(data)

    def flush(self):
        self.flush_called = True


class MockStdin:
    """Mock stdin that can simulate responses"""
    def __init__(self):
        self.responses = queue.Queue()
        self.closed = False

    def add_response(self, response_dict):
        """Add a response to be read"""
        self.responses.put(json.dumps(response_dict) + "\n")

    def __iter__(self):
        return self

    def __next__(self):
        if self.closed:
            raise StopIteration
        try:
            return self.responses.get(timeout=0.1)
        except queue.Empty:
            raise StopIteration


class TestStateQueryTools(unittest.TestCase):
    """Test StateQueryTools class"""

    def setUp(self):
        """Set up test fixtures"""
        self.mock_stdout = MockStdout()
        self.executor = ToolExecutor(stdout=self.mock_stdout)
        self.state_tools = StateQueryTools(self.executor)

    def test_get_selection_start_time_with_selection(self):
        """Test get_selection_start_time with valid selection"""
        # Mock the executor's execute_state_query to return a successful result
        with patch.object(self.executor, 'execute_state_query') as mock_query:
            mock_query.return_value = {"success": True, "value": 5.5}
            result = self.state_tools.get_selection_start_time()
            self.assertEqual(result, 5.5)
            mock_query.assert_called_once_with("get_selection_start_time")

    def test_get_selection_start_time_no_selection(self):
        """Test get_selection_start_time with no selection"""
        with patch.object(self.executor, 'execute_state_query') as mock_query:
            mock_query.return_value = {"success": True, "value": 0.0}
            result = self.state_tools.get_selection_start_time()
            self.assertEqual(result, 0.0)

    def test_get_selection_start_time_failure(self):
        """Test get_selection_start_time when query fails"""
        with patch.object(self.executor, 'execute_state_query') as mock_query:
            mock_query.return_value = {"success": False, "error": "State reader not available"}
            result = self.state_tools.get_selection_start_time()
            self.assertIsNone(result)

    def test_get_selection_end_time_with_selection(self):
        """Test get_selection_end_time with valid selection"""
        with patch.object(self.executor, 'execute_state_query') as mock_query:
            mock_query.return_value = {"success": True, "value": 10.5}
            result = self.state_tools.get_selection_end_time()
            self.assertEqual(result, 10.5)
            mock_query.assert_called_once_with("get_selection_end_time")

    def test_get_selection_end_time_no_selection(self):
        """Test get_selection_end_time with no selection"""
        with patch.object(self.executor, 'execute_state_query') as mock_query:
            mock_query.return_value = {"success": True, "value": 0.0}
            result = self.state_tools.get_selection_end_time()
            self.assertEqual(result, 0.0)

    def test_has_time_selection_true(self):
        """Test has_time_selection returns True when selection exists"""
        with patch.object(self.executor, 'execute_state_query') as mock_query:
            mock_query.return_value = {"success": True, "value": True}
            result = self.state_tools.has_time_selection()
            self.assertTrue(result)
            mock_query.assert_called_once_with("has_time_selection")

    def test_has_time_selection_false(self):
        """Test has_time_selection returns False when no selection"""
        with patch.object(self.executor, 'execute_state_query') as mock_query:
            mock_query.return_value = {"success": True, "value": False}
            result = self.state_tools.has_time_selection()
            self.assertFalse(result)

    def test_get_selected_tracks_with_selection(self):
        """Test get_selected_tracks with selected tracks"""
        with patch.object(self.executor, 'execute_state_query') as mock_query:
            mock_query.return_value = {
                "success": True,
                "value": ["track_1", "track_2"]
            }
            result = self.state_tools.get_selected_tracks()
            self.assertEqual(result, ["track_1", "track_2"])
            mock_query.assert_called_once_with("get_selected_tracks")

    def test_get_selected_tracks_no_selection(self):
        """Test get_selected_tracks with no tracks selected"""
        with patch.object(self.executor, 'execute_state_query') as mock_query:
            mock_query.return_value = {"success": True, "value": []}
            result = self.state_tools.get_selected_tracks()
            self.assertEqual(result, [])

    def test_get_selected_clips_with_selection(self):
        """Test get_selected_clips with selected clips"""
        with patch.object(self.executor, 'execute_state_query') as mock_query:
            mock_query.return_value = {
                "success": True,
                "value": [
                    {"track_id": "track_1", "clip_id": "clip_1"},
                    {"track_id": "track_1", "clip_id": "clip_2"}
                ]
            }
            result = self.state_tools.get_selected_clips()
            self.assertEqual(len(result), 2)
            self.assertEqual(result[0]["track_id"], "track_1")
            mock_query.assert_called_once_with("get_selected_clips")

    def test_get_selected_clips_no_selection(self):
        """Test get_selected_clips with no clips selected"""
        with patch.object(self.executor, 'execute_state_query') as mock_query:
            mock_query.return_value = {"success": True, "value": []}
            result = self.state_tools.get_selected_clips()
            self.assertEqual(result, [])

    def test_get_cursor_position(self):
        """Test get_cursor_position returns valid time"""
        with patch.object(self.executor, 'execute_state_query') as mock_query:
            mock_query.return_value = {"success": True, "value": 15.3}
            result = self.state_tools.get_cursor_position()
            self.assertEqual(result, 15.3)
            mock_query.assert_called_once_with("get_cursor_position")

    def test_get_cursor_position_unavailable(self):
        """Test get_cursor_position when playback state not available"""
        with patch.object(self.executor, 'execute_state_query') as mock_query:
            mock_query.return_value = {
                "success": False,
                "error": "Playback state not available"
            }
            result = self.state_tools.get_cursor_position()
            self.assertIsNone(result)

    def test_get_total_project_time(self):
        """Test get_total_project_time returns project duration"""
        with patch.object(self.executor, 'execute_state_query') as mock_query:
            mock_query.return_value = {"success": True, "value": 120.5}
            result = self.state_tools.get_total_project_time()
            self.assertEqual(result, 120.5)
            mock_query.assert_called_once_with("get_total_project_time")

    def test_get_track_list(self):
        """Test get_track_list returns list of tracks"""
        with patch.object(self.executor, 'execute_state_query') as mock_query:
            mock_query.return_value = {
                "success": True,
                "value": [
                    {"track_id": "track_1", "name": "Track 1", "type": "audio"},
                    {"track_id": "track_2", "name": "Track 2", "type": "audio"}
                ]
            }
            result = self.state_tools.get_track_list()
            self.assertEqual(len(result), 2)
            self.assertEqual(result[0]["track_id"], "track_1")
            mock_query.assert_called_once_with("get_track_list")

    def test_get_clips_on_track_valid(self):
        """Test get_clips_on_track with valid track"""
        with patch.object(self.executor, 'execute_state_query') as mock_query:
            mock_query.return_value = {
                "success": True,
                "value": [
                    {"track_id": "track_1", "clip_id": "clip_1"},
                    {"track_id": "track_1", "clip_id": "clip_2"}
                ]
            }
            result = self.state_tools.get_clips_on_track("track_1")
            self.assertEqual(len(result), 2)
            mock_query.assert_called_once_with("get_clips_on_track", {"track_id": "track_1"})

    def test_get_clips_on_track_invalid(self):
        """Test get_clips_on_track with invalid track"""
        with patch.object(self.executor, 'execute_state_query') as mock_query:
            mock_query.return_value = {"success": True, "value": []}
            result = self.state_tools.get_clips_on_track("invalid_track")
            self.assertEqual(result, [])

    def test_get_all_labels(self):
        """Test get_all_labels returns label data"""
        with patch.object(self.executor, 'execute_state_query') as mock_query:
            mock_query.return_value = {"success": True, "value": []}
            result = self.state_tools.get_all_labels()
            self.assertEqual(result, [])
            mock_query.assert_called_once_with("get_all_labels")

    def test_action_enabled_true(self):
        """Test action_enabled with enabled action"""
        with patch.object(self.executor, 'execute_state_query') as mock_query:
            mock_query.return_value = {"success": True, "value": True}
            result = self.state_tools.action_enabled("action://trackedit/undo")
            self.assertTrue(result)
            mock_query.assert_called_once_with(
                "action_enabled",
                {"action_code": "action://trackedit/undo"}
            )

    def test_action_enabled_false(self):
        """Test action_enabled with disabled action"""
        with patch.object(self.executor, 'execute_state_query') as mock_query:
            mock_query.return_value = {"success": True, "value": False}
            result = self.state_tools.action_enabled("action://trackedit/redo")
            self.assertFalse(result)


class TestToolRegistryIntegration(unittest.TestCase):
    """Test ToolRegistry integration with state query tools"""

    def setUp(self):
        """Set up test fixtures"""
        self.mock_stdout = MockStdout()
        self.executor = ToolExecutor(stdout=self.mock_stdout)
        self.registry = ToolRegistry(self.executor)

    def test_state_query_tools_registered(self):
        """Test state query tools are registered in _tool_map"""
        state_query_tools = [
            "get_selection_start_time",
            "get_selection_end_time",
            "has_time_selection",
            "get_selected_tracks",
            "get_selected_clips",
            "get_cursor_position",
            "get_total_project_time",
            "get_track_list",
            "get_clips_on_track",
            "get_all_labels",
            "action_enabled",
        ]
        for tool_name in state_query_tools:
            self.assertIn(tool_name, self.registry._tool_map, f"{tool_name} not in tool map")

    def test_execute_by_name_state_query(self):
        """Test execute_by_name works for state queries"""
        with patch.object(self.registry.state, 'get_selection_start_time') as mock_method:
            mock_method.return_value = 5.5
            result = self.registry.execute_by_name("get_selection_start_time", {})
            self.assertTrue(result.get("success"))
            self.assertEqual(result.get("value"), 5.5)

    def test_execute_by_name_state_query_with_params(self):
        """Test execute_by_name with state query that requires parameters"""
        with patch.object(self.registry.state, 'get_clips_on_track') as mock_method:
            mock_method.return_value = []
            result = self.registry.execute_by_name("get_clips_on_track", {"track_id": "track_1"})
            self.assertTrue(result.get("success"))
            mock_method.assert_called_once_with("track_1")

    def test_execute_by_name_unknown_tool(self):
        """Test error handling for unknown state query tools"""
        result = self.registry.execute_by_name("unknown_state_query", {})
        self.assertFalse(result.get("success"))
        self.assertIn("Unknown tool", result.get("error"))


class TestToolSchemas(unittest.TestCase):
    """Test tool schemas for state query tools"""

    def test_all_state_query_tools_in_definitions(self):
        """Test all state query tools are in TOOL_DEFINITIONS"""
        state_query_tools = [
            "get_selection_start_time",
            "get_selection_end_time",
            "has_time_selection",
            "get_selected_tracks",
            "get_selected_clips",
            "get_cursor_position",
            "get_total_project_time",
            "get_track_list",
            "get_clips_on_track",
            "get_all_labels",
            "action_enabled",
        ]
        tool_names = [tool["function"]["name"] for tool in TOOL_DEFINITIONS]
        for tool_name in state_query_tools:
            self.assertIn(tool_name, tool_names, f"{tool_name} not in TOOL_DEFINITIONS")

    def test_parameter_validation(self):
        """Test parameter validation for state query tools"""
        # Tools that require parameters
        get_clips_on_track = next(
            t for t in TOOL_DEFINITIONS if t["function"]["name"] == "get_clips_on_track"
        )
        self.assertIn("track_id", get_clips_on_track["function"]["parameters"]["required"])
        self.assertEqual(
            get_clips_on_track["function"]["parameters"]["properties"]["track_id"]["type"],
            "string"
        )

        action_enabled = next(
            t for t in TOOL_DEFINITIONS if t["function"]["name"] == "action_enabled"
        )
        self.assertIn("action_code", action_enabled["function"]["parameters"]["required"])
        self.assertEqual(
            action_enabled["function"]["parameters"]["properties"]["action_code"]["type"],
            "string"
        )

    def test_descriptions_are_clear(self):
        """Test descriptions are clear and helpful"""
        for tool_def in TOOL_DEFINITIONS:
            if tool_def["function"]["name"].startswith("get_") or tool_def["function"]["name"] in [
                "has_time_selection", "action_enabled"
            ]:
                description = tool_def["function"]["description"]
                self.assertGreater(len(description), 20, "Description too short")
                has_keyword = ("Get" in description or "Check" in description or 
                              "returns" in description.lower() or "query" in description.lower())
                self.assertTrue(has_keyword, f"Description should explain what it does: {description}")


class TestStateQueryMessageFormat(unittest.TestCase):
    """Test state query message format and C++ bridge communication"""

    def setUp(self):
        """Set up test fixtures"""
        self.mock_stdout = MockStdout()
        self.executor = ToolExecutor(stdout=self.mock_stdout)

    def test_state_query_message_format(self):
        """Test state query message format sent to C++"""
        # Start reader with mock stdin
        mock_stdin = MockStdin()
        self.executor.start_reader(stdin=mock_stdin)

        # Add a response
        mock_stdin.add_response({
            "type": "tool_result",
            "result": {
                "call_id": "call_1",
                "success": True,
                "value": 5.5
            }
        })

        # Execute state query
        result = self.executor.execute_state_query("get_selection_start_time")

        # Check message was written
        self.assertGreater(len(self.mock_stdout.written_data), 0)
        message = json.loads(self.mock_stdout.written_data[-1])

        # Verify message format
        self.assertEqual(message["type"], "state_query")
        self.assertIn("call_id", message)
        self.assertEqual(message["query_type"], "get_selection_start_time")
        self.assertIn("parameters", message)

        # Clean up
        self.executor.stop_reader()

    def test_state_query_response_parsing(self):
        """Test state query response parsing"""
        mock_stdin = MockStdin()
        self.executor.start_reader(stdin=mock_stdin)

        # Add a response
        mock_stdin.add_response({
            "type": "tool_result",
            "result": {
                "call_id": "call_1",
                "query_type": "get_selection_start_time",
                "success": True,
                "value": 10.5
            }
        })

        # Execute state query
        result = self.executor.execute_state_query("get_selection_start_time")

        # Verify response parsing
        self.assertTrue(result.get("success"))
        self.assertEqual(result.get("value"), 10.5)

        self.executor.stop_reader()

    def test_error_handling_invalid_query(self):
        """Test error handling for invalid queries"""
        mock_stdin = MockStdin()
        self.executor.start_reader(stdin=mock_stdin)

        # Add error response
        mock_stdin.add_response({
            "type": "tool_result",
            "result": {
                "call_id": "call_1",
                "query_type": "invalid_query",
                "success": False,
                "error": "Unknown query type: invalid_query"
            }
        })

        # Execute invalid query
        result = self.executor.execute_state_query("invalid_query")

        # Verify error handling
        self.assertFalse(result.get("success"))
        self.assertIn("error", result)

        self.executor.stop_reader()

    def test_timeout_handling(self):
        """Test timeout handling for state queries"""
        mock_stdin = MockStdin()
        # Don't add any response - will timeout
        self.executor.start_reader(stdin=mock_stdin)

        # Execute query with short timeout
        result = self.executor.execute_state_query("get_selection_start_time")

        # Should get timeout error
        self.assertFalse(result.get("success"))
        error_msg = result.get("error", "").lower()
        self.assertTrue("timeout" in error_msg or "timed out" in error_msg, 
                       f"Expected timeout error, got: {error_msg}")

        self.executor.stop_reader()


class TestMockedCppResponses(unittest.TestCase):
    """Test state query tools with mocked C++ responses"""

    def setUp(self):
        """Set up test fixtures"""
        self.mock_stdout = MockStdout()
        self.executor = ToolExecutor(stdout=self.mock_stdout)
        self.state_tools = StateQueryTools(self.executor)

    def test_mocked_successful_response(self):
        """Test state query with mocked successful C++ response"""
        with patch.object(self.executor, 'execute_state_query') as mock_query:
            mock_query.return_value = {
                "call_id": "call_1",
                "query_type": "get_selection_start_time",
                "success": True,
                "value": 7.5
            }
            result = self.state_tools.get_selection_start_time()
            self.assertEqual(result, 7.5)

    def test_mocked_error_response(self):
        """Test state query with mocked error response"""
        with patch.object(self.executor, 'execute_state_query') as mock_query:
            mock_query.return_value = {
                "call_id": "call_1",
                "query_type": "get_cursor_position",
                "success": False,
                "error": "Playback state not available"
            }
            result = self.state_tools.get_cursor_position()
            self.assertIsNone(result)

    def test_state_query_execution_flow(self):
        """Test complete state query execution flow"""
        mock_stdin = MockStdin()
        self.executor.start_reader(stdin=mock_stdin)

        # Simulate complete flow: send query, receive response
        mock_stdin.add_response({
            "type": "tool_result",
            "result": {
                "call_id": "call_1",
                "query_type": "has_time_selection",
                "success": True,
                "value": True
            }
        })

        result = self.state_tools.has_time_selection()

        # Verify complete flow
        self.assertTrue(result)
        self.assertTrue(self.mock_stdout.flush_called)

        self.executor.stop_reader()


if __name__ == '__main__':
    unittest.main()

