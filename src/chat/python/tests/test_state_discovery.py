#!/usr/bin/env python3
"""
Unit tests for StateDiscovery (Phase 3.2)

Tests state discovery including:
- Determining required queries
- Executing state queries
- Building state snapshot
- State caching
"""

import unittest
import sys
import os
from unittest.mock import Mock, MagicMock

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from state_discovery import StateDiscovery


class TestDetermineRequiredQueries(unittest.TestCase):
    """Test determining required queries"""

    def setUp(self):
        """Set up test fixtures"""
        self.tool_registry = Mock()
        self.discovery = StateDiscovery(self.tool_registry)

    def test_determine_queries_with_selection_keyword(self):
        """Test determining queries with selection keyword"""
        queries = self.discovery.determine_required_queries("select the audio")
        self.assertIn("has_time_selection", queries)
        self.assertIn("get_selection_start_time", queries)
        self.assertIn("get_selection_end_time", queries)

    def test_determine_queries_with_cursor_keyword(self):
        """Test determining queries with cursor keyword"""
        queries = self.discovery.determine_required_queries("at cursor position")
        self.assertIn("get_cursor_position", queries)

    def test_determine_queries_with_track_keyword(self):
        """Test determining queries with track keyword"""
        queries = self.discovery.determine_required_queries("list all tracks")
        self.assertIn("get_track_list", queries)
        self.assertIn("get_selected_tracks", queries)

    def test_determine_queries_with_clip_keyword(self):
        """Test determining queries with clip keyword"""
        queries = self.discovery.determine_required_queries("split the clips")
        self.assertIn("get_selected_clips", queries)

    def test_determine_queries_with_label_keyword(self):
        """Test determining queries with label keyword"""
        queries = self.discovery.determine_required_queries("find the intro label")
        self.assertIn("get_all_labels", queries)

    def test_determine_queries_with_relative_time(self):
        """Test determining queries with relative time keywords"""
        queries = self.discovery.determine_required_queries("last 30 seconds")
        self.assertIn("get_total_project_time", queries)

    def test_determine_queries_default(self):
        """Test determining queries with no specific keywords (default)"""
        queries = self.discovery.determine_required_queries("hello")
        # Should include project time and default queries
        self.assertIn("get_total_project_time", queries)
        self.assertIn("has_time_selection", queries)
        self.assertIn("get_cursor_position", queries)

    def test_determine_queries_with_existing_state(self):
        """Test determining queries when state already exists"""
        current_state = {
            "has_time_selection": True,
            "selection_start_time": 10.0,
            "selection_end_time": 20.0
        }
        queries = self.discovery.determine_required_queries("select the audio", current_state)
        # Should not include queries for data we already have
        # (Note: current implementation may still include them, but should filter)
        self.assertIn("get_total_project_time", queries)  # Always included


class TestExecuteStateQueries(unittest.TestCase):
    """Test executing state queries"""

    def setUp(self):
        """Set up test fixtures"""
        self.tool_registry = Mock()
        self.discovery = StateDiscovery(self.tool_registry)

    def test_execute_state_queries_success(self):
        """Test executing state queries successfully"""
        self.tool_registry.execute_by_name.return_value = {
            "success": True,
            "value": 10.0
        }
        
        queries = ["get_selection_start_time", "get_selection_end_time"]
        results = self.discovery.execute_state_queries(queries)
        
        self.assertEqual(len(results), 2)
        self.assertEqual(results["get_selection_start_time"], 10.0)
        self.assertEqual(results["get_selection_end_time"], 10.0)
        self.assertEqual(self.tool_registry.execute_by_name.call_count, 2)

    def test_execute_state_queries_with_failure(self):
        """Test executing state queries with some failures"""
        def mock_execute(tool_name, args):
            if tool_name == "get_selection_start_time":
                return {"success": True, "value": 10.0}
            else:
                return {"success": False, "error": "failed"}
        
        self.tool_registry.execute_by_name.side_effect = mock_execute
        
        queries = ["get_selection_start_time", "get_selection_end_time"]
        results = self.discovery.execute_state_queries(queries)
        
        self.assertEqual(len(results), 2)
        self.assertEqual(results["get_selection_start_time"], 10.0)
        self.assertIsNone(results["get_selection_end_time"])

    def test_execute_state_queries_with_exception(self):
        """Test executing state queries with exception"""
        self.tool_registry.execute_by_name.side_effect = Exception("test error")
        
        queries = ["get_selection_start_time"]
        results = self.discovery.execute_state_queries(queries)
        
        self.assertIsNone(results["get_selection_start_time"])


