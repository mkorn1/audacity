#!/usr/bin/env python3
"""
Pre-Execution Validator
Validates runtime conditions before tool execution and ensures all required state is available.
This layer bridges the gap between visual state (what user sees) and programmatic state.

Runs AFTER planning but BEFORE execution to catch runtime conditions that may not be
captured by static prerequisites.

DEPRECATED: This module is superseded by the State Preparation system:
- state_contracts.py - Ground truth state requirements from C++
- state_gap_analyzer.py - Compares current state against requirements
- value_inference.py - Infers missing values from user message
- state_preparation.py - Orchestrates the state preparation loop
- state_verification.py - Verifies state changes after execution

This module is kept for backward compatibility but should not be used for new code.
The planning_orchestrator.py now uses StatePreparationOrchestrator as the primary
mechanism, which handles both state preparation AND runtime validation.
"""

import logging
from typing import Dict, Any, Optional, List, Tuple
from tool_schemas import TOOL_PREREQUISITES

logger = logging.getLogger(__name__)


class PreExecutionValidator:
    """
    Validates and prepares tools for execution by checking runtime conditions.
    This is a post-planning, pre-execution validation layer that ensures tools
    can actually execute given the current runtime state.
    """

    def __init__(self, tool_registry):
        """
        Initialize pre-execution validator.

        Args:
            tool_registry: ToolRegistry instance for executing state queries
        """
        self.tool_registry = tool_registry

    def validate_and_prepare(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        current_state: Dict[str, Any]
    ) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str], List[Dict[str, Any]]]:
        """
        Validate tool can execute and prepare prerequisites if needed.

        Args:
            tool_name: Name of tool to validate
            arguments: Tool arguments
            current_state: Current state snapshot

        Returns:
            Tuple of (can_execute, prepared_arguments, error_message, prerequisite_tools)
            - can_execute: Whether tool can execute
            - prepared_arguments: Modified arguments if needed
            - error_message: Error if validation fails
            - prerequisite_tools: List of tools to execute first to satisfy prerequisites
        """
        logger.debug(f"Validating tool: {tool_name} with args: {arguments}")

        # Get tool-specific validation logic
        validator_method = getattr(self, f"_validate_{tool_name}", None)
        if validator_method:
            return validator_method(arguments, current_state)
        else:
            # Default validation: check prerequisites
            return self._validate_default(tool_name, arguments, current_state)

    def _validate_default(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        current_state: Dict[str, Any]
    ) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str], List[Dict[str, Any]]]:
        """
        Default validation: check prerequisites and runtime conditions.

        Args:
            tool_name: Tool name
            arguments: Tool arguments
            current_state: Current state

        Returns:
            Validation result tuple
        """
        prerequisite_tools = []

        # Check prerequisites
        if tool_name in TOOL_PREREQUISITES:
            prerequisites = TOOL_PREREQUISITES[tool_name]

            # Check required prerequisites
            if prerequisites.get("time_selection") is True:
                if not current_state.get("has_time_selection", False):
                    # Try to get selection from state
                    start = current_state.get("selection_start_time")
                    end = current_state.get("selection_end_time")
                    if start is not None and end is not None:
                        prerequisite_tools.append({
                            "tool_name": "set_time_selection",
                            "arguments": {"start_time": start, "end_time": end}
                        })
                    else:
                        return False, None, f"Tool '{tool_name}' requires a time selection, but none exists. Please set a time selection first.", []

            if prerequisites.get("selected_clips") is True:
                selected_clips = current_state.get("selected_clips", [])
                if not selected_clips:
                    # Can't automatically select clips - need user action
                    return False, None, f"Tool '{tool_name}' requires selected clips, but none are selected. Please select clips first.", []

            if prerequisites.get("selected_tracks") is True:
                selected_tracks = current_state.get("selected_tracks", [])
                if not selected_tracks:
                    # Can't automatically select tracks for hard requirements
                    return False, None, f"Tool '{tool_name}' requires selected tracks, but none are selected. Please select tracks first.", []

        return True, arguments, None, prerequisite_tools

    def _validate_split(
        self,
        arguments: Dict[str, Any],
        current_state: Dict[str, Any]
    ) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str], List[Dict[str, Any]]]:
        """
        Validate split tool: needs cursor position OR time selection, and tracks.

        The split tool can work with:
        - Cursor position (if no time selection)
        - Time selection (if exists)
        - Selected tracks (optional, but recommended)

        Args:
            arguments: Tool arguments (should be empty for split)
            current_state: Current state

        Returns:
            Validation result tuple
        """
        prerequisite_tools = []

        # Query current state to ensure we have latest
        has_selection = current_state.get("has_time_selection", False)
        cursor_pos = current_state.get("cursor_position")
        selected_tracks = current_state.get("selected_tracks", [])

        # Re-query if missing
        if not has_selection and cursor_pos is None:
            # Query cursor position
            cursor_result = self.tool_registry.execute_by_name("get_cursor_position", {})
            if cursor_result.get("success"):
                cursor_pos = cursor_result.get("value")
                current_state["cursor_position"] = cursor_pos

        if not has_selection:
            # Query time selection
            has_selection_result = self.tool_registry.execute_by_name("has_time_selection", {})
            if has_selection_result.get("success"):
                has_selection = has_selection_result.get("value", False)
                current_state["has_time_selection"] = has_selection

        if not selected_tracks:
            # Query selected tracks
            tracks_result = self.tool_registry.execute_by_name("get_selected_tracks", {})
            if tracks_result.get("success"):
                selected_tracks = tracks_result.get("value", [])
                current_state["selected_tracks"] = selected_tracks

        # Check if we have a valid split point
        if not has_selection and cursor_pos is None:
            return False, None, "Split requires either a time selection or cursor position. Neither is available.", []

        # Check if we have tracks (soft requirement - split_at_time works on all tracks)
        if not selected_tracks:
            logger.warning("No tracks selected for split - will operate on all tracks")

        return True, arguments, None, prerequisite_tools

    def _validate_join(
        self,
        arguments: Dict[str, Any],
        current_state: Dict[str, Any]
    ) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str], List[Dict[str, Any]]]:
        """
        Validate join tool: requires selected clips.

        Args:
            arguments: Tool arguments
            current_state: Current state

        Returns:
            Validation result tuple
        """
        selected_clips = current_state.get("selected_clips", [])

        # Re-query if missing
        if not selected_clips:
            clips_result = self.tool_registry.execute_by_name("get_selected_clips", {})
            if clips_result.get("success"):
                selected_clips = clips_result.get("value", [])
                current_state["selected_clips"] = selected_clips

        if not selected_clips:
            return False, None, "Join requires selected clips, but none are selected. Please select clips first.", []

        return True, arguments, None, []

    def _validate_duplicate_clip(
        self,
        arguments: Dict[str, Any],
        current_state: Dict[str, Any]
    ) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str], List[Dict[str, Any]]]:
        """
        Validate duplicate_clip tool: requires selected clips.

        Args:
            arguments: Tool arguments
            current_state: Current state

        Returns:
            Validation result tuple
        """
        selected_clips = current_state.get("selected_clips", [])

        # Re-query if missing
        if not selected_clips:
            clips_result = self.tool_registry.execute_by_name("get_selected_clips", {})
            if clips_result.get("success"):
                selected_clips = clips_result.get("value", [])
                current_state["selected_clips"] = selected_clips

        if not selected_clips:
            return False, None, "Duplicate clip requires selected clips, but none are selected. Please select clips first.", []

        return True, arguments, None, []

    def _validate_trim_to_selection(
        self,
        arguments: Dict[str, Any],
        current_state: Dict[str, Any]
    ) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str], List[Dict[str, Any]]]:
        """
        Validate trim_to_selection: requires time selection.

        Args:
            arguments: Tool arguments
            current_state: Current state

        Returns:
            Validation result tuple
        """
        has_selection = current_state.get("has_time_selection", False)

        # Re-query if missing
        if not has_selection:
            has_selection_result = self.tool_registry.execute_by_name("has_time_selection", {})
            if has_selection_result.get("success"):
                has_selection = has_selection_result.get("value", False)
                current_state["has_time_selection"] = has_selection

        if not has_selection:
            # Try to get selection from state
            start = current_state.get("selection_start_time")
            end = current_state.get("selection_end_time")
            if start is not None and end is not None:
                return True, arguments, None, [{
                    "tool_name": "set_time_selection",
                    "arguments": {"start_time": start, "end_time": end}
                }]
            else:
                return False, None, "Trim requires a time selection, but none exists. Please set a time selection first.", []

        return True, arguments, None, []

    def _validate_cut(
        self,
        arguments: Dict[str, Any],
        current_state: Dict[str, Any]
    ) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str], List[Dict[str, Any]]]:
        """
        Validate cut tool: requires time selection.

        Args:
            arguments: Tool arguments
            current_state: Current state

        Returns:
            Validation result tuple
        """
        return self._validate_trim_to_selection(arguments, current_state)

    def _validate_copy(
        self,
        arguments: Dict[str, Any],
        current_state: Dict[str, Any]
    ) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str], List[Dict[str, Any]]]:
        """
        Validate copy tool: requires time selection.

        Args:
            arguments: Tool arguments
            current_state: Current state

        Returns:
            Validation result tuple
        """
        return self._validate_trim_to_selection(arguments, current_state)

    def _validate_delete_selection(
        self,
        arguments: Dict[str, Any],
        current_state: Dict[str, Any]
    ) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str], List[Dict[str, Any]]]:
        """
        Validate delete_selection: requires time selection.

        Args:
            arguments: Tool arguments
            current_state: Current state

        Returns:
            Validation result tuple
        """
        return self._validate_trim_to_selection(arguments, current_state)

    def _validate_silence_selection(
        self,
        arguments: Dict[str, Any],
        current_state: Dict[str, Any]
    ) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str], List[Dict[str, Any]]]:
        """
        Validate silence_selection: requires time selection.

        Args:
            arguments: Tool arguments
            current_state: Current state

        Returns:
            Validation result tuple
        """
        return self._validate_trim_to_selection(arguments, current_state)

    def _validate_apply_normalize(
        self,
        arguments: Dict[str, Any],
        current_state: Dict[str, Any]
    ) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str], List[Dict[str, Any]]]:
        """
        Validate effect tools: require time selection.

        Args:
            arguments: Tool arguments
            current_state: Current state

        Returns:
            Validation result tuple
        """
        return self._validate_trim_to_selection(arguments, current_state)

    def validate_execution_plan(
        self,
        execution_plan: List[Dict[str, Any]],
        current_state: Dict[str, Any]
    ) -> Tuple[List[Dict[str, Any]], List[str]]:
        """
        Validate entire execution plan and add prerequisite tools.

        Args:
            execution_plan: List of tool calls
            current_state: Current state snapshot

        Returns:
            Tuple of (validated_plan, errors)
        """
        validated_plan = []
        errors = []

        for tool_call in execution_plan:
            tool_name = tool_call.get("tool_name")
            arguments = tool_call.get("arguments", {})

            if not tool_name:
                errors.append(f"Tool call missing tool_name: {tool_call}")
                continue

            # Validate this tool
            can_execute, prepared_args, error_msg, prerequisite_tools = self.validate_and_prepare(
                tool_name,
                arguments,
                current_state
            )

            if not can_execute:
                errors.append(error_msg or f"Tool '{tool_name}' cannot execute")
                continue

            # Add prerequisite tools first
            for prereq_tool in prerequisite_tools:
                validated_plan.append(prereq_tool)
                logger.info(f"Added prerequisite tool: {prereq_tool['tool_name']}")

            # Add the validated tool with prepared arguments
            validated_tool_call = tool_call.copy()
            if prepared_args is not None:
                validated_tool_call["arguments"] = prepared_args
            validated_plan.append(validated_tool_call)

            # Update state optimistically for next tools
            # (This is a simplified update - in practice, we'd re-query after each tool)
            if tool_name == "set_time_selection":
                current_state["has_time_selection"] = True
                current_state["selection_start_time"] = prepared_args.get("start_time")
                current_state["selection_end_time"] = prepared_args.get("end_time")

        return validated_plan, errors

