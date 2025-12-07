#!/usr/bin/env python3
"""
Unit tests for state_contracts.py
"""

import sys
import os
import unittest

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from state_contracts import (
    TOOL_STATE_CONTRACTS,
    StateKey,
    StateRequirement,
    ToolStateContract,
    get_contract,
    get_required_state,
    get_state_setting_tool,
    get_all_tool_names,
    tool_requires_time_selection,
    tool_requires_track_selection,
    is_state_setting_tool,
)


class TestStateContractsStructure(unittest.TestCase):
    """Test contract structure and validity."""

    def test_contracts_import_without_errors(self):
        """Verify state_contracts.py imports without errors."""
        self.assertIsNotNone(TOOL_STATE_CONTRACTS)
        self.assertGreater(len(TOOL_STATE_CONTRACTS), 0)

    def test_all_contracts_have_required_fields(self):
        """Verify each contract has required fields."""
        for tool_name, contract in TOOL_STATE_CONTRACTS.items():
            self.assertIsInstance(contract, ToolStateContract, f"{tool_name} is not ToolStateContract")
            self.assertEqual(contract.tool_name, tool_name, f"Mismatched tool_name for {tool_name}")
            self.assertIsInstance(contract.state_reads, list, f"{tool_name} state_reads is not list")
            self.assertIsInstance(contract.parameters, dict, f"{tool_name} parameters is not dict")
            self.assertIsInstance(contract.state_writes, list, f"{tool_name} state_writes is not list")
            self.assertIsInstance(contract.cpp_reference, str, f"{tool_name} cpp_reference is not str")

    def test_state_requirements_have_valid_keys(self):
        """Verify state requirements use valid StateKey enum values."""
        for tool_name, contract in TOOL_STATE_CONTRACTS.items():
            for req in contract.state_reads:
                self.assertIsInstance(req, StateRequirement, f"{tool_name} has non-StateRequirement")
                self.assertIsInstance(req.key, StateKey, f"{tool_name} has invalid StateKey")
                self.assertIsInstance(req.required, bool, f"{tool_name} required is not bool")
                if req.fallback_from is not None:
                    self.assertIsInstance(req.fallback_from, StateKey, f"{tool_name} fallback_from invalid")

    def test_state_writes_have_valid_keys(self):
        """Verify state_writes use valid StateKey enum values."""
        for tool_name, contract in TOOL_STATE_CONTRACTS.items():
            for state_key in contract.state_writes:
                self.assertIsInstance(state_key, StateKey, f"{tool_name} state_writes has invalid key")


class TestCoreToolContracts(unittest.TestCase):
    """Test specific tool contracts match C++ implementation."""

    def test_split_at_time_contract(self):
        """Verify split_at_time contract matches C++ (line 1716-1735)."""
        contract = get_contract("split_at_time")
        self.assertIsNotNone(contract)

        # split_at_time has no selection requirements - uses orderedTrackList()
        self.assertEqual(len(contract.state_reads), 0)

        # Requires time parameter
        self.assertIn("time", contract.parameters)

        # Writes to selected_clips
        self.assertIn(StateKey.SELECTED_CLIPS, contract.state_writes)

    def test_cut_contract(self):
        """Verify cut contract matches C++ (line 363-424)."""
        contract = get_contract("cut")
        self.assertIsNotNone(contract)

        # cut requires time selection and selected tracks
        required_keys = get_required_state("cut")
        self.assertIn(StateKey.HAS_TIME_SELECTION, required_keys)
        self.assertIn(StateKey.SELECTION_START_TIME, required_keys)
        self.assertIn(StateKey.SELECTION_END_TIME, required_keys)
        self.assertIn(StateKey.SELECTED_TRACKS, required_keys)

        # No parameters
        self.assertEqual(len(contract.parameters), 0)

    def test_trim_to_selection_contract(self):
        """Verify trim_to_selection contract matches C++ (line 1462-1484)."""
        contract = get_contract("trim_to_selection")
        self.assertIsNotNone(contract)

        # trim requires time selection and selected tracks
        required_keys = get_required_state("trim_to_selection")
        self.assertIn(StateKey.HAS_TIME_SELECTION, required_keys)
        self.assertIn(StateKey.SELECTION_START_TIME, required_keys)
        self.assertIn(StateKey.SELECTION_END_TIME, required_keys)
        self.assertIn(StateKey.SELECTED_TRACKS, required_keys)

    def test_paste_contract(self):
        """Verify paste contract matches C++ (line 1053-1112)."""
        contract = get_contract("paste")
        self.assertIsNotNone(contract)

        # paste requires cursor position
        required_keys = get_required_state("paste")
        self.assertIn(StateKey.CURSOR_POSITION, required_keys)

        # Does NOT require time selection
        self.assertNotIn(StateKey.HAS_TIME_SELECTION, required_keys)

    def test_set_time_selection_contract(self):
        """Verify set_time_selection contract matches C++ (line 1693-1714)."""
        contract = get_contract("set_time_selection")
        self.assertIsNotNone(contract)

        # set_time_selection has no state reads
        self.assertEqual(len(contract.state_reads), 0)

        # Requires start_time and end_time parameters
        self.assertIn("start_time", contract.parameters)
        self.assertIn("end_time", contract.parameters)

        # Writes to selection state
        self.assertIn(StateKey.HAS_TIME_SELECTION, contract.state_writes)
        self.assertIn(StateKey.SELECTION_START_TIME, contract.state_writes)
        self.assertIn(StateKey.SELECTION_END_TIME, contract.state_writes)

    def test_split_contract(self):
        """Verify split contract matches C++ (line 669-703)."""
        contract = get_contract("split")
        self.assertIsNotNone(contract)

        # split has optional requirements (can use time selection or cursor)
        has_time_sel_req = None
        cursor_req = None
        for req in contract.state_reads:
            if req.key == StateKey.HAS_TIME_SELECTION:
                has_time_sel_req = req
            elif req.key == StateKey.CURSOR_POSITION:
                cursor_req = req

        # HAS_TIME_SELECTION is optional
        self.assertIsNotNone(has_time_sel_req)
        self.assertFalse(has_time_sel_req.required)

        # CURSOR_POSITION is optional with fallback
        self.assertIsNotNone(cursor_req)
        self.assertFalse(cursor_req.required)
        self.assertEqual(cursor_req.fallback_from, StateKey.HAS_TIME_SELECTION)


