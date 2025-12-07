# State Preparation Architecture - Implementation Plan

## Overview

Refactor the chat agent's tool calling architecture to properly handle the C++ backend's stateful design. The core change is implementing a **State Preparation Loop** that ensures all backend state requirements are met before executing operation tools.

## Current State Analysis

### Problem
The current architecture tries to make the LLM "smart" about prerequisites through verbose prompts and manual prerequisite mappings, but:
1. `TOOL_PREREQUISITES` in `tool_schemas.py` is hand-written and drifts from C++ ground truth
2. The LLM gets confused about when to query state vs call tools
3. There's no mechanism to infer missing values from user intent
4. No iterative verification that state changes succeeded

### C++ Backend Reality
All operation tools read state from `selectionController()` and `playbackState()` at execution time:
- `cut/delete/copy` → reads `timeSelectionIsNotEmpty()`, `selectedTracks()`, `dataSelectedStartTime/EndTime()`
- `trim_to_selection` → reads `selectedTracks()`, `dataSelectedStartTime/EndTime()`
- `split_at_time(t)` → reads `orderedTrackList()` (all tracks), accepts `time` parameter
- `paste` → reads `playbackPosition()` (cursor)
- Effects → read `timeSelectionIsNotEmpty()`, selection times

## Desired End State

A new architecture where:
1. **Ground truth state contracts** are derived from C++ and maintained as authoritative source
2. **State Preparation Loop** iteratively ensures all prerequisites are satisfied before tool execution
3. **Value inference** determines missing parameter values from user intent and current state
4. **Simplified prompts** - LLM only needs to identify user intent, not manage prerequisites

### Architecture Flow

```
User Request
    ↓
┌─────────────────────────────────────────────────┐
│              STATE PREPARATION LOOP              │
│                                                  │
│   State Discovery ◄───────────────┐             │
│        ↓                          │             │
│   Intent Planning                 │             │
│        ↓                          │             │
│   State Gap Analysis              │             │
│        ↓                          │             │
│   ┌─────────────────┐             │             │
│   │ Gap Exists?     │─── No ──────┼──► EXIT    │
│   └────────┬────────┘             │     LOOP    │
│            │ Yes                  │             │
│            ▼                      │             │
│   Value Inference                 │             │
│        ↓                          │             │
│   Execute State-Setting Tool      │             │
│            │                      │             │
│            ▼                      │             │
│   Verify State Change ────────────┘             │
│   (loop back to discovery)                      │
│                                                  │
└─────────────────────────────────────────────────┘
    ↓
Execute Operation Tool
    ↓
Response
```

## What We're NOT Doing

- NOT changing the C++ backend
- NOT changing the Python-C++ bridge protocol
- NOT adding new C++ actions
- NOT modifying QML UI components
- NOT changing how tools communicate with C++ (execute_tool/execute_state_query patterns stay)

---

## Phase 1: Extract Ground Truth State Contracts from C++

### Overview
Analyze C++ backend to create authoritative documentation of what state each action reads at execution time.

### Changes Required

#### 1.1 Create State Contracts Documentation

**File**: `src/chat/python/state_contracts.py` (new file)

**Purpose**: Single source of truth for tool state requirements, derived from C++ analysis.