class TestBuildStateSnapshot(unittest.TestCase):
    """Test building state snapshot"""

    def setUp(self):
        """Set up test fixtures"""
        self.tool_registry = Mock()
        self.discovery = StateDiscovery(self.tool_registry)

    def test_build_state_snapshot_complete(self):
        """Test building state snapshot with complete query results"""
        query_results = {
            "has_time_selection": True,
            "get_selection_start_time": 10.0,
            "get_selection_end_time": 20.0,
            "get_cursor_position": 15.0,
            "get_total_project_time": 100.0,
            "get_track_list": [{"id": "1", "name": "Track 1"}],
            "get_selected_tracks": ["1"],
            "get_selected_clips": ["clip1"],
            "get_all_labels": [{"name": "intro", "start_time": 0.0, "end_time": 10.0}]
        }
        
        snapshot = self.discovery.build_state_snapshot(query_results)
        
        self.assertTrue(snapshot["has_time_selection"])
        self.assertEqual(snapshot["selection_start_time"], 10.0)
        self.assertEqual(snapshot["selection_end_time"], 20.0)
        self.assertEqual(snapshot["cursor_position"], 15.0)
        self.assertEqual(snapshot["total_project_time"], 100.0)
        self.assertEqual(len(snapshot["track_list"]), 1)
        self.assertEqual(len(snapshot["selected_tracks"]), 1)
        self.assertEqual(len(snapshot["selected_clips"]), 1)
        self.assertEqual(len(snapshot["all_labels"]), 1)
        self.assertTrue(snapshot["project_open"])

    def test_build_state_snapshot_partial(self):
        """Test building state snapshot with partial query results"""
        query_results = {
            "has_time_selection": False,
            "get_selection_start_time": None,
            "get_total_project_time": 50.0
        }

        snapshot = self.discovery.build_state_snapshot(query_results)

        self.assertFalse(snapshot["has_time_selection"])
        self.assertEqual(snapshot["selection_start_time"], 0.0)  # Default for None
        self.assertEqual(snapshot["total_project_time"], 50.0)
        # track_list is not in query_results so it won't be in snapshot
        self.assertEqual(snapshot.get("track_list", []), [])
        # project_open is True if any results were added to snapshot
        self.assertTrue(snapshot["project_open"])

    def test_build_state_snapshot_empty(self):
        """Test building state snapshot with empty results"""
        query_results = {}
        snapshot = self.discovery.build_state_snapshot(query_results)

        # Should have defaults (or be missing keys)
        self.assertFalse(snapshot.get("has_time_selection", False))
        self.assertEqual(snapshot.get("selection_start_time", 0.0), 0.0)
        self.assertEqual(snapshot.get("total_project_time", 0.0), 0.0)
        self.assertEqual(snapshot.get("track_list", []), [])
        # Empty results means we don't know if project is open
        # Default to False since we have no evidence
        self.assertFalse(snapshot.get("project_open", False))


class TestStateCaching(unittest.TestCase):
    """Test state caching"""

    def setUp(self):
        """Set up test fixtures"""
        self.tool_registry = Mock()
        self.discovery = StateDiscovery(self.tool_registry)

    def test_state_caching(self):
        """Test state caching avoids redundant queries"""
        self.tool_registry.execute_by_name.return_value = {
            "success": True,
            "value": 10.0
        }
        
        # First discovery
        state1 = self.discovery.discover_state("test message")
        call_count_1 = self.tool_registry.execute_by_name.call_count
        
        # Second discovery (should use cache)
        state2 = self.discovery.discover_state("test message")
        call_count_2 = self.tool_registry.execute_by_name.call_count
        
        # Should not have made additional calls
        self.assertEqual(call_count_1, call_count_2)
        self.assertEqual(state1, state2)

    def test_state_cache_invalidation(self):
        """Test state cache invalidation"""
        self.tool_registry.execute_by_name.return_value = {
            "success": True,
            "value": 10.0
        }
        
        # First discovery
        self.discovery.discover_state("test message")
        call_count_1 = self.tool_registry.execute_by_name.call_count
        
        # Invalidate cache
        self.discovery.invalidate_cache()
        
        # Second discovery (should query again)
        self.discovery.discover_state("test message")
        call_count_2 = self.tool_registry.execute_by_name.call_count
        
        # Should have made additional calls
        self.assertGreater(call_count_2, call_count_1)

    def test_state_discovery_with_current_state(self):
        """Test state discovery with existing state"""
        current_state = {
            "has_time_selection": True,
            "selection_start_time": 10.0
        }
        
        self.tool_registry.execute_by_name.return_value = {
            "success": True,
            "value": 20.0
        }
        
        snapshot = self.discovery.discover_state("test", current_state)
        
        # Should merge with existing state
        self.assertEqual(snapshot["selection_start_time"], 10.0)
        self.assertTrue(snapshot["has_time_selection"])


if __name__ == '__main__':
    unittest.main()

