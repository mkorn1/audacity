#!/usr/bin/env python3
"""
State Discovery Phase
Determines what state queries are needed and executes them to build a state snapshot.
"""

from typing import Dict, Any, List, Optional, Set
import re


class StateDiscovery:
    """
    Discovers project state by determining required queries and executing them.
    """

    # State query tool names
    STATE_QUERY_TOOLS = {
        "selection": ["has_time_selection", "get_selection_start_time", "get_selection_end_time"],
        "cursor": ["get_cursor_position"],
        "tracks": ["get_track_list", "get_selected_tracks"],
        "clips": ["get_selected_clips"],
        "labels": ["get_all_labels"],
        "project": ["get_total_project_time"],
        "actions": ["action_enabled"]  # For checking if actions are enabled
    }

    def __init__(self, tool_registry):
        """
        Initialize state discovery.

        Args:
            tool_registry: ToolRegistry instance for executing state queries
        """
        self.tool_registry = tool_registry
        self._state_cache: Dict[str, Any] = {}
        self._cache_valid = False

    def determine_required_queries(
        self,
        user_message: str,
        current_state: Optional[Dict[str, Any]] = None
    ) -> List[str]:
        """
        Determine which state queries are needed based on user message.

        Args:
            user_message: User's request
            current_state: Existing state snapshot (to avoid redundant queries)

        Returns:
            List of state query tool names to execute
        """
        user_message_lower = user_message.lower()
        required_queries: Set[str] = set()

        # Always query project state (total time, etc.)
        required_queries.update(self.STATE_QUERY_TOOLS["project"])

        # Check for selection-related keywords
        selection_keywords = ["selection", "select", "selected", "this", "trim", "cut", "delete", "copy"]
        if any(keyword in user_message_lower for keyword in selection_keywords):
            required_queries.update(self.STATE_QUERY_TOOLS["selection"])

        # Check for cursor-related keywords
        cursor_keywords = ["cursor", "playhead", "position", "at", "here"]
        if any(keyword in user_message_lower for keyword in cursor_keywords):
            required_queries.update(self.STATE_QUERY_TOOLS["cursor"])

        # Check for track-related keywords
        track_keywords = ["track", "tracks", "audio track", "mono", "stereo"]
        if any(keyword in user_message_lower for keyword in track_keywords):
            required_queries.update(self.STATE_QUERY_TOOLS["tracks"])

        # Check for clip-related keywords
        clip_keywords = ["clip", "clips", "split", "join"]
        if any(keyword in user_message_lower for keyword in clip_keywords):
            required_queries.update(self.STATE_QUERY_TOOLS["clips"])

        # Check for label-related keywords
        label_keywords = ["label", "labels", "marker", "markers", "intro", "outro", "chapter"]
        if any(keyword in user_message_lower for keyword in label_keywords):
            required_queries.update(self.STATE_QUERY_TOOLS["labels"])

        # Check for relative time references that need total time
        relative_time_keywords = ["last", "end", "total", "duration", "length"]
        if any(keyword in user_message_lower for keyword in relative_time_keywords):
            required_queries.update(self.STATE_QUERY_TOOLS["project"])

        # If no specific keywords found, query essential state
        if len(required_queries) == len(self.STATE_QUERY_TOOLS["project"]):
            # Default: query selection and cursor (most common operations)
            required_queries.update(self.STATE_QUERY_TOOLS["selection"])
            required_queries.update(self.STATE_QUERY_TOOLS["cursor"])

        # Remove queries that are already in current_state
        if current_state:
            filtered_queries = []
            for query in required_queries:
                # Map query names to state keys
                state_key_map = {
                    "has_time_selection": "has_time_selection",
                    "get_selection_start_time": "selection_start_time",
                    "get_selection_end_time": "selection_end_time",
                    "get_cursor_position": "cursor_position",
                    "get_total_project_time": "total_project_time",
                    "get_track_list": "track_list",
                    "get_selected_tracks": "selected_tracks",
                    "get_selected_clips": "selected_clips",
                    "get_all_labels": "all_labels"
                }
                state_key = state_key_map.get(query)
                if state_key and state_key not in current_state:
                    filtered_queries.append(query)
            required_queries = set(filtered_queries)

        return list(required_queries)

    def execute_state_queries(
        self,
        queries: List[str]
    ) -> Dict[str, Any]:
        """
        Execute state query tools and collect results.

        Args:
            queries: List of state query tool names

        Returns:
            Dictionary mapping query names to results
        """
        results = {}

        for query_name in queries:
            try:
                # Execute query (most state queries take no arguments)
                if query_name == "get_clips_on_track":
                    # This one requires track_id, skip for now
                    continue
                elif query_name == "action_enabled":
                    # This one requires action_code, skip for now
                    continue
                else:
                    result = self.tool_registry.execute_by_name(query_name, {})

                if result.get("success", False):
                    results[query_name] = result.get("value")
                else:
                    # Store error but continue with other queries
                    results[query_name] = None
                    print(f"State query {query_name} failed: {result.get('error', 'unknown')}", file=__import__('sys').stderr)

            except Exception as e:
                print(f"Error executing state query {query_name}: {e}", file=__import__('sys').stderr)
                results[query_name] = None

        return results

    def build_state_snapshot(
        self,
        query_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Build a normalized state snapshot from query results.

        Args:
            query_results: Dictionary mapping query names to results

        Returns:
            Normalized state snapshot dictionary
        """
        snapshot = {}

        # Map query results to normalized state keys
        if "has_time_selection" in query_results:
            snapshot["has_time_selection"] = query_results["has_time_selection"] or False

        if "get_selection_start_time" in query_results:
            value = query_results["get_selection_start_time"]
            snapshot["selection_start_time"] = value if value is not None else 0.0

        if "get_selection_end_time" in query_results:
            value = query_results["get_selection_end_time"]
            snapshot["selection_end_time"] = value if value is not None else 0.0

        if "get_cursor_position" in query_results:
            value = query_results["get_cursor_position"]
            snapshot["cursor_position"] = value if value is not None else 0.0

        if "get_total_project_time" in query_results:
            value = query_results["get_total_project_time"]
            snapshot["total_project_time"] = value if value is not None else 0.0

        if "get_track_list" in query_results:
            snapshot["track_list"] = query_results["get_track_list"] or []

        if "get_selected_tracks" in query_results:
            snapshot["selected_tracks"] = query_results["get_selected_tracks"] or []

        if "get_selected_clips" in query_results:
            snapshot["selected_clips"] = query_results["get_selected_clips"] or []

        if "get_all_labels" in query_results:
            snapshot["all_labels"] = query_results["get_all_labels"] or []

        # Mark that we have a project open if we got any results
        snapshot["project_open"] = len(snapshot) > 0

        return snapshot

    def discover_state(
        self,
        user_message: str,
        current_state: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Complete state discovery process.

        Args:
            user_message: User's request
            current_state: Existing state snapshot

        Returns:
            Complete state snapshot
        """
        # Check cache first
        if self._cache_valid and current_state is None:
            return self._state_cache.copy()

        # Determine required queries
        queries = self.determine_required_queries(user_message, current_state)

        # Execute queries
        query_results = self.execute_state_queries(queries)

        # Build snapshot
        snapshot = self.build_state_snapshot(query_results)

        # Merge with existing state
        if current_state:
            snapshot.update(current_state)

        # Update cache
        self._state_cache = snapshot.copy()
        self._cache_valid = True

        return snapshot

    def invalidate_cache(self):
        """Invalidate the state cache (call after state-changing operations)."""
        self._cache_valid = False
        self._state_cache = {}