```python
"""
State Contracts - Ground Truth from C++ Backend

Each tool's state contract defines:
- state_reads: What state the C++ backend reads at execution time
- parameters: What parameters the tool accepts
- state_writes: What state changes after successful execution (for verification)

Derived from: src/trackedit/internal/trackeditactionscontroller.cpp
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum


class StateKey(Enum):
    """Available state keys that can be read/written."""
    HAS_TIME_SELECTION = "has_time_selection"
    SELECTION_START_TIME = "selection_start_time"
    SELECTION_END_TIME = "selection_end_time"
    CURSOR_POSITION = "cursor_position"
    SELECTED_TRACKS = "selected_tracks"
    SELECTED_CLIPS = "selected_clips"
    TRACK_LIST = "track_list"
    TOTAL_PROJECT_TIME = "total_project_time"
    PROJECT_OPEN = "project_open"


@dataclass
class StateRequirement:
    """A single state requirement for a tool."""
    key: StateKey
    required: bool  # True = must exist, False = optional/fallback available
    fallback_from: Optional[StateKey] = None  # Alternative state to use if this is missing
    description: str = ""


@dataclass
class ToolStateContract:
    """Complete state contract for a tool."""
    tool_name: str
    state_reads: List[StateRequirement]  # State read by C++ at execution
    parameters: Dict[str, str]  # Parameter name -> description
    state_writes: List[StateKey]  # State modified after execution (for verification)
    cpp_reference: str  # File:line reference to C++ implementation


# Ground truth contracts derived from trackeditactionscontroller.cpp
TOOL_STATE_CONTRACTS: Dict[str, ToolStateContract] = {

    # === Clip Operations ===

    "split_at_time": ToolStateContract(
        tool_name="split_at_time",
        state_reads=[
            # C++ reads orderedTrackList() - operates on ALL tracks
            # No selection requirements
        ],
        parameters={
            "time": "Time in seconds where to split (required)"
        },
        state_writes=[StateKey.SELECTED_CLIPS],  # Selects leftmost clip after split
        cpp_reference="trackeditactionscontroller.cpp:1716-1735"
    ),

    "split": ToolStateContract(
        tool_name="split",
        state_reads=[
            StateRequirement(
                key=StateKey.HAS_TIME_SELECTION,
                required=False,
                description="If true, splits at selection start AND end"
            ),
            StateRequirement(
                key=StateKey.SELECTION_START_TIME,
                required=False,
                description="Used if has_time_selection is true"
            ),
            StateRequirement(
                key=StateKey.SELECTION_END_TIME,
                required=False,
                description="Used if has_time_selection is true"
            ),
            StateRequirement(
                key=StateKey.CURSOR_POSITION,
                required=False,
                fallback_from=StateKey.HAS_TIME_SELECTION,
                description="Used if no time selection exists"
            ),
            StateRequirement(
                key=StateKey.SELECTED_TRACKS,
                required=True,
                description="Operates on selected tracks from UI"
            ),
        ],
        parameters={},
        state_writes=[StateKey.SELECTED_CLIPS],
        cpp_reference="trackeditactionscontroller.cpp:669-703"
    ),

    # === Editing Operations ===

    "cut": ToolStateContract(
        tool_name="cut",
        state_reads=[
            StateRequirement(
                key=StateKey.HAS_TIME_SELECTION,
                required=True,
                description="Must have time selection to cut"
            ),
            StateRequirement(
                key=StateKey.SELECTION_START_TIME,
                required=True,
                description="Start of region to cut"
            ),
            StateRequirement(
                key=StateKey.SELECTION_END_TIME,
                required=True,
                description="End of region to cut"
            ),
            StateRequirement(
                key=StateKey.SELECTED_TRACKS,
                required=True,
                description="Operates on selected tracks"
            ),
        ],
        parameters={},
        state_writes=[StateKey.HAS_TIME_SELECTION],  # Clears selection after cut
        cpp_reference="trackeditactionscontroller.cpp:363-403"
    ),

    "delete_selection": ToolStateContract(
        tool_name="delete_selection",
        state_reads=[
            StateRequirement(
                key=StateKey.HAS_TIME_SELECTION,
                required=True,
                description="Must have time selection to delete"
            ),
            StateRequirement(
                key=StateKey.SELECTION_START_TIME,
                required=True,
                description="Start of region to delete"
            ),
            StateRequirement(
                key=StateKey.SELECTION_END_TIME,
                required=True,
                description="End of region to delete"
            ),
            StateRequirement(
                key=StateKey.SELECTED_TRACKS,
                required=True,
                description="Operates on selected tracks"
            ),
        ],
        parameters={},
        state_writes=[StateKey.HAS_TIME_SELECTION],
        cpp_reference="trackeditactionscontroller.cpp:505-565"
    ),

    "copy": ToolStateContract(
        tool_name="copy",
        state_reads=[
            StateRequirement(
                key=StateKey.HAS_TIME_SELECTION,
                required=True,
                description="Must have time selection to copy"
            ),
            StateRequirement(
                key=StateKey.SELECTION_START_TIME,
                required=True,
                description="Start of region to copy"
            ),
            StateRequirement(
                key=StateKey.SELECTION_END_TIME,
                required=True,
                description="End of region to copy"
            ),
            StateRequirement(
                key=StateKey.SELECTED_TRACKS,
                required=True,
                description="Operates on selected tracks"
            ),
        ],
        parameters={},
        state_writes=[],  # Copy doesn't modify state
        cpp_reference="trackeditactionscontroller.cpp:345-361"
    ),

    "paste": ToolStateContract(
        tool_name="paste",
        state_reads=[
            StateRequirement(
                key=StateKey.CURSOR_POSITION,
                required=True,
                description="Paste location"
            ),
        ],
        parameters={},
        state_writes=[StateKey.SELECTED_CLIPS],
        cpp_reference="trackeditactionscontroller.cpp:1053-1104"
    ),

    "trim_to_selection": ToolStateContract(
        tool_name="trim_to_selection",
        state_reads=[
            StateRequirement(
                key=StateKey.HAS_TIME_SELECTION,
                required=True,
                description="Must have time selection to trim"
            ),
            StateRequirement(
                key=StateKey.SELECTION_START_TIME,
                required=True,
                description="Start of region to keep"
            ),
            StateRequirement(
                key=StateKey.SELECTION_END_TIME,
                required=True,
                description="End of region to keep"
            ),
            StateRequirement(
                key=StateKey.SELECTED_TRACKS,
                required=True,
                description="Operates on selected tracks only"
            ),
        ],
        parameters={},
        state_writes=[],
        cpp_reference="trackeditactionscontroller.cpp:1462-1492"
    ),

    # === Selection/State-Setting Tools ===

    "set_time_selection": ToolStateContract(
        tool_name="set_time_selection",
        state_reads=[],
        parameters={
            "start_time": "Start time in seconds",
            "end_time": "End time in seconds"
        },
        state_writes=[
            StateKey.HAS_TIME_SELECTION,
            StateKey.SELECTION_START_TIME,
            StateKey.SELECTION_END_TIME
        ],
        cpp_reference="trackeditactionscontroller.cpp:1603-1614"
    ),

    "select_all_tracks": ToolStateContract(
        tool_name="select_all_tracks",
        state_reads=[
            StateRequirement(
                key=StateKey.TRACK_LIST,
                required=True,
                description="Need tracks to select"
            ),
        ],
        parameters={},
        state_writes=[StateKey.SELECTED_TRACKS],
        cpp_reference="trackeditactionscontroller.cpp:select-all-tracks action"
    ),

    "seek": ToolStateContract(
        tool_name="seek",
        state_reads=[],
        parameters={
            "time": "Time in seconds to move cursor to"
        },
        state_writes=[StateKey.CURSOR_POSITION],
        cpp_reference="playbackactionscontroller.cpp:seek action"
    ),

    # === Effect Tools (all have same pattern) ===

    "apply_normalize": ToolStateContract(
        tool_name="apply_normalize",
        state_reads=[
            StateRequirement(
                key=StateKey.HAS_TIME_SELECTION,
                required=True,
                description="Must have time selection for effect"
            ),
            StateRequirement(
                key=StateKey.SELECTION_START_TIME,
                required=True,
                description="Effect applies from this time"
            ),
            StateRequirement(
                key=StateKey.SELECTION_END_TIME,
                required=True,
                description="Effect applies to this time"
            ),
            StateRequirement(
                key=StateKey.SELECTED_TRACKS,
                required=True,
                description="Effect applies to selected tracks"
            ),
        ],
        parameters={},
        state_writes=[],
        cpp_reference="Effects system"
    ),

    # Add more effect tools with same pattern...

    # === Playback Tools ===

    "play": ToolStateContract(
        tool_name="play",
        state_reads=[],
        parameters={},
        state_writes=[],
        cpp_reference="playbackactionscontroller.cpp:play action"
    ),

    "stop": ToolStateContract(
        tool_name="stop",
        state_reads=[],
        parameters={},
        state_writes=[],
        cpp_reference="playbackactionscontroller.cpp:stop action"
    ),
}


def get_contract(tool_name: str) -> Optional[ToolStateContract]:
    """Get state contract for a tool."""
    return TOOL_STATE_CONTRACTS.get(tool_name)


def get_required_state(tool_name: str) -> List[StateKey]:
    """Get list of required state keys for a tool."""
    contract = get_contract(tool_name)
    if not contract:
        return []
    return [req.key for req in contract.state_reads if req.required]


def get_state_setting_tool(state_key: StateKey) -> Optional[str]:
    """Get the tool that can set a given state key."""
    STATE_SETTERS = {
        StateKey.HAS_TIME_SELECTION: "set_time_selection",
        StateKey.SELECTION_START_TIME: "set_time_selection",
        StateKey.SELECTION_END_TIME: "set_time_selection",
        StateKey.CURSOR_POSITION: "seek",
        StateKey.SELECTED_TRACKS: "select_all_tracks",
        StateKey.SELECTED_CLIPS: "select_all",  # Or specific clip selection
    }
    return STATE_SETTERS.get(state_key)
```

