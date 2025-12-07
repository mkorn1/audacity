#!/usr/bin/env python3
"""
State Contracts - Ground Truth from C++ Backend

Each tool's state contract defines:
- state_reads: What state the C++ backend reads at execution time
- parameters: What parameters the tool accepts
- state_writes: What state changes after successful execution (for verification)

Derived from: src/trackedit/internal/trackeditactionscontroller.cpp

This file is the SINGLE SOURCE OF TRUTH for tool state requirements.
The State Preparation system uses these contracts to determine what
state must be set before a tool can execute.
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
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
    state_reads: List[StateRequirement] = field(default_factory=list)
    parameters: Dict[str, str] = field(default_factory=dict)  # Parameter name -> description
    state_writes: List[StateKey] = field(default_factory=list)  # State modified after execution
    cpp_reference: str = ""  # File:line reference to C++ implementation


# Ground truth contracts derived from trackeditactionscontroller.cpp
# Verified against actual C++ implementation
TOOL_STATE_CONTRACTS: Dict[str, ToolStateContract] = {

    # === Clip Operations ===

    "split_at_time": ToolStateContract(
        tool_name="split_at_time",
        state_reads=[
            # C++ reads orderedTrackList() - operates on ALL tracks
            # No selection requirements - line 1724-1727
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
            # doGlobalSplit reads UI track selection (line 683-688)
            StateRequirement(
                key=StateKey.HAS_TIME_SELECTION,
                required=False,
                description="If true, splits at selection start AND end (line 695-697)"
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
                description="Used via playbackPosition() if no time selection (line 699)"
            ),
            # Note: Reads UI track selection directly, not selectionController()->selectedTracks()
        ],
        parameters={},
        state_writes=[StateKey.SELECTED_CLIPS],
        cpp_reference="trackeditactionscontroller.cpp:669-703"
    ),

    # === Editing Operations ===

    "cut": ToolStateContract(
        tool_name="cut",
        state_reads=[
            # doGlobalCut checks timeSelectionIsNotEmpty() first (line 405)
            StateRequirement(
                key=StateKey.HAS_TIME_SELECTION,
                required=True,
                description="Must have time selection to cut (line 405)"
            ),
            StateRequirement(
                key=StateKey.SELECTION_START_TIME,
                required=True,
                description="Start of region to cut (line 407)"
            ),
            StateRequirement(
                key=StateKey.SELECTION_END_TIME,
                required=True,
                description="End of region to cut (line 408)"
            ),
            StateRequirement(
                key=StateKey.SELECTED_TRACKS,
                required=True,
                description="Operates on selected tracks (line 406)"
            ),
        ],
        parameters={},
        state_writes=[StateKey.HAS_TIME_SELECTION],  # Clears selection after cut
        cpp_reference="trackeditactionscontroller.cpp:363-424"
    ),

    "delete_selection": ToolStateContract(
        tool_name="delete_selection",
        state_reads=[
            # doGlobalDelete checks timeSelectionIsNotEmpty() (line 547)
            StateRequirement(
                key=StateKey.HAS_TIME_SELECTION,
                required=True,
                description="Must have time selection to delete (line 547)"
            ),
            StateRequirement(
                key=StateKey.SELECTION_START_TIME,
                required=True,
                description="Start of region to delete (line 549)"
            ),
            StateRequirement(
                key=StateKey.SELECTION_END_TIME,
                required=True,
                description="End of region to delete (line 550)"
            ),
            StateRequirement(
                key=StateKey.SELECTED_TRACKS,
                required=True,
                description="Operates on selected tracks (line 548)"
            ),
        ],
        parameters={},
        state_writes=[StateKey.HAS_TIME_SELECTION],
        cpp_reference="trackeditactionscontroller.cpp:505-575"
    ),

    "copy": ToolStateContract(
        tool_name="copy",
        state_reads=[
            # doGlobalCopy checks timeSelectionIsNotEmpty() first (line 347)
            StateRequirement(
                key=StateKey.HAS_TIME_SELECTION,
                required=True,
                description="Must have time selection to copy (line 347)"
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
            # pasteOverlap/pasteInsert reads playbackPosition() (line 1076, 1092)
            StateRequirement(
                key=StateKey.CURSOR_POSITION,
                required=True,
                description="Paste location from playbackPosition() (line 1076)"
            ),
        ],
        parameters={},
        state_writes=[StateKey.SELECTED_CLIPS],
        cpp_reference="trackeditactionscontroller.cpp:1053-1112"
    ),

    "trim_to_selection": ToolStateContract(
        tool_name="trim_to_selection",
        state_reads=[
            # trimAudioOutsideSelection reads selectedTracks(), dataSelectedStartTime/EndTime
            StateRequirement(
                key=StateKey.HAS_TIME_SELECTION,
                required=True,
                description="Must have time selection to trim"
            ),
            StateRequirement(
                key=StateKey.SELECTION_START_TIME,
                required=True,
                description="Start of region to keep (line 1466)"
            ),
            StateRequirement(
                key=StateKey.SELECTION_END_TIME,
                required=True,
                description="End of region to keep (line 1467)"
            ),
            StateRequirement(
                key=StateKey.SELECTED_TRACKS,
                required=True,
                description="Operates on selected tracks only (line 1465)"
            ),
        ],
        parameters={},
        state_writes=[],
        cpp_reference="trackeditactionscontroller.cpp:1462-1484"
    ),

    "silence_selection": ToolStateContract(
        tool_name="silence_selection",
        state_reads=[
            # silenceAudioSelection reads same state as trim
            StateRequirement(
                key=StateKey.HAS_TIME_SELECTION,
                required=True,
                description="Must have time selection to silence"
            ),
            StateRequirement(
                key=StateKey.SELECTION_START_TIME,
                required=True,
                description="Start of region to silence (line 1490)"
            ),
            StateRequirement(
                key=StateKey.SELECTION_END_TIME,
                required=True,
                description="End of region to silence (line 1491)"
            ),
            StateRequirement(
                key=StateKey.SELECTED_TRACKS,
                required=True,
                description="Operates on selected tracks only (line 1489)"
            ),
        ],
        parameters={},
        state_writes=[],
        cpp_reference="trackeditactionscontroller.cpp:1486-1508"
    ),

    "join": ToolStateContract(
        tool_name="join",
        state_reads=[
            # doGlobalJoin reads selectedTracks() and dataSelectedStartTime/EndTime
            StateRequirement(
                key=StateKey.SELECTED_TRACKS,
                required=True,
                description="Operates on selected tracks (line 726)"
            ),
            StateRequirement(
                key=StateKey.SELECTION_START_TIME,
                required=True,
                description="Start of region to join (line 727)"
            ),
            StateRequirement(
                key=StateKey.SELECTION_END_TIME,
                required=True,
                description="End of region to join (line 728)"
            ),
        ],
        parameters={},
        state_writes=[StateKey.SELECTED_CLIPS],
        cpp_reference="trackeditactionscontroller.cpp:724-732"
    ),

    "duplicate_clip": ToolStateContract(
        tool_name="duplicate_clip",
        state_reads=[
            # doGlobalDuplicate reads selectedClips() (line 768)
            StateRequirement(
                key=StateKey.SELECTED_CLIPS,
                required=True,
                description="Requires selected clips (line 768)"
            ),
        ],
        parameters={},
        state_writes=[StateKey.SELECTED_CLIPS],
        cpp_reference="trackeditactionscontroller.cpp:763-784"
    ),

    # === Ripple Edit Operations ===

    "delete_all_tracks_ripple": ToolStateContract(
        tool_name="delete_all_tracks_ripple",
        state_reads=[
            # doGlobalDeleteAllTracksRipple checks timeSelectionIsNotEmpty() (line 635)
            StateRequirement(
                key=StateKey.HAS_TIME_SELECTION,
                required=True,
                description="Must have time selection (line 635)"
            ),
            StateRequirement(
                key=StateKey.SELECTION_START_TIME,
                required=True,
                description="Start of region to delete (line 636)"
            ),
            StateRequirement(
                key=StateKey.SELECTION_END_TIME,
                required=True,
                description="End of region to delete (line 637)"
            ),
            # Note: Uses ALL tracks, not selected tracks (line 633)
        ],
        parameters={},
        state_writes=[StateKey.HAS_TIME_SELECTION],
        cpp_reference="trackeditactionscontroller.cpp:628-667"
    ),

    "cut_all_tracks_ripple": ToolStateContract(
        tool_name="cut_all_tracks_ripple",
        state_reads=[
            # doGlobalCutAllTracksRipple checks timeSelectionIsNotEmpty() (line 471)
            StateRequirement(
                key=StateKey.HAS_TIME_SELECTION,
                required=True,
                description="Must have time selection (line 471)"
            ),
            StateRequirement(
                key=StateKey.SELECTION_START_TIME,
                required=True,
                description="Start of region to cut (line 472)"
            ),
            StateRequirement(
                key=StateKey.SELECTION_END_TIME,
                required=True,
                description="End of region to cut (line 473)"
            ),
            # Note: Uses ALL tracks, not selected tracks (line 469)
        ],
        parameters={},
        state_writes=[StateKey.HAS_TIME_SELECTION],
        cpp_reference="trackeditactionscontroller.cpp:464-503"
    ),

    # === Selection/State-Setting Tools ===

    "set_time_selection": ToolStateContract(
        tool_name="set_time_selection",
        state_reads=[],  # No state reads, just sets state
        parameters={
            "start_time": "Start time in seconds",
            "end_time": "End time in seconds"
        },
        state_writes=[
            StateKey.HAS_TIME_SELECTION,
            StateKey.SELECTION_START_TIME,
            StateKey.SELECTION_END_TIME
        ],
        cpp_reference="trackeditactionscontroller.cpp:1693-1714"
    ),

    "select_all": ToolStateContract(
        tool_name="select_all",
        state_reads=[],
        parameters={},
        state_writes=[
            StateKey.HAS_TIME_SELECTION,
            StateKey.SELECTION_START_TIME,
            StateKey.SELECTION_END_TIME,
            StateKey.SELECTED_TRACKS
        ],
        cpp_reference="trackeditactionscontroller.cpp:1571-1574"
    ),

    "select_all_tracks": ToolStateContract(
        tool_name="select_all_tracks",
        state_reads=[
            StateRequirement(
                key=StateKey.TRACK_LIST,
                required=True,
                description="Need tracks to select (line 1586-1591)"
            ),
        ],
        parameters={},
        state_writes=[StateKey.SELECTED_TRACKS],
        cpp_reference="trackeditactionscontroller.cpp:1584-1592"
    ),

    "clear_selection": ToolStateContract(
        tool_name="clear_selection",
        state_reads=[],
        parameters={},
        state_writes=[
            StateKey.HAS_TIME_SELECTION,
            StateKey.SELECTED_CLIPS,
            StateKey.SELECTED_TRACKS
        ],
        cpp_reference="trackeditactionscontroller.cpp:1576-1582"
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

    # === Track Operations ===

    "create_mono_track": ToolStateContract(
        tool_name="create_mono_track",
        state_reads=[],
        parameters={},
        state_writes=[StateKey.TRACK_LIST],
        cpp_reference="trackeditactionscontroller.cpp:1321-1324"
    ),

    "create_stereo_track": ToolStateContract(
        tool_name="create_stereo_track",
        state_reads=[],
        parameters={},
        state_writes=[StateKey.TRACK_LIST],
        cpp_reference="trackeditactionscontroller.cpp:1326-1329"
    ),

    "delete_track": ToolStateContract(
        tool_name="delete_track",
        state_reads=[
            StateRequirement(
                key=StateKey.SELECTED_TRACKS,
                required=True,
                description="Requires selected tracks (line 1338)"
            ),
        ],
        parameters={},
        state_writes=[StateKey.TRACK_LIST, StateKey.SELECTED_TRACKS],
        cpp_reference="trackeditactionscontroller.cpp:1336-1345"
    ),

    "duplicate_track": ToolStateContract(
        tool_name="duplicate_track",
        state_reads=[
            StateRequirement(
                key=StateKey.SELECTED_TRACKS,
                required=True,
                description="Requires selected tracks (line 1349)"
            ),
        ],
        parameters={},
        state_writes=[StateKey.TRACK_LIST],
        cpp_reference="trackeditactionscontroller.cpp:1347-1356"
    ),

    "move_track_to_top": ToolStateContract(
        tool_name="move_track_to_top",
        state_reads=[
            StateRequirement(
                key=StateKey.SELECTED_TRACKS,
                required=True,
                description="Requires selected tracks (line 1382)"
            ),
        ],
        parameters={},
        state_writes=[],
        cpp_reference="trackeditactionscontroller.cpp:1380-1389"
    ),

    "move_track_to_bottom": ToolStateContract(
        tool_name="move_track_to_bottom",
        state_reads=[
            StateRequirement(
                key=StateKey.SELECTED_TRACKS,
                required=True,
                description="Requires selected tracks (line 1393)"
            ),
        ],
        parameters={},
        state_writes=[],
        cpp_reference="trackeditactionscontroller.cpp:1391-1400"
    ),

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

    "pause": ToolStateContract(
        tool_name="pause",
        state_reads=[],
        parameters={},
        state_writes=[],
        cpp_reference="playbackactionscontroller.cpp:pause action"
    ),

    "rewind_to_start": ToolStateContract(
        tool_name="rewind_to_start",
        state_reads=[],
        parameters={},
        state_writes=[StateKey.CURSOR_POSITION],
        cpp_reference="playbackactionscontroller.cpp:rewind-start action"
    ),

    "toggle_loop": ToolStateContract(
        tool_name="toggle_loop",
        state_reads=[],
        parameters={},
        state_writes=[],
        cpp_reference="playbackactionscontroller.cpp:toggle-loop-region action"
    ),

    # === Undo/Redo ===

    "undo": ToolStateContract(
        tool_name="undo",
        state_reads=[],  # Checks canUndo() internally
        parameters={},
        state_writes=[],  # Can modify any state
        cpp_reference="trackeditactionscontroller.cpp:753-756"
    ),

    "redo": ToolStateContract(
        tool_name="redo",
        state_reads=[],  # Checks canRedo() internally
        parameters={},
        state_writes=[],  # Can modify any state
        cpp_reference="trackeditactionscontroller.cpp:758-761"
    ),

    # === Label Tools ===

    "create_label_track": ToolStateContract(
        tool_name="create_label_track",
        state_reads=[],
        parameters={},
        state_writes=[StateKey.TRACK_LIST],
        cpp_reference="trackeditactionscontroller.cpp:1331-1334"
    ),

    "add_label": ToolStateContract(
        tool_name="add_label",
        state_reads=[
            # addLabelToSelection uses current selection or cursor
            StateRequirement(
                key=StateKey.HAS_TIME_SELECTION,
                required=False,
                description="Uses time selection if available"
            ),
            StateRequirement(
                key=StateKey.CURSOR_POSITION,
                required=False,
                fallback_from=StateKey.HAS_TIME_SELECTION,
                description="Uses cursor position if no time selection"
            ),
        ],
        parameters={},
        state_writes=[],
        cpp_reference="trackeditactionscontroller.cpp:1899-1902"
    ),
}


# Map from state key to the tool that can set it
STATE_SETTERS: Dict[StateKey, str] = {
    StateKey.HAS_TIME_SELECTION: "set_time_selection",
    StateKey.SELECTION_START_TIME: "set_time_selection",
    StateKey.SELECTION_END_TIME: "set_time_selection",
    StateKey.CURSOR_POSITION: "seek",
    StateKey.SELECTED_TRACKS: "select_all_tracks",
    StateKey.SELECTED_CLIPS: "select_all",  # Or specific clip selection
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
    return STATE_SETTERS.get(state_key)


def get_all_tool_names() -> List[str]:
    """Get list of all tools with contracts."""
    return list(TOOL_STATE_CONTRACTS.keys())


def tool_requires_time_selection(tool_name: str) -> bool:
    """Check if a tool requires time selection."""
    contract = get_contract(tool_name)
    if not contract:
        return False
    return any(
        req.key == StateKey.HAS_TIME_SELECTION and req.required
        for req in contract.state_reads
    )


def tool_requires_track_selection(tool_name: str) -> bool:
    """Check if a tool requires track selection."""
    contract = get_contract(tool_name)
    if not contract:
        return False
    return any(
        req.key == StateKey.SELECTED_TRACKS and req.required
        for req in contract.state_reads
    )


def is_state_setting_tool(tool_name: str) -> bool:
    """Check if a tool is primarily used for setting state."""
    state_setting_tools = {
        "set_time_selection",
        "select_all",
        "select_all_tracks",
        "clear_selection",
        "seek",
        "set_selection_start_time",
        "set_selection_end_time",
        "reset_selection"
    }
    return tool_name in state_setting_tools