class TestHelperFunctions(unittest.TestCase):
    """Test helper functions."""

    def test_get_contract_returns_contract_for_known_tool(self):
        """get_contract returns contract for known tools."""
        contract = get_contract("cut")
        self.assertIsNotNone(contract)
        self.assertEqual(contract.tool_name, "cut")

    def test_get_contract_returns_none_for_unknown_tool(self):
        """get_contract returns None for unknown tools."""
        contract = get_contract("nonexistent_tool")
        self.assertIsNone(contract)

    def test_get_required_state_returns_required_keys(self):
        """get_required_state returns only required state keys."""
        required = get_required_state("cut")
        self.assertIn(StateKey.HAS_TIME_SELECTION, required)

        # split has no required keys
        required = get_required_state("split")
        self.assertEqual(len(required), 0)

    def test_get_state_setting_tool(self):
        """get_state_setting_tool returns correct tools."""
        self.assertEqual(get_state_setting_tool(StateKey.HAS_TIME_SELECTION), "set_time_selection")
        self.assertEqual(get_state_setting_tool(StateKey.CURSOR_POSITION), "seek")
        self.assertEqual(get_state_setting_tool(StateKey.SELECTED_TRACKS), "select_all_tracks")

    def test_get_all_tool_names(self):
        """get_all_tool_names returns list of tool names."""
        names = get_all_tool_names()
        self.assertIn("cut", names)
        self.assertIn("split_at_time", names)
        self.assertIn("paste", names)
        self.assertGreater(len(names), 20)

    def test_tool_requires_time_selection(self):
        """tool_requires_time_selection returns correct values."""
        self.assertTrue(tool_requires_time_selection("cut"))
        self.assertTrue(tool_requires_time_selection("trim_to_selection"))
        self.assertFalse(tool_requires_time_selection("split_at_time"))
        self.assertFalse(tool_requires_time_selection("play"))

    def test_tool_requires_track_selection(self):
        """tool_requires_track_selection returns correct values."""
        self.assertTrue(tool_requires_track_selection("cut"))
        self.assertTrue(tool_requires_track_selection("delete_track"))
        self.assertFalse(tool_requires_track_selection("split_at_time"))
        self.assertFalse(tool_requires_track_selection("play"))

    def test_is_state_setting_tool(self):
        """is_state_setting_tool identifies state setters."""
        self.assertTrue(is_state_setting_tool("set_time_selection"))
        self.assertTrue(is_state_setting_tool("select_all_tracks"))
        self.assertTrue(is_state_setting_tool("seek"))
        self.assertFalse(is_state_setting_tool("cut"))
        self.assertFalse(is_state_setting_tool("play"))


class TestToolCoverage(unittest.TestCase):
    """Test that all tools in tools.py have contracts."""

    def test_core_editing_tools_have_contracts(self):
        """Core editing tools have contracts."""
        core_tools = [
            "cut", "copy", "paste", "delete_selection",
            "trim_to_selection", "silence_selection",
            "split", "split_at_time", "join",
            "undo", "redo"
        ]
        for tool in core_tools:
            self.assertIsNotNone(get_contract(tool), f"Missing contract for {tool}")

    def test_selection_tools_have_contracts(self):
        """Selection tools have contracts."""
        selection_tools = [
            "set_time_selection", "select_all", "select_all_tracks",
            "clear_selection", "seek"
        ]
        for tool in selection_tools:
            self.assertIsNotNone(get_contract(tool), f"Missing contract for {tool}")

    def test_track_tools_have_contracts(self):
        """Track tools have contracts."""
        track_tools = [
            "create_mono_track", "create_stereo_track",
            "delete_track", "duplicate_track",
            "move_track_to_top", "move_track_to_bottom"
        ]
        for tool in track_tools:
            self.assertIsNotNone(get_contract(tool), f"Missing contract for {tool}")

    def test_playback_tools_have_contracts(self):
        """Playback tools have contracts."""
        playback_tools = [
            "play", "stop", "pause", "rewind_to_start", "toggle_loop"
        ]
        for tool in playback_tools:
            self.assertIsNotNone(get_contract(tool), f"Missing contract for {tool}")


if __name__ == "__main__":
    unittest.main()