### Success Criteria

#### Automated Verification:
- [x] `state_contracts.py` imports without errors
- [x] All tools in `tools.py` have corresponding contracts
- [x] Unit tests verify contract structure

#### Manual Verification:
- [x] Spot-check 5 contracts against actual C++ code
- [x] Verify `split_at_time` contract matches `trackeditactionscontroller.cpp:1716-1735`
- [x] Verify `cut` contract matches `trackeditactionscontroller.cpp:363-403`

---

## Phase 2: Implement State Gap Analyzer

### Overview
Create a component that compares current state against tool requirements and identifies gaps.

### Changes Required

#### 2.1 State Gap Analyzer

**File**: `src/chat/python/state_gap_analyzer.py` (new file)

```python
"""
State Gap Analyzer

Compares current state against tool state contracts to identify:
1. What state is missing
2. What state-setting tools are needed
3. What values need to be inferred
"""

from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from state_contracts import (
    get_contract,
    get_required_state,
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
                fallback_value = None
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
        key_map = {
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
        return state.get(key_map.get(key, key.value))

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
        return value is not None
```

### Success Criteria

#### Automated Verification:
- [x] Unit tests for `StateGapAnalyzer.analyze()`
- [x] Test: `cut` with no selection returns gap for `HAS_TIME_SELECTION`
- [x] Test: `split_at_time` with time param returns no gaps
- [x] Test: `trim_to_selection` with selection returns `can_execute=True`

