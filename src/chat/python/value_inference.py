#!/usr/bin/env python3
"""
Value Inference Engine

Infers missing parameter and state values from:
1. User message (parsed time references, keywords)
2. Current state (cursor position, existing selection)
3. Reasonable defaults
"""

import re
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from state_contracts import StateKey
from state_gap_analyzer import StateGap


@dataclass
class InferredValue:
    """A value inferred for a state key or parameter."""
    key: str  # State key or parameter name
    value: Any
    source: str  # Where this value came from (user_message, current_state, default)
    confidence: float  # 0.0 to 1.0


@dataclass
class InferenceResult:
    """Result of value inference."""
    inferred_values: Dict[str, InferredValue]
    unresolved: List[str]  # Keys we couldn't infer values for
    needs_user_clarification: bool
    clarification_message: Optional[str]


class ValueInferenceEngine:
    """Infers missing values from context."""

    def __init__(self, location_parser=None):
        """
        Args:
            location_parser: LocationParser instance for parsing time references (optional)
        """
        self.location_parser = location_parser

    def infer_values(
        self,
        gaps: List[StateGap],
        missing_parameters: List[str],
        user_message: str,
        current_state: Dict[str, Any],
        tool_name: str
    ) -> InferenceResult:
        """
        Infer values for gaps and missing parameters.

        Args:
            gaps: State gaps from gap analyzer
            missing_parameters: Missing tool parameters
            user_message: Original user request
            current_state: Current state snapshot
            tool_name: Target tool name

        Returns:
            InferenceResult with inferred values
        """
        inferred = {}
        unresolved = []

        # Parse time references from user message
        parsed_times = self._parse_time_references(user_message, current_state)

        # Infer missing parameters first
        for param in missing_parameters:
            value = self._infer_parameter(
                param, tool_name, parsed_times, current_state, user_message
            )
            if value is not None:
                inferred[param] = value
            else:
                unresolved.append(f"parameter:{param}")

        # Infer state gap values
        for gap in gaps:
            if not gap.needs_value:
                continue

            value = self._infer_state_value(
                gap.state_key, parsed_times, current_state, user_message, tool_name
            )
            if value is not None:
                inferred[gap.state_key.value] = value
            elif gap.required:
                unresolved.append(f"state:{gap.state_key.value}")

        # Determine if we need user clarification
        needs_clarification = len(unresolved) > 0
        clarification_msg = None
        if needs_clarification:
            clarification_msg = self._build_clarification_message(unresolved, tool_name)

        return InferenceResult(
            inferred_values=inferred,
            unresolved=unresolved,
            needs_user_clarification=needs_clarification,
            clarification_message=clarification_msg
        )

    def _parse_time_references(
        self,
        user_message: str,
        current_state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Parse time references from user message.

        Returns dict with:
        - start_time: parsed start time (if found)
        - end_time: parsed end time (if found)
        - point_time: single time point (if found)
        - is_relative: whether times are relative (e.g., "last 30 seconds")
        """
        result = {
            "start_time": None,
            "end_time": None,
            "point_time": None,
            "is_relative": False
        }

        msg_lower = user_message.lower()

        # Check for MM:SS format first (more specific)
        mmss_pattern = r'(\d+):(\d{2})(?:\s*(?:to|-)\s*(\d+):(\d{2}))?'
        mmss_match = re.search(mmss_pattern, user_message)
        if mmss_match:
            minutes1 = int(mmss_match.group(1))
            seconds1 = int(mmss_match.group(2))
            time1 = minutes1 * 60 + seconds1

            if mmss_match.group(3) and mmss_match.group(4):
                # Range: MM:SS to MM:SS
                minutes2 = int(mmss_match.group(3))
                seconds2 = int(mmss_match.group(4))
                time2 = minutes2 * 60 + seconds2
                result["start_time"] = float(time1)
                result["end_time"] = float(time2)
                return result
            else:
                result["point_time"] = float(time1)
                return result

        # Check for "at X seconds" pattern (point time)
        at_pattern = r'at\s+(\d+(?:\.\d+)?)\s*(?:s|sec|seconds?)?'
        at_match = re.search(at_pattern, msg_lower)
        if at_match:
            result["point_time"] = float(at_match.group(1))
            return result

        # Check for "first X seconds" pattern
        first_pattern = r'first\s+(\d+(?:\.\d+)?)\s*(?:s|sec|seconds?)?'
        first_match = re.search(first_pattern, msg_lower)
        if first_match:
            result["start_time"] = 0.0
            result["end_time"] = float(first_match.group(1))
            return result

        # Check for "last X seconds" pattern
        last_pattern = r'last\s+(\d+(?:\.\d+)?)\s*(?:s|sec|seconds?)?'
        last_match = re.search(last_pattern, msg_lower)
        if last_match:
            duration = float(last_match.group(1))
            total_time = current_state.get("total_project_time", 0)
            if total_time > 0:
                result["start_time"] = max(0, total_time - duration)
                result["end_time"] = total_time
                result["is_relative"] = True
            return result

        # Check for "from X to Y" pattern
        range_pattern = r'from\s+(\d+(?:\.\d+)?)\s*(?:s|sec|seconds?)?\s*to\s+(\d+(?:\.\d+)?)\s*(?:s|sec|seconds?)?'
        range_match = re.search(range_pattern, msg_lower)
        if range_match:
            result["start_time"] = float(range_match.group(1))
            result["end_time"] = float(range_match.group(2))
            return result

        # Check for "X to Y seconds" pattern
        range_pattern2 = r'(\d+(?:\.\d+)?)\s*(?:s|sec|seconds?)?\s*(?:to|-)\s*(\d+(?:\.\d+)?)\s*(?:s|sec|seconds?)?'
        range_match2 = re.search(range_pattern2, msg_lower)
        if range_match2:
            result["start_time"] = float(range_match2.group(1))
            result["end_time"] = float(range_match2.group(2))
            return result

        # Check for standalone "X seconds" or "Xs" (point time)
        seconds_pattern = r'(\d+(?:\.\d+)?)\s*(?:s|sec|seconds?)\b'
        seconds_match = re.search(seconds_pattern, msg_lower)
        if seconds_match:
            result["point_time"] = float(seconds_match.group(1))

        return result

    def _infer_parameter(
        self,
        param_name: str,
        tool_name: str,
        parsed_times: Dict[str, Any],
        current_state: Dict[str, Any],
        user_message: str
    ) -> Optional[InferredValue]:
        """Infer a missing parameter value."""

        # Time parameter for split_at_time, seek, etc.
        if param_name == "time":
            # Priority 1: Explicit time from user message
            if parsed_times.get("point_time") is not None:
                return InferredValue(
                    key=param_name,
                    value=parsed_times["point_time"],
                    source="user_message",
                    confidence=1.0
                )

            # Priority 2: Cursor position (for "split here", "split at cursor")
            cursor_keywords = ["here", "cursor", "playhead", "current position", "current"]
            if any(kw in user_message.lower() for kw in cursor_keywords):
                cursor = current_state.get("cursor_position")
                if cursor is not None:
                    return InferredValue(
                        key=param_name,
                        value=cursor,
                        source="current_state:cursor_position",
                        confidence=0.9
                    )

            # Priority 3: Fallback to cursor if no other time reference
            if tool_name in ("split_at_time", "seek"):
                cursor = current_state.get("cursor_position")
                if cursor is not None:
                    return InferredValue(
                        key=param_name,
                        value=cursor,
                        source="fallback:cursor_position",
                        confidence=0.5
                    )

        # start_time / end_time for set_time_selection
        if param_name == "start_time":
            if parsed_times.get("start_time") is not None:
                return InferredValue(
                    key=param_name,
                    value=parsed_times["start_time"],
                    source="user_message",
                    confidence=1.0
                )

        if param_name == "end_time":
            if parsed_times.get("end_time") is not None:
                return InferredValue(
                    key=param_name,
                    value=parsed_times["end_time"],
                    source="user_message",
                    confidence=1.0
                )

        return None

    def _infer_state_value(
        self,
        state_key: StateKey,
        parsed_times: Dict[str, Any],
        current_state: Dict[str, Any],
        user_message: str,
        tool_name: str
    ) -> Optional[InferredValue]:
        """Infer a missing state value."""

        # Time selection inference
        if state_key == StateKey.HAS_TIME_SELECTION:
            # If we have start and end times, we can set selection
            if parsed_times.get("start_time") is not None and parsed_times.get("end_time") is not None:
                return InferredValue(
                    key=state_key.value,
                    value=True,
                    source="will_be_set",
                    confidence=1.0
                )

        if state_key == StateKey.SELECTION_START_TIME:
            if parsed_times.get("start_time") is not None:
                return InferredValue(
                    key=state_key.value,
                    value=parsed_times["start_time"],
                    source="user_message",
                    confidence=1.0
                )

        if state_key == StateKey.SELECTION_END_TIME:
            if parsed_times.get("end_time") is not None:
                return InferredValue(
                    key=state_key.value,
                    value=parsed_times["end_time"],
                    source="user_message",
                    confidence=1.0
                )

        # Track selection inference
        if state_key == StateKey.SELECTED_TRACKS:
            # Check if user mentioned "all tracks"
            all_keywords = ["all tracks", "every track", "all audio", "entire project", "all"]
            if any(kw in user_message.lower() for kw in all_keywords):
                return InferredValue(
                    key=state_key.value,
                    value="all",  # Signal to select all
                    source="user_message",
                    confidence=1.0
                )

            # Default: use all tracks (reasonable default for most audio editing operations)
            # This is a common pattern - when user says "cut from 1:00 to 2:00" without
            # specifying tracks, they expect it to operate on all tracks.
            # This matches behavior of most audio editors.
            return InferredValue(
                key=state_key.value,
                value="all",  # Will select all tracks
                source="default:all_tracks",
                confidence=0.8
            )

        # Cursor position inference
        if state_key == StateKey.CURSOR_POSITION:
            cursor = current_state.get("cursor_position")
            if cursor is not None:
                return InferredValue(
                    key=state_key.value,
                    value=cursor,
                    source="current_state",
                    confidence=1.0
                )

        return None

    def _build_clarification_message(
        self,
        unresolved: List[str],
        tool_name: str
    ) -> str:
        """Build a user-friendly clarification request."""

        messages = []

        for item in unresolved:
            if item == "parameter:time":
                messages.append("What time should I use? (e.g., '20 seconds', '1:30')")
            elif item == "state:has_time_selection":
                messages.append("What time range should I select? (e.g., 'from 0 to 30 seconds', 'first 10 seconds')")
            elif item == "state:selection_start_time":
                messages.append("What's the start time? (e.g., '0 seconds', '1:00')")
            elif item == "state:selection_end_time":
                messages.append("What's the end time? (e.g., '30 seconds', '2:00')")
            elif item == "state:selected_tracks":
                messages.append("Which tracks should I operate on? (e.g., 'all tracks', 'track 1')")
            elif item == "state:cursor_position":
                messages.append("Where should I position the cursor?")
            elif item.startswith("parameter:"):
                param = item.replace("parameter:", "")
                messages.append(f"What value should I use for {param}?")
            elif item.startswith("state:"):
                state = item.replace("state:", "")
                messages.append(f"I need {state.replace('_', ' ')} to be set first.")

        tool_display = tool_name.replace("_", " ")
        if messages:
            return f"To {tool_display}, I need more information:\n- " + "\n- ".join(messages)

        return f"I need more information to execute {tool_display}."


def infer_missing_values(
    gaps: List[StateGap],
    missing_parameters: List[str],
    user_message: str,
    current_state: Dict[str, Any],
    tool_name: str
) -> InferenceResult:
    """
    Convenience function for value inference.

    Args:
        gaps: State gaps from gap analyzer
        missing_parameters: Missing tool parameters
        user_message: Original user request
        current_state: Current state snapshot
        tool_name: Target tool name

    Returns:
        InferenceResult with inferred values
    """
    engine = ValueInferenceEngine()
    return engine.infer_values(
        gaps=gaps,
        missing_parameters=missing_parameters,
        user_message=user_message,
        current_state=current_state,
        tool_name=tool_name
    )
