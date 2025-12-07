#!/usr/bin/env python3
"""
Prerequisite Resolver Phase
Ensures all prerequisites are met before tool execution by adding prerequisite tools.

DEPRECATED: This module is superseded by the State Preparation system:
- state_contracts.py - Ground truth state requirements from C++
- state_gap_analyzer.py - Compares current state against requirements
- value_inference.py - Infers missing values from user message
- state_preparation.py - Orchestrates the state preparation loop

This module is kept for backward compatibility but should not be used for new code.
The planning_orchestrator.py now uses StatePreparationOrchestrator as the primary
mechanism, falling back to this module only when state prep fails.
"""

from typing import Dict, Any, List, Optional, Set, Tuple
from tool_schemas import TOOL_PREREQUISITES


class PrerequisiteResolver:
    """
    Resolves missing prerequisites by adding prerequisite tools to execution plan.
    """

    # Map prerequisites to tools that can satisfy them
    PREREQUISITE_TO_TOOL = {
        "time_selection": "set_time_selection",
        "selected_clips": "select_all",  # Or more specific clip selection
        "selected_tracks": "select_all_tracks",
        "cursor_position": None,  # Can't be set, only queried
        "project_open": None,  # Can't be set, only checked
    }
    
    # Tools that respect track selection (only operate on selected tracks)
    # These should check for selected_tracks but not require it (soft prerequisite)
    TRACK_SELECTION_RESPECTING_TOOLS = {
        "trim_to_selection",
        "cut",
        "copy",
        "delete_selection",
        "silence_selection",
        "apply_noise_reduction",
        "apply_normalize",
        "apply_amplify",
        "apply_fade_in",
        "apply_fade_out",
        "apply_reverse",
        "apply_invert",
        "apply_normalize_loudness",
        "apply_compressor",
        "apply_limiter",
        "apply_truncate_silence",
    }

    def __init__(self, tool_registry):
        """
        Initialize prerequisite resolver.

        Args:
            tool_registry: ToolRegistry instance
        """
        self.tool_registry = tool_registry

    def check_prerequisites(
        self,
        tool_name: str,
        current_state: Dict[str, Any]
    ) -> Tuple[bool, List[str]]:
        """
        Check if prerequisites for a tool are met.

        Args:
            tool_name: Name of the tool
            current_state: Current state snapshot

        Returns:
            Tuple of (all_met, missing_prerequisites)
        """
        if tool_name not in TOOL_PREREQUISITES:
            # No prerequisites defined, assume OK
            return True, []

        prerequisites = TOOL_PREREQUISITES[tool_name]
        missing = []

        # Check project_open (always required if True)
        if prerequisites.get("project_open") is True:
            if not current_state.get("project_open", False):
                missing.append("project_open")

        # Check time_selection
        time_selection_req = prerequisites.get("time_selection")
        if time_selection_req is True:  # Required
            if not current_state.get("has_time_selection", False):
                missing.append("time_selection")
        # Optional (False) or None - no check needed

        # Check selected_clips
        selected_clips_req = prerequisites.get("selected_clips")
        if selected_clips_req is True:  # Required
            selected_clips = current_state.get("selected_clips", [])
            if not selected_clips:
                missing.append("selected_clips")

        # Check selected_tracks
        selected_tracks_req = prerequisites.get("selected_tracks")
        if selected_tracks_req is True:  # Required
            selected_tracks = current_state.get("selected_tracks", [])
            if not selected_tracks:
                missing.append("selected_tracks")
        
        # Check for tools that respect track selection (soft prerequisite)
        # These tools operate on selected tracks, so we should ensure tracks are selected
        # But we prefer to use existing selection rather than selecting all
        if tool_name in self.TRACK_SELECTION_RESPECTING_TOOLS:
            selected_tracks = current_state.get("selected_tracks", [])
            # If no tracks selected, we'll add a soft prerequisite (not an error, just a suggestion)
            # This will be handled in resolve_missing_prerequisites

        # Check cursor_position (optional only)
        cursor_position_req = prerequisites.get("cursor_position")
        if cursor_position_req is True:  # Required
            cursor = current_state.get("cursor_position")
            if cursor is None:
                missing.append("cursor_position")

        all_met = len(missing) == 0
        return all_met, missing

    def resolve_missing_prerequisites(
        self,
        execution_plan: List[Dict[str, Any]],
        current_state: Dict[str, Any]
    ) -> Tuple[List[Dict[str, Any]], List[str]]:
        """
        Resolve missing prerequisites by adding prerequisite tools to plan.

        Args:
            execution_plan: List of tool calls
            current_state: Current state snapshot

        Returns:
            Tuple of (resolved_plan, errors)
        """
        resolved_plan = []
        errors = []
        added_prerequisites: Set[str] = set()  # Track what we've already added

        for tool_call in execution_plan:
            tool_name = tool_call.get("tool_name")
            if not tool_name:
                errors.append(f"Tool call missing tool_name: {tool_call}")
                continue

            # Check prerequisites for this tool
            all_met, missing = self.check_prerequisites(tool_name, current_state)

            # Check for tools that respect track selection (soft prerequisite)
            # CRITICAL: Do NOT add select_all_tracks() automatically
            # These tools operate on currently selected tracks only
            # If tracks are already selected, use them
            # If no tracks selected, the tool will operate on nothing (correct behavior)
            # Only select all tracks if user explicitly requests "all tracks"
            if tool_name in self.TRACK_SELECTION_RESPECTING_TOOLS:
                selected_tracks = current_state.get("selected_tracks", [])
                # If tracks are already selected, we're good - don't add select_all_tracks
                # If no tracks selected, that's OK - tool will operate on nothing
                # We NEVER auto-add select_all_tracks for these tools
                # User must explicitly request "all tracks" in their message

            if not all_met:
                # Try to resolve each missing prerequisite
                for prereq in missing:
                    if prereq in added_prerequisites:
                        # Already added this prerequisite earlier in the plan
                        continue

                    prerequisite_tool = self._get_prerequisite_tool(prereq, current_state)
                    if prerequisite_tool:
                        # Add prerequisite tool before the tool that needs it
                        resolved_plan.append(prerequisite_tool)
                        added_prerequisites.add(prereq)

                        # Update state for next checks (optimistic)
                        if prereq == "time_selection":
                            # We'll set time selection, so mark it as available
                            current_state["has_time_selection"] = True
                        elif prereq == "selected_clips":
                            current_state["selected_clips"] = ["*"]  # Mark as selected
                        elif prereq == "selected_tracks":
                            current_state["selected_tracks"] = ["*"]  # Mark as selected
                    else:
                        errors.append(
                            f"Cannot resolve prerequisite '{prereq}' for tool '{tool_name}'. "
                            f"Please ensure {prereq} is available before using {tool_name}."
                        )

            # Add the original tool call
            resolved_plan.append(tool_call)

        return resolved_plan, errors

    def _get_prerequisite_tool(
        self,
        prerequisite: str,
        current_state: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Get the tool call needed to satisfy a prerequisite.

        Args:
            prerequisite: Prerequisite name
            current_state: Current state snapshot

        Returns:
            Tool call dictionary, or None if can't be resolved
        """
        if prerequisite == "time_selection":
            # Try to get selection from state
            start = current_state.get("selection_start_time")
            end = current_state.get("selection_end_time")
            if start is not None and end is not None:
                return {
                    "tool_name": "set_time_selection",
                    "arguments": {
                        "start_time": start,
                        "end_time": end
                    }
                }
            else:
                # Can't determine selection, return None (will error)
                return None

        elif prerequisite == "selected_clips":
            # Select all (which selects clips)
            return {
                "tool_name": "select_all",
                "arguments": {}
            }

        elif prerequisite == "selected_tracks":
            # Only add select_all_tracks if it's a hard requirement (like delete_track)
            # For tools that respect track selection, we should NOT auto-select all tracks
            # Check if tracks are already selected in current_state
            selected_tracks = current_state.get("selected_tracks", [])
            if selected_tracks:
                # Tracks already selected, don't add select_all_tracks
                return None
            # Only add if it's truly required (not for tools that respect selection)
            # This will be handled by the calling code checking if it's a hard requirement
            return {
                "tool_name": "select_all_tracks",
                "arguments": {}
            }

        elif prerequisite == "project_open":
            # Can't be set, only checked
            return None

        elif prerequisite == "cursor_position":
            # Can't be set, only queried
            return None

        return None

    def order_by_dependencies(
        self,
        execution_plan: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], List[str]]:
        """
        Order tools by dependencies (topological sort).

        Args:
            execution_plan: List of tool calls

        Returns:
            Tuple of (ordered_plan, errors)
        """
        # Simple dependency tracking
        # Tools that set state should come before tools that use it
        state_setters = {
            "set_time_selection",
            "set_selection_start_time",
            "set_selection_end_time",
            "select_all",
            "select_all_tracks",
            "seek"  # Sets cursor position
        }

        ordered_plan = []
        remaining = execution_plan.copy()
        errors = []

        # First pass: add all state setters
        for tool_call in execution_plan:
            tool_name = tool_call.get("tool_name")
            if tool_name in state_setters:
                ordered_plan.append(tool_call)
                remaining.remove(tool_call)

        # Second pass: add remaining tools
        ordered_plan.extend(remaining)

        # Check for circular dependencies (simple check)
        # This is a basic implementation - could be enhanced
        tool_names = [tc.get("tool_name") for tc in ordered_plan]
        if len(tool_names) != len(set(tool_names)):
            # Duplicate tools might indicate circular dependency
            pass  # For now, allow duplicates (might be intentional)

        return ordered_plan, errors

    def resolve(
        self,
        execution_plan: List[Dict[str, Any]],
        current_state: Dict[str, Any]
    ) -> Tuple[List[Dict[str, Any]], List[str]]:
        """
        Complete prerequisite resolution process.

        Args:
            execution_plan: List of tool calls
            current_state: Current state snapshot

        Returns:
            Tuple of (resolved_plan, errors)
        """
        # Resolve missing prerequisites
        resolved_plan, errors = self.resolve_missing_prerequisites(execution_plan, current_state)

        if errors:
            return resolved_plan, errors

        # Order by dependencies
        ordered_plan, order_errors = self.order_by_dependencies(resolved_plan)
        errors.extend(order_errors)

        return ordered_plan, errors