#### Manual Verification:
- [x] Verify gap analysis matches expected behavior for 5 common operations

---

## Phase 3: Implement Value Inference Engine

### Overview
Create a component that infers missing values from user intent and current state.

### Changes Required

#### 3.1 Value Inference Engine

**File**: `src/chat/python/value_inference.py` (new file)

```python
"""
Value Inference Engine

Infers missing parameter and state values from:
1. User message (parsed time references, keywords)
2. Current state (cursor position, existing selection)
3. Reasonable defaults
"""

from typing import Dict, Any, List, Optional, Tuple
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
            location_parser: LocationParser instance for parsing time references
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

        # Check for "at X seconds" pattern (point time)
        import re
        at_pattern = r'at\s+(\d+(?:\.\d+)?)\s*(?:s|sec|seconds?)?'
        at_match = re.search(at_pattern, msg_lower)
        if at_match:
            result["point_time"] = float(at_match.group(1))
            return result

        # Check for "X seconds" standalone
        seconds_pattern = r'(\d+(?:\.\d+)?)\s*(?:s|sec|seconds?)\b'
        seconds_match = re.search(seconds_pattern, msg_lower)
        if seconds_match:
            result["point_time"] = float(seconds_match.group(1))

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

        # Check for "X to Y" pattern
        range_pattern2 = r'(\d+(?:\.\d+)?)\s*(?:s|sec|seconds?)?\s*(?:to|-)\s*(\d+(?:\.\d+)?)\s*(?:s|sec|seconds?)?'
        range_match2 = re.search(range_pattern2, msg_lower)
        if range_match2:
            result["start_time"] = float(range_match2.group(1))
            result["end_time"] = float(range_match2.group(2))
            return result

        # Check for MM:SS format
        mmss_pattern = r'(\d+):(\d{2})'
        mmss_match = re.search(mmss_pattern, user_message)
        if mmss_match:
            minutes = int(mmss_match.group(1))
            seconds = int(mmss_match.group(2))
            result["point_time"] = minutes * 60 + seconds

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
            cursor_keywords = ["here", "cursor", "playhead", "current position"]
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
            all_keywords = ["all tracks", "every track", "all"]
            if any(kw in user_message.lower() for kw in all_keywords):
                return InferredValue(
                    key=state_key.value,
                    value="all",  # Signal to select all
                    source="user_message",
                    confidence=1.0
                )

            # Default: use all tracks if none selected (reasonable default)
            track_list = current_state.get("track_list", [])
            if track_list:
                return InferredValue(
                    key=state_key.value,
                    value="all",  # Will select all tracks
                    source="default:all_tracks",
                    confidence=0.6
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
            elif item == "state:selected_tracks":
                messages.append("Which tracks should I operate on? (e.g., 'all tracks', 'track 1')")
            elif item.startswith("parameter:"):
                param = item.replace("parameter:", "")
                messages.append(f"What value should I use for {param}?")
            elif item.startswith("state:"):
                state = item.replace("state:", "")
                messages.append(f"I need {state} to be set first.")

        if messages:
            return f"To {tool_name.replace('_', ' ')}, I need more information: " + " ".join(messages)

        return f"I need more information to execute {tool_name}."
```

### Success Criteria

#### Automated Verification:
- [x] Unit tests for time parsing patterns
- [x] Test: "split at 20s" → infers time=20.0
- [x] Test: "trim first 30 seconds" → infers start=0, end=30
- [x] Test: "split" with cursor at 15.0 → infers time=15.0

#### Manual Verification:
- [x] Test 10 common user phrases and verify inferred values

---

## Phase 4: Implement State Preparation Loop

### Overview
Create the main orchestration component that implements the iterative state preparation loop.

### Changes Required

#### 4.1 State Preparation Orchestrator

**File**: `src/chat/python/state_preparation.py` (new file)

