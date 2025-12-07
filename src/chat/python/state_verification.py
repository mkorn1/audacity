#!/usr/bin/env python3
"""
State Verification

Verifies that state changes succeeded after tool execution.
Enables the feedback loop in state preparation.
"""

from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
import logging

from state_contracts import get_contract, StateKey

logger = logging.getLogger(__name__)


@dataclass
class VerificationResult:
    """Result of state verification."""
    success: bool
    actual_state: Dict[str, Any]
    expected_changes: Dict[str, Any]
    discrepancies: List[str]  # List of state keys that didn't match
    error: Optional[str]


class StateVerifier:
    """Verifies state changes after tool execution."""

    # Map state keys to query tool names
    STATE_QUERY_MAP = {
        "has_time_selection": "has_time_selection",
        "selection_start_time": "get_selection_start_time",
        "selection_end_time": "get_selection_end_time",
        "cursor_position": "get_cursor_position",
        "selected_tracks": "get_selected_tracks",
        "selected_clips": "get_selected_clips",
        "track_list": "get_track_list",
        "total_project_time": "get_total_project_time",
    }

    def __init__(self, tool_registry=None):
        """
        Args:
            tool_registry: ToolRegistry instance for executing state queries
        """
        self.tool_registry = tool_registry

    def verify_state_change(
        self,
        tool_name: str,
        expected_state: Dict[str, Any],
        pre_execution_state: Dict[str, Any]
    ) -> VerificationResult:
        """
        Verify state changed as expected after tool execution.

        Args:
            tool_name: Tool that was executed
            expected_state: Expected state values after execution
            pre_execution_state: State before execution

        Returns:
            VerificationResult with success status and details
        """
        contract = get_contract(tool_name)
        if not contract:
            # No contract = no verification possible
            return VerificationResult(
                success=True,
                actual_state={},
                expected_changes={},
                discrepancies=[],
                error=None
            )

        # Determine which state keys to verify based on contract's state_writes
        keys_to_verify = [key.value for key in contract.state_writes]

        if not keys_to_verify:
            # Tool doesn't write state, nothing to verify
            return VerificationResult(
                success=True,
                actual_state={},
                expected_changes={},
                discrepancies=[],
                error=None
            )

        # Query current state
        try:
            actual_state = self._query_state_keys(keys_to_verify)
        except Exception as e:
            return VerificationResult(
                success=False,
                actual_state={},
                expected_changes=expected_state,
                discrepancies=[],
                error=f"Failed to query state: {str(e)}"
            )

        # Compare expected vs actual
        discrepancies = []
        for key in keys_to_verify:
            expected = expected_state.get(key)
            actual = actual_state.get(key)

            if expected is not None and not self._values_match(key, expected, actual):
                discrepancies.append(key)
                logger.warning(f"State mismatch for {key}: expected={expected}, actual={actual}")

        success = len(discrepancies) == 0

        return VerificationResult(
            success=success,
            actual_state=actual_state,
            expected_changes=expected_state,
            discrepancies=discrepancies,
            error=None if success else f"State verification failed for: {', '.join(discrepancies)}"
        )

    def verify_preparation_step(
        self,
        step_tool_name: str,
        step_arguments: Dict[str, Any]
    ) -> VerificationResult:
        """
        Verify a preparation step executed correctly.

        Args:
            step_tool_name: State-setting tool that was executed
            step_arguments: Arguments passed to the tool

        Returns:
            VerificationResult with success status
        """
        # Build expected state from arguments
        expected_state = {}

        if step_tool_name == "set_time_selection":
            expected_state["has_time_selection"] = True
            if "start_time" in step_arguments:
                expected_state["selection_start_time"] = step_arguments["start_time"]
            if "end_time" in step_arguments:
                expected_state["selection_end_time"] = step_arguments["end_time"]

        elif step_tool_name == "seek":
            if "time" in step_arguments:
                expected_state["cursor_position"] = step_arguments["time"]

        elif step_tool_name == "select_all_tracks":
            # Just verify tracks are now selected
            expected_state["selected_tracks"] = "any"  # Special: just check non-empty

        elif step_tool_name == "clear_selection":
            expected_state["has_time_selection"] = False

        return self.verify_state_change(
            tool_name=step_tool_name,
            expected_state=expected_state,
            pre_execution_state={}
        )

    def _query_state_keys(self, keys: List[str]) -> Dict[str, Any]:
        """Query current values for specified state keys."""
        state = {}

        if not self.tool_registry:
            logger.warning("No tool_registry available for state queries")
            return state

        for key in keys:
            query_tool = self.STATE_QUERY_MAP.get(key)
            if not query_tool:
                continue

            try:
                result = self.tool_registry.execute_by_name(query_tool, {})
                if result.get("success"):
                    state[key] = result.get("value")
                else:
                    logger.warning(f"State query {query_tool} failed: {result.get('error')}")
            except Exception as e:
                logger.warning(f"Exception querying {query_tool}: {e}")

        return state

    def _values_match(self, key: str, expected: Any, actual: Any) -> bool:
        """Check if expected and actual values match."""
        # Handle special "any" marker (just check non-empty)
        if expected == "any":
            if key == "selected_tracks":
                return isinstance(actual, list) and len(actual) > 0
            return actual is not None

        # Handle boolean values
        if isinstance(expected, bool):
            return actual == expected

        # Handle numeric values with tolerance
        if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
            return abs(expected - actual) < 0.01  # 10ms tolerance

        # Handle list values
        if isinstance(expected, list):
            if not isinstance(actual, list):
                return False
            return set(expected) == set(actual)

        # Default comparison
        return expected == actual

    def get_state_snapshot(self) -> Dict[str, Any]:
        """Get a full state snapshot."""
        keys = list(self.STATE_QUERY_MAP.keys())
        return self._query_state_keys(keys)


def verify_tool_execution(
    tool_name: str,
    expected_state: Dict[str, Any],
    tool_registry=None
) -> VerificationResult:
    """
    Convenience function for state verification.

    Args:
        tool_name: Tool that was executed
        expected_state: Expected state after execution
        tool_registry: Optional tool registry for state queries

    Returns:
        VerificationResult with success status
    """
    verifier = StateVerifier(tool_registry)
    return verifier.verify_state_change(
        tool_name=tool_name,
        expected_state=expected_state,
        pre_execution_state={}
    )
