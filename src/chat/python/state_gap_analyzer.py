#!/usr/bin/env python3
"""
State Gap Analyzer

Compares current state against tool state contracts to identify:
1. What state is missing
2. What state-setting tools are needed
3. What values need to be inferred
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from state_contracts import (
    get_contract,
    get_state_setting_tool,
    StateKey,
    StateRequirement,
    ToolStateContract
)


@dataclass
class StateGap:
    """A single state gap that needs to be filled."""
    state_key: StateKey
    required: bool
    current_value: Any
    needs_value: bool  # True if we need to determine what value to set
    suggested_tool: Optional[str]
    fallback_key: Optional[StateKey] = None


@dataclass
class GapAnalysisResult:
    """Result of analyzing state gaps for a tool."""
    tool_name: str
    can_execute: bool  # True if all required state exists
    gaps: List[StateGap]
    missing_parameters: List[str]  # Tool parameters not provided


class StateGapAnalyzer:
    """Analyzes gaps between current state and tool requirements."""

    # Map StateKey enum to state dict keys
    STATE_KEY_MAP = {
        StateKey.HAS_TIME_SELECTION: "has_time_selection",
        StateKey.SELECTION_START_TIME: "selection_start_time",
        StateKey.SELECTION_END_TIME: "selection_end_time",
        StateKey.CURSOR_POSITION: "cursor_position",
        StateKey.SELECTED_TRACKS: "selected_tracks",
        StateKey.SELECTED_CLIPS: "selected_clips",
        StateKey.TRACK_LIST: "track_list",
        StateKey.TOTAL_PROJECT_TIME: "total_project_time",
        StateKey.PROJECT_OPEN: "project_open",
    }

    def __init__(self):
        pass

    def analyze(
        self,
        tool_name: str,
        tool_arguments: Dict[str, Any],
        current_state: Dict[str, Any]
    ) -> GapAnalysisResult:
        """
        Analyze state gaps for a tool.

        Args:
            tool_name: Name of the tool to execute
            tool_arguments: Arguments provided for the tool
            current_state: Current state snapshot

        Returns:
            GapAnalysisResult with identified gaps
        """
        contract = get_contract(tool_name)
        if not contract:
            # No contract = no known requirements, assume OK
            return GapAnalysisResult(
                tool_name=tool_name,
                can_execute=True,
                gaps=[],
                missing_parameters=[]
            )

        gaps = []
        can_execute = True

        # Check each state requirement
        for requirement in contract.state_reads:
            state_key = requirement.key
            current_value = self._get_state_value(state_key, current_state)

            has_value = self._has_valid_value(state_key, current_value)

            if not has_value:
                # Check for fallback
                if requirement.fallback_from:
                    fallback_value = self._get_state_value(
                        requirement.fallback_from,
                        current_state
                    )
                    if self._has_valid_value(requirement.fallback_from, fallback_value):
                        # Fallback available, not a gap
                        continue

                # This is a gap
                gap = StateGap(
                    state_key=state_key,
                    required=requirement.required,
                    current_value=current_value,
                    needs_value=True,
                    suggested_tool=get_state_setting_tool(state_key),
                    fallback_key=requirement.fallback_from
                )
                gaps.append(gap)

                if requirement.required:
                    can_execute = False

        # Check for missing parameters
        missing_params = []
        for param_name in contract.parameters.keys():
            if param_name not in tool_arguments:
                missing_params.append(param_name)
                can_execute = False

        return GapAnalysisResult(
            tool_name=tool_name,
            can_execute=can_execute,
            gaps=gaps,
            missing_parameters=missing_params
        )

    def _get_state_value(self, key: StateKey, state: Dict[str, Any]) -> Any:
        """Get state value, handling key name mapping."""
        state_key_str = self.STATE_KEY_MAP.get(key, key.value)
        return state.get(state_key_str)

    def _has_valid_value(self, key: StateKey, value: Any) -> bool:
        """Check if a state value is valid (not None/empty)."""
        if value is None:
            return False

        if key == StateKey.HAS_TIME_SELECTION:
            return value is True

        if key in (StateKey.SELECTED_TRACKS, StateKey.SELECTED_CLIPS, StateKey.TRACK_LIST):
            return isinstance(value, list) and len(value) > 0

        if key in (StateKey.SELECTION_START_TIME, StateKey.SELECTION_END_TIME,
                   StateKey.CURSOR_POSITION, StateKey.TOTAL_PROJECT_TIME):
            return isinstance(value, (int, float))

        if key == StateKey.PROJECT_OPEN:
            return value is True

        return value is not None

    def get_gaps_for_state_keys(
        self,
        required_keys: List[StateKey],
        current_state: Dict[str, Any]
    ) -> List[StateGap]:
        """
        Get gaps for a specific list of state keys.
        Useful for checking if specific state values are available.

        Args:
            required_keys: List of state keys to check
            current_state: Current state snapshot

        Returns:
            List of gaps for missing state
        """
        gaps = []
        for key in required_keys:
            current_value = self._get_state_value(key, current_state)
            if not self._has_valid_value(key, current_value):
                gap = StateGap(
                    state_key=key,
                    required=True,
                    current_value=current_value,
                    needs_value=True,
                    suggested_tool=get_state_setting_tool(key),
                    fallback_key=None
                )
                gaps.append(gap)
        return gaps

    def analyze_multiple_tools(
        self,
        tool_calls: List[Dict[str, Any]],
        current_state: Dict[str, Any]
    ) -> List[GapAnalysisResult]:
        """
        Analyze gaps for multiple tools in sequence.
        Simulates state changes from each tool to provide accurate gap analysis.

        Args:
            tool_calls: List of tool calls with 'tool_name' and 'arguments'
            current_state: Initial state snapshot

        Returns:
            List of gap analysis results for each tool
        """
        results = []
        simulated_state = current_state.copy()

        for tool_call in tool_calls:
            tool_name = tool_call.get("tool_name", "")
            tool_args = tool_call.get("arguments", {})

            result = self.analyze(tool_name, tool_args, simulated_state)
            results.append(result)

            # Simulate state changes from this tool
            self._simulate_state_change(tool_name, tool_args, simulated_state)

        return results

    def _simulate_state_change(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        state: Dict[str, Any]
    ):
        """
        Simulate state changes from a tool execution.
        Updates state dict in place.
        """
        contract = get_contract(tool_name)
        if not contract:
            return

        # Simulate based on tool
        if tool_name == "set_time_selection":
            state["has_time_selection"] = True
            if "start_time" in arguments:
                state["selection_start_time"] = arguments["start_time"]
            if "end_time" in arguments:
                state["selection_end_time"] = arguments["end_time"]

        elif tool_name == "select_all_tracks":
            # Mark as having track selection
            track_list = state.get("track_list", [])
            if track_list:
                state["selected_tracks"] = track_list.copy()
            else:
                state["selected_tracks"] = ["*"]  # Placeholder

        elif tool_name == "select_all":
            # Selects all audio and tracks
            state["has_time_selection"] = True
            state["selected_tracks"] = state.get("track_list", ["*"])

        elif tool_name == "clear_selection":
            state["has_time_selection"] = False
            state["selected_tracks"] = []
            state["selected_clips"] = []

        elif tool_name == "seek":
            if "time" in arguments:
                state["cursor_position"] = arguments["time"]

        # For state_writes, we can update based on contract
        for state_key in contract.state_writes:
            key_str = self.STATE_KEY_MAP.get(state_key, state_key.value)
            # Already handled specific tools above
            # For other tools, mark as potentially changed
            if state_key == StateKey.HAS_TIME_SELECTION and tool_name in (
                "cut", "delete_selection", "delete_all_tracks_ripple", "cut_all_tracks_ripple"
            ):
                state["has_time_selection"] = False

            if state_key == StateKey.SELECTED_CLIPS and tool_name in (
                "split", "split_at_time", "paste", "duplicate_clip"
            ):
                # Tool creates/selects clips
                state["selected_clips"] = ["*"]  # Placeholder


def analyze_tool_requirements(
    tool_name: str,
    tool_arguments: Dict[str, Any],
    current_state: Dict[str, Any]
) -> GapAnalysisResult:
    """
    Convenience function for single tool gap analysis.

    Args:
        tool_name: Name of the tool
        tool_arguments: Tool arguments
        current_state: Current state snapshot

    Returns:
        Gap analysis result
    """
    analyzer = StateGapAnalyzer()
    return analyzer.analyze(tool_name, tool_arguments, current_state)