```python
"""
State Preparation Orchestrator

Implements the iterative state preparation loop:
1. Discover current state
2. Analyze gaps for target tool
3. Infer missing values
4. Execute state-setting tools
5. Verify state changes
6. Repeat until ready or max iterations

Only when all prerequisites are satisfied does execution proceed.
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass

from state_contracts import get_contract, StateKey, get_state_setting_tool
from state_gap_analyzer import StateGapAnalyzer, GapAnalysisResult
from value_inference import ValueInferenceEngine, InferenceResult

logger = logging.getLogger(__name__)


@dataclass
class PreparationStep:
    """A single state preparation step."""
    tool_name: str
    arguments: Dict[str, Any]
    purpose: str  # Human-readable description


@dataclass
class PreparationResult:
    """Result of state preparation."""
    ready_to_execute: bool
    preparation_steps: List[PreparationStep]  # Tools to run before operation
    operation_tool: str
    operation_arguments: Dict[str, Any]
    error: Optional[str]
    needs_clarification: bool
    clarification_message: Optional[str]


class StatePreparationOrchestrator:
    """
    Orchestrates the state preparation loop.
    """

    MAX_ITERATIONS = 5  # Prevent infinite loops

    def __init__(self, tool_registry):
        """
        Args:
            tool_registry: ToolRegistry instance for executing state queries
        """
        self.tool_registry = tool_registry
        self.gap_analyzer = StateGapAnalyzer()
        self.value_inference = ValueInferenceEngine()

    def prepare(
        self,
        tool_name: str,
        tool_arguments: Dict[str, Any],
        user_message: str,
        initial_state: Dict[str, Any]
    ) -> PreparationResult:
        """
        Prepare state for tool execution.

        Args:
            tool_name: Target operation tool
            tool_arguments: Arguments provided by LLM
            user_message: Original user request
            initial_state: Initial state snapshot

        Returns:
            PreparationResult with preparation steps or error
        """
        current_state = initial_state.copy()
        preparation_steps = []
        iteration = 0

        while iteration < self.MAX_ITERATIONS:
            iteration += 1
            logger.info(f"State preparation iteration {iteration} for {tool_name}")

            # Step 1: Analyze gaps
            gap_result = self.gap_analyzer.analyze(
                tool_name,
                tool_arguments,
                current_state
            )

            logger.debug(f"Gap analysis: can_execute={gap_result.can_execute}, "
                        f"gaps={len(gap_result.gaps)}, "
                        f"missing_params={gap_result.missing_parameters}")

            # Step 2: Check if ready
            if gap_result.can_execute and not gap_result.missing_parameters:
                logger.info(f"State preparation complete after {iteration} iteration(s)")
                return PreparationResult(
                    ready_to_execute=True,
                    preparation_steps=preparation_steps,
                    operation_tool=tool_name,
                    operation_arguments=tool_arguments,
                    error=None,
                    needs_clarification=False,
                    clarification_message=None
                )

            # Step 3: Infer missing values
            inference_result = self.value_inference.infer_values(
                gaps=gap_result.gaps,
                missing_parameters=gap_result.missing_parameters,
                user_message=user_message,
                current_state=current_state,
                tool_name=tool_name
            )

            # Step 4: Check if we need user clarification
            if inference_result.needs_user_clarification:
                return PreparationResult(
                    ready_to_execute=False,
                    preparation_steps=preparation_steps,
                    operation_tool=tool_name,
                    operation_arguments=tool_arguments,
                    error=None,
                    needs_clarification=True,
                    clarification_message=inference_result.clarification_message
                )

            # Step 5: Generate state-setting steps
            new_steps = self._generate_preparation_steps(
                gap_result,
                inference_result,
                tool_arguments
            )

            if not new_steps:
                # No more steps to take but still can't execute
                logger.error(f"Cannot prepare state for {tool_name}: no steps available")
                return PreparationResult(
                    ready_to_execute=False,
                    preparation_steps=preparation_steps,
                    operation_tool=tool_name,
                    operation_arguments=tool_arguments,
                    error=f"Cannot determine how to prepare state for {tool_name}",
                    needs_clarification=False,
                    clarification_message=None
                )

            # Step 6: Add steps and update simulated state
            for step in new_steps:
                preparation_steps.append(step)
                self._simulate_state_change(step, current_state, inference_result)

            # Update tool arguments with inferred parameter values
            for param in gap_result.missing_parameters:
                if param in inference_result.inferred_values:
                    tool_arguments[param] = inference_result.inferred_values[param].value

        # Max iterations reached
        logger.error(f"State preparation exceeded {self.MAX_ITERATIONS} iterations")
        return PreparationResult(
            ready_to_execute=False,
            preparation_steps=preparation_steps,
            operation_tool=tool_name,
            operation_arguments=tool_arguments,
            error=f"State preparation exceeded maximum iterations ({self.MAX_ITERATIONS})",
            needs_clarification=False,
            clarification_message=None
        )

    def _generate_preparation_steps(
        self,
        gap_result: GapAnalysisResult,
        inference_result: InferenceResult,
        tool_arguments: Dict[str, Any]
    ) -> List[PreparationStep]:
        """Generate state-setting tool calls to fill gaps."""
        steps = []

        # Group related gaps (e.g., start_time + end_time → single set_time_selection)
        needs_time_selection = False
        start_time = None
        end_time = None
        needs_track_selection = False
        needs_seek = False
        seek_time = None

        for gap in gap_result.gaps:
            if not gap.needs_value:
                continue

            inferred = inference_result.inferred_values.get(gap.state_key.value)

            if gap.state_key in (StateKey.HAS_TIME_SELECTION,
                                  StateKey.SELECTION_START_TIME,
                                  StateKey.SELECTION_END_TIME):
                needs_time_selection = True
                if gap.state_key == StateKey.SELECTION_START_TIME and inferred:
                    start_time = inferred.value
                elif gap.state_key == StateKey.SELECTION_END_TIME and inferred:
                    end_time = inferred.value
                # Also check inference result directly
                if "selection_start_time" in inference_result.inferred_values:
                    start_time = inference_result.inferred_values["selection_start_time"].value
                if "selection_end_time" in inference_result.inferred_values:
                    end_time = inference_result.inferred_values["selection_end_time"].value

            elif gap.state_key == StateKey.SELECTED_TRACKS:
                needs_track_selection = True

            elif gap.state_key == StateKey.CURSOR_POSITION:
                needs_seek = True
                if inferred:
                    seek_time = inferred.value

        # Generate consolidated steps
        if needs_time_selection and start_time is not None and end_time is not None:
            steps.append(PreparationStep(
                tool_name="set_time_selection",
                arguments={"start_time": start_time, "end_time": end_time},
                purpose=f"Set selection from {start_time}s to {end_time}s"
            ))

        if needs_track_selection:
            steps.append(PreparationStep(
                tool_name="select_all_tracks",
                arguments={},
                purpose="Select all tracks"
            ))

        if needs_seek and seek_time is not None:
            steps.append(PreparationStep(
                tool_name="seek",
                arguments={"time": seek_time},
                purpose=f"Move cursor to {seek_time}s"
            ))

        return steps

    def _simulate_state_change(
        self,
        step: PreparationStep,
        state: Dict[str, Any],
        inference_result: InferenceResult
    ):
        """
        Simulate state change after a preparation step.
        This optimistically updates state for the next iteration.
        """
        if step.tool_name == "set_time_selection":
            state["has_time_selection"] = True
            state["selection_start_time"] = step.arguments.get("start_time")
            state["selection_end_time"] = step.arguments.get("end_time")

        elif step.tool_name == "select_all_tracks":
            # Mark as having track selection
            state["selected_tracks"] = state.get("track_list", ["*"])

        elif step.tool_name == "seek":
            state["cursor_position"] = step.arguments.get("time")
```

#### 4.2 Integrate with Planning Orchestrator

**File**: `src/chat/python/planning_orchestrator.py`

**Changes**: Replace current prerequisite resolution with State Preparation Orchestrator.

```python
# In process_request(), after Intent Planning phase:

# Phase 3: State Preparation (NEW - replaces prerequisite resolution)
logger.info("Phase 3: State Preparation")
if not planning_state.transition_to(PlanningPhase.STATE_PREPARATION):
    error_msg = "Failed to transition to state preparation"
    logger.error(error_msg)
    return self._error_response(error_msg)

state_prep = StatePreparationOrchestrator(self.tool_registry)
final_plan = []

for tool_call in planning_state.execution_plan:
    tool_name = tool_call.get("tool_name")
    tool_args = tool_call.get("arguments", {})

    # Prepare state for this tool
    prep_result = state_prep.prepare(
        tool_name=tool_name,
        tool_arguments=tool_args,
        user_message=user_message,
        initial_state=planning_state.discovered_state
    )

    if prep_result.needs_clarification:
        return {
            "type": "clarification_needed",
            "content": prep_result.clarification_message,
            "can_undo": False
        }

    if prep_result.error:
        return self._error_response(prep_result.error)

    # Add preparation steps to plan
    for step in prep_result.preparation_steps:
        final_plan.append({
            "tool_name": step.tool_name,
            "arguments": step.arguments
        })

    # Add the operation tool
    final_plan.append({
        "tool_name": prep_result.operation_tool,
        "arguments": prep_result.operation_arguments
    })

planning_state.set_execution_plan(final_plan)
# Continue to execution phase...
```

### Success Criteria

#### Automated Verification:
- [x] Unit tests for StatePreparationOrchestrator
- [x] Test: "split at 20s" → returns ready_to_execute=True with no prep steps
- [x] Test: "trim first 30 seconds" → returns prep steps [set_time_selection, select_all_tracks]
- [x] Test: "cut" with no selection → returns needs_clarification=True
- [x] Integration test: Full flow from user message to prepared plan

#### Manual Verification:
- [ ] "split at 20s" executes correctly
- [ ] "trim first 30 seconds" executes correctly
- [ ] "delete from 10 to 20 seconds" executes correctly
- [ ] "split" with no context asks for clarification

---

## Phase 5: Simplify LLM Prompts and Tool Schemas

### Overview
Simplify the system prompt and tool descriptions now that state preparation is handled systematically.

### Changes Required

#### 5.1 Simplified Tool Schemas

**File**: `src/chat/python/tool_schemas.py`

**Changes**: Remove prerequisite documentation from tool descriptions - the State Preparation system handles it.

```python
# BEFORE (verbose, error-prone):
{
    "name": "trim_to_selection",
    "description": "Remove all audio outside the current selection, keeping only the selected portion. Prerequisites: Requires a time selection. Use set_time_selection() first, or check has_time_selection() to verify. This tool operates on currently selected tracks only. If no tracks are selected, it will operate on nothing. If you want to trim all tracks, select all tracks first with select_all_tracks(). Example: set_time_selection(start_time=2, end_time=5) then trim_to_selection(). If no selection exists, this tool will fail.",
    ...
}

# AFTER (simple, focused):
{
    "name": "trim_to_selection",
    "description": "Keep only the audio within a time range, removing everything outside it.",
    ...
}
```

#### 5.2 Simplified System Prompt

**File**: `src/chat/python/tool_schemas.py`

**Changes**: Remove prerequisite documentation, state query guidance, multi-step examples.

```python
FUNCTION_CALLING_SYSTEM_PROMPT = """You are an AI assistant that controls Audacity audio editor.

When the user asks you to perform audio editing tasks, identify the operation they want and call the appropriate tool.

## Your Role
- Identify what the user wants to do (trim, split, cut, delete, apply effect, etc.)
- Extract any time references from their message (e.g., "20 seconds", "first 30 seconds", "from 1:00 to 2:00")
- Call the operation tool with extracted parameters

## Time Parsing
- "20s", "20 seconds" → time: 20.0
- "1:30" → time: 90.0 (1 minute 30 seconds)
- "first 30 seconds" → start: 0, end: 30
- "last 30 seconds" → calculate from project duration
- "from 5 to 10 seconds" → start: 5, end: 10

## Examples
- "Split at 20 seconds" → split_at_time(time=20.0)
- "Trim the first 30 seconds" → trim_to_selection() (system will set selection)
- "Delete from 10 to 20 seconds" → delete_selection() (system will set selection)
- "Normalize the audio" → apply_normalize() (system will handle selection)

You do NOT need to:
- Call state query tools (get_selection_start_time, etc.)
- Call state-setting tools (set_time_selection, select_all_tracks)
- Worry about prerequisites

The system will automatically prepare the required state before executing your requested operation.

For greetings or general conversation, respond naturally without calling tools.
"""
```

#### 5.3 Remove TOOL_PREREQUISITES

**File**: `src/chat/python/tool_schemas.py`

**Changes**: Delete the `TOOL_PREREQUISITES` dictionary - it's replaced by `state_contracts.py`.

### Success Criteria

#### Automated Verification:
- [x] Tool schemas pass validation
- [x] System prompt is under 500 words (reduced from 6000+ to ~280 words)
- [x] No references to prerequisite handling in tool descriptions

#### Manual Verification:
- [ ] LLM correctly identifies intent from simple prompts
- [ ] LLM no longer generates state query tool calls
- [ ] Complex operations work end-to-end

---

## Phase 6: Implement Execution with Verification

### Overview
Add state verification after each tool execution to enable the feedback loop.

### Changes Required

#### 6.1 State Verification

**File**: `src/chat/python/state_verification.py` (new file)

```python
"""
State Verification

Verifies that state changes succeeded after tool execution.
Enables the feedback loop in state preparation.
"""

from typing import Dict, Any, List, Optional
from state_contracts import get_contract, StateKey


class StateVerifier:
    """Verifies state changes after tool execution."""

    def __init__(self, tool_registry):
        self.tool_registry = tool_registry

    def verify_state_change(
        self,
        tool_name: str,
        expected_state: Dict[str, Any],
        pre_execution_state: Dict[str, Any]
    ) -> tuple[bool, Dict[str, Any], Optional[str]]:
        """
        Verify state changed as expected after tool execution.

        Args:
            tool_name: Tool that was executed
            expected_state: Expected state values after execution
            pre_execution_state: State before execution

        Returns:
            Tuple of (success, actual_state, error_message)
        """
        # Query current state
        actual_state = self._query_current_state()

        contract = get_contract(tool_name)
        if not contract:
            return True, actual_state, None

        # Check expected state writes
        errors = []
        for state_key in contract.state_writes:
            expected = expected_state.get(state_key.value)
            actual = actual_state.get(state_key.value)

            if expected is not None and actual != expected:
                errors.append(f"{state_key.value}: expected {expected}, got {actual}")

        if errors:
            return False, actual_state, "; ".join(errors)

        return True, actual_state, None

    def _query_current_state(self) -> Dict[str, Any]:
        """Query all relevant state from backend."""
        state = {}

        queries = [
            ("has_time_selection", "has_time_selection"),
            ("get_selection_start_time", "selection_start_time"),
            ("get_selection_end_time", "selection_end_time"),
            ("get_cursor_position", "cursor_position"),
            ("get_selected_tracks", "selected_tracks"),
            ("get_selected_clips", "selected_clips"),
        ]

        for query_tool, state_key in queries:
            result = self.tool_registry.execute_by_name(query_tool, {})
            if result.get("success"):
                state[state_key] = result.get("value")

        return state
```

#### 6.2 Enhanced Execution Loop

**File**: `src/chat/python/planning_orchestrator.py`

**Changes**: Add verification step after each state-setting tool.

```python
# In execution phase, after each state-setting tool:

verifier = StateVerifier(self.tool_registry)

for tool_call in final_plan:
    tool_name = tool_call.get("tool_name")
    arguments = tool_call.get("arguments", {})

    # Execute tool
    result = self.tool_registry.execute_by_name(tool_name, arguments)

    if not result.get("success"):
        # Handle failure
        return self._error_response(f"Tool {tool_name} failed: {result.get('error')}")

    # For state-setting tools, verify the change
    if tool_name in STATE_SETTING_TOOLS:
        expected = self._calculate_expected_state(tool_name, arguments)
        success, actual, error = verifier.verify_state_change(
            tool_name, expected, planning_state.discovered_state
        )

        if not success:
            logger.warning(f"State verification failed for {tool_name}: {error}")
            # Update state with actual values and potentially retry
            planning_state.discovered_state.update(actual)
        else:
            # Update state with verified values
            planning_state.discovered_state.update(actual)
```

### Success Criteria

#### Automated Verification:
- [x] Unit tests for StateVerifier
- [x] Test: set_time_selection changes are verified
- [x] Test: Failed state change is detected

#### Manual Verification:
- [ ] State verification logs show correct behavior
- [ ] Failed state changes trigger appropriate error handling

---

## Phase 7: Cleanup and Documentation

### Overview
Remove deprecated code and document the new architecture.

### Changes Required

#### 7.1 Remove Deprecated Code

**Files to modify**:
- `src/chat/python/prerequisite_resolver.py` - Delete or mark as deprecated
- `src/chat/python/pre_execution_validator.py` - Delete or mark as deprecated
- `src/chat/python/tool_schemas.py` - Remove `TOOL_PREREQUISITES`

#### 7.2 Update Planning State

**File**: `src/chat/python/planning_state.py`

**Changes**: Add `STATE_PREPARATION` phase to enum.

```python
class PlanningPhase(Enum):
    INITIAL = "initial"
    STATE_DISCOVERY = "state_discovery"
    PLANNING = "planning"
    STATE_PREPARATION = "state_preparation"  # NEW
    EXECUTION = "execution"
    COMPLETE = "complete"
    ERROR = "error"
```

#### 7.3 Architecture Documentation

**File**: `src/chat/python/ARCHITECTURE.md` (new file)

Document the new state preparation architecture with diagrams and examples.

### Success Criteria

#### Automated Verification:
- [x] No import errors after removing deprecated code
- [x] All tests pass (98 tests)

#### Manual Verification:
- [ ] Architecture documentation is clear and accurate
- [ ] New developers can understand the flow

---

## Testing Strategy

### Unit Tests
- `test_state_contracts.py` - Contract structure and lookup
- `test_state_gap_analyzer.py` - Gap detection for various tools
- `test_value_inference.py` - Time parsing, value inference
- `test_state_preparation.py` - Preparation loop logic

### Integration Tests
- `test_state_preparation_integration.py` - Full flow from user message to prepared plan
- `test_end_to_end.py` - Complete execution including actual tool calls

### Manual Testing Steps
1. "split at 20 seconds" - Should execute directly
2. "trim the first 30 seconds" - Should set selection then trim
3. "delete from 1:00 to 2:00" - Should set selection then delete
4. "normalize" with existing selection - Should use existing selection
5. "normalize" without selection - Should ask for clarification
6. "split" with cursor at 15s - Should use cursor position
7. "cut the last 10 seconds" - Should calculate from project duration

---

## Migration Notes

### Backward Compatibility
- The new system should handle existing tool calls that include state-setting tools
- LLM-generated plans with explicit state queries should still work (just be redundant)

### Rollback Plan
- Keep `prerequisite_resolver.py` and `pre_execution_validator.py` but unused
- Feature flag in config to switch between old and new systems

---

## References

- C++ State Controllers: `src/trackedit/iselectioncontroller.h`, `src/context/iplaybackstate.h`
- C++ Action Implementation: `src/trackedit/internal/trackeditactionscontroller.cpp`
- Original issue: `.cursor/issue.md`
- Current Python tools: `src/chat/python/tools.py`, `src/chat/python/tool_schemas.py`
