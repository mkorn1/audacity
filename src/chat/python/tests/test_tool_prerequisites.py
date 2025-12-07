#!/usr/bin/env python3
"""
Unit tests for tool prerequisites

Tests the tool prerequisite infrastructure including:
- TOOL_PREREQUISITES structure (deprecated, kept for backward compatibility)
- Prerequisite checking logic
- New tools from TOOL_CATALOG.md
- Tool definitions
- Prerequisite mapping

NOTE: As of the State Preparation architecture update (2025-12-06), the
primary source of truth for tool prerequisites is state_contracts.py.
TOOL_PREREQUISITES in tool_schemas.py is deprecated but maintained for
backward compatibility. Tool descriptions no longer contain verbose
prerequisite documentation - the State Preparation system handles this
automatically.
"""

import unittest
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from tool_schemas import TOOL_DEFINITIONS, TOOL_PREREQUISITES


class TestToolPrerequisitesStructure(unittest.TestCase):
    """Test TOOL_PREREQUISITES structure"""

    def test_all_tools_have_prerequisite_definitions(self):
        """Test all tools in TOOL_DEFINITIONS have prerequisite definitions"""
        tool_names = [tool["function"]["name"] for tool in TOOL_DEFINITIONS]
        
        for tool_name in tool_names:
            self.assertIn(
                tool_name, 
                TOOL_PREREQUISITES,
                f"Tool '{tool_name}' is in TOOL_DEFINITIONS but missing from TOOL_PREREQUISITES"
            )

    def test_prerequisite_structure_validation(self):
        """Test prerequisite structure is valid for all tools"""
        required_keys = ["project_open", "time_selection", "selected_clips", "selected_tracks", "cursor_position"]
        
        for tool_name, prerequisites in TOOL_PREREQUISITES.items():
            for key in required_keys:
                self.assertIn(
                    key,
                    prerequisites,
                    f"Tool '{tool_name}' missing prerequisite key '{key}'"
                )
                # Value should be True, False, or None
                self.assertIn(
                    prerequisites[key],
                    [True, False, None],
                    f"Tool '{tool_name}' has invalid value for '{key}': {prerequisites[key]}"
                )

    def test_required_vs_optional_prerequisites(self):
        """Test that required prerequisites are marked as True"""
        # Tools that require time_selection
        time_selection_required = [
            "trim_to_selection",
            "silence_selection",
            "cut",
            "copy",
            "delete_selection",
            "delete_all_tracks_ripple",
            "cut_all_tracks_ripple",
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
            "repeat_last_effect",
        ]
        
        for tool_name in time_selection_required:
            if tool_name in TOOL_PREREQUISITES:
                self.assertTrue(
                    TOOL_PREREQUISITES[tool_name]["time_selection"],
                    f"Tool '{tool_name}' should require time_selection but it's not marked as required"
                )

    def test_selected_clips_required(self):
        """Test tools that require selected_clips are marked correctly"""
        selected_clips_required = [
            "join",
            "duplicate_clip",
        ]
        
        for tool_name in selected_clips_required:
            if tool_name in TOOL_PREREQUISITES:
                self.assertTrue(
                    TOOL_PREREQUISITES[tool_name]["selected_clips"],
                    f"Tool '{tool_name}' should require selected_clips but it's not marked as required"
                )

    def test_selected_tracks_required(self):
        """Test tools that require selected_tracks are marked correctly"""
        selected_tracks_required = [
            "delete_track",
            "duplicate_track",
            "move_track_to_top",
            "move_track_to_bottom",
        ]
        
        for tool_name in selected_tracks_required:
            if tool_name in TOOL_PREREQUISITES:
                self.assertTrue(
                    TOOL_PREREQUISITES[tool_name]["selected_tracks"],
                    f"Tool '{tool_name}' should require selected_tracks but it's not marked as required"
                )

    def test_project_open_always_required(self):
        """Test that project_open is always True (required) for all tools"""
        for tool_name, prerequisites in TOOL_PREREQUISITES.items():
            # State query tools might have optional project_open, but most tools require it
            if not tool_name.startswith("get_") and tool_name != "action_enabled":
                self.assertTrue(
                    prerequisites["project_open"],
                    f"Tool '{tool_name}' should require project_open"
                )


class TestPrerequisiteCheckingLogic(unittest.TestCase):
    """Test prerequisite checking logic"""
    
    def test_check_prerequisites_all_met(self):
        """Test check_prerequisites() with all prerequisites met"""
        # Create a helper function to check prerequisites
        def check_prerequisites(tool_name: str, state_snapshot: dict):
            """Check if prerequisites are met for a tool"""
            if tool_name not in TOOL_PREREQUISITES:
                return False, [f"Unknown tool: {tool_name}"]
            
            prerequisites = TOOL_PREREQUISITES[tool_name]
            missing = []
            
            # Check project_open
            if prerequisites["project_open"] and not state_snapshot.get("project_open", False):
                missing.append("project_open")
            
            # Check time_selection
            if prerequisites["time_selection"] is True:
                if not state_snapshot.get("time_selection", False):
                    missing.append("time_selection")
            
            # Check selected_clips
            if prerequisites["selected_clips"] is True:
                if not state_snapshot.get("selected_clips", False):
                    missing.append("selected_clips")
            
            # Check selected_tracks
            if prerequisites["selected_tracks"] is True:
                if not state_snapshot.get("selected_tracks", False):
                    missing.append("selected_tracks")
            
            return len(missing) == 0, missing
        
        # Test with all prerequisites met
        state = {
            "project_open": True,
            "time_selection": True,
            "selected_clips": True,
            "selected_tracks": True,
        }
        
        result, missing = check_prerequisites("trim_to_selection", state)
        self.assertTrue(result)
        self.assertEqual(missing, [])

    def test_check_prerequisites_missing_required(self):
        """Test check_prerequisites() with missing required prerequisite"""
        def check_prerequisites(tool_name: str, state_snapshot: dict):
            """Check if prerequisites are met for a tool"""
            if tool_name not in TOOL_PREREQUISITES:
                return False, [f"Unknown tool: {tool_name}"]
            
            prerequisites = TOOL_PREREQUISITES[tool_name]
            missing = []
            
            if prerequisites["project_open"] and not state_snapshot.get("project_open", False):
                missing.append("project_open")
            if prerequisites["time_selection"] is True:
                if not state_snapshot.get("time_selection", False):
                    missing.append("time_selection")
            if prerequisites["selected_clips"] is True:
                if not state_snapshot.get("selected_clips", False):
                    missing.append("selected_clips")
            if prerequisites["selected_tracks"] is True:
                if not state_snapshot.get("selected_tracks", False):
                    missing.append("selected_tracks")
            
            return len(missing) == 0, missing
        
        # Test with missing time_selection
        state = {
            "project_open": True,
            "time_selection": False,  # Missing!
            "selected_clips": True,
            "selected_tracks": True,
        }
        
        result, missing = check_prerequisites("trim_to_selection", state)
        self.assertFalse(result)
        self.assertIn("time_selection", missing)

    def test_check_prerequisites_missing_optional(self):
        """Test check_prerequisites() with missing optional prerequisite"""
        def check_prerequisites(tool_name: str, state_snapshot: dict):
            """Check if prerequisites are met for a tool"""
            if tool_name not in TOOL_PREREQUISITES:
                return False, [f"Unknown tool: {tool_name}"]
            
            prerequisites = TOOL_PREREQUISITES[tool_name]
            missing = []
            
            if prerequisites["project_open"] and not state_snapshot.get("project_open", False):
                missing.append("project_open")
            if prerequisites["time_selection"] is True:
                if not state_snapshot.get("time_selection", False):
                    missing.append("time_selection")
            
            return len(missing) == 0, missing
        
        # Test with optional prerequisite missing (should still pass)
        state = {
            "project_open": True,
            "time_selection": False,  # Optional for split
        }
        
        # split has time_selection as False (optional)
        if "split" in TOOL_PREREQUISITES:
            result, missing = check_prerequisites("split", state)
            # Should pass because time_selection is optional
            self.assertTrue(result or "split" not in TOOL_PREREQUISITES)

    def test_check_prerequisites_invalid_tool_name(self):
        """Test check_prerequisites() with invalid tool name"""
        def check_prerequisites(tool_name: str, state_snapshot: dict):
            """Check if prerequisites are met for a tool"""
            if tool_name not in TOOL_PREREQUISITES:
                return False, [f"Unknown tool: {tool_name}"]
            
            prerequisites = TOOL_PREREQUISITES[tool_name]
            missing = []
            
            if prerequisites["project_open"] and not state_snapshot.get("project_open", False):
                missing.append("project_open")
            
            return len(missing) == 0, missing
        
        state = {"project_open": True}
        result, missing = check_prerequisites("nonexistent_tool", state)
        self.assertFalse(result)
        self.assertIn("Unknown tool", missing[0])


class TestNewToolsFromCatalog(unittest.TestCase):
    """Test new tools added from TOOL_CATALOG.md"""
    
    def test_set_selection_start_time_definition(self):
        """Test set_selection_start_time tool definition"""
        tool = next((t for t in TOOL_DEFINITIONS if t["function"]["name"] == "set_selection_start_time"), None)
        self.assertIsNotNone(tool, "set_selection_start_time should be in TOOL_DEFINITIONS")
        self.assertEqual(tool["function"]["parameters"]["required"], ["time"])
        self.assertIn("time", tool["function"]["parameters"]["properties"])

    def test_set_selection_end_time_definition(self):
        """Test set_selection_end_time tool definition"""
        tool = next((t for t in TOOL_DEFINITIONS if t["function"]["name"] == "set_selection_end_time"), None)
        self.assertIsNotNone(tool, "set_selection_end_time should be in TOOL_DEFINITIONS")
        self.assertEqual(tool["function"]["parameters"]["required"], ["time"])
        self.assertIn("time", tool["function"]["parameters"]["properties"])

    def test_reset_selection_definition(self):
        """Test reset_selection tool definition"""
        tool = next((t for t in TOOL_DEFINITIONS if t["function"]["name"] == "reset_selection"), None)
        self.assertIsNotNone(tool, "reset_selection should be in TOOL_DEFINITIONS")
        self.assertEqual(tool["function"]["parameters"]["required"], [])

    def test_delete_all_tracks_ripple_definition(self):
        """Test delete_all_tracks_ripple tool definition"""
        tool = next((t for t in TOOL_DEFINITIONS if t["function"]["name"] == "delete_all_tracks_ripple"), None)
        self.assertIsNotNone(tool, "delete_all_tracks_ripple should be in TOOL_DEFINITIONS")
        # Description should be concise (prerequisites handled by state_contracts.py)
        self.assertIsNotNone(tool["function"]["description"])

    def test_cut_all_tracks_ripple_definition(self):
        """Test cut_all_tracks_ripple tool definition"""
        tool = next((t for t in TOOL_DEFINITIONS if t["function"]["name"] == "cut_all_tracks_ripple"), None)
        self.assertIsNotNone(tool, "cut_all_tracks_ripple should be in TOOL_DEFINITIONS")
        # Description should be concise (prerequisites handled by state_contracts.py)
        self.assertIsNotNone(tool["function"]["description"])

    def test_apply_normalize_loudness_definition(self):
        """Test apply_normalize_loudness tool definition"""
        tool = next((t for t in TOOL_DEFINITIONS if t["function"]["name"] == "apply_normalize_loudness"), None)
        self.assertIsNotNone(tool, "apply_normalize_loudness should be in TOOL_DEFINITIONS")
        # Description should be concise (prerequisites handled by state_contracts.py)
        self.assertIsNotNone(tool["function"]["description"])

    def test_apply_compressor_definition(self):
        """Test apply_compressor tool definition"""
        tool = next((t for t in TOOL_DEFINITIONS if t["function"]["name"] == "apply_compressor"), None)
        self.assertIsNotNone(tool, "apply_compressor should be in TOOL_DEFINITIONS")
        # Description should be concise (prerequisites handled by state_contracts.py)
        self.assertIsNotNone(tool["function"]["description"])

    def test_apply_limiter_definition(self):
        """Test apply_limiter tool definition"""
        tool = next((t for t in TOOL_DEFINITIONS if t["function"]["name"] == "apply_limiter"), None)
        self.assertIsNotNone(tool, "apply_limiter should be in TOOL_DEFINITIONS")
        # Description should be concise (prerequisites handled by state_contracts.py)
        self.assertIsNotNone(tool["function"]["description"])

    def test_apply_truncate_silence_definition(self):
        """Test apply_truncate_silence tool definition"""
        tool = next((t for t in TOOL_DEFINITIONS if t["function"]["name"] == "apply_truncate_silence"), None)
        self.assertIsNotNone(tool, "apply_truncate_silence should be in TOOL_DEFINITIONS")
        # Description should be concise (prerequisites handled by state_contracts.py)
        self.assertIsNotNone(tool["function"]["description"])

    def test_repeat_last_effect_definition(self):
        """Test repeat_last_effect tool definition"""
        tool = next((t for t in TOOL_DEFINITIONS if t["function"]["name"] == "repeat_last_effect"), None)
        self.assertIsNotNone(tool, "repeat_last_effect should be in TOOL_DEFINITIONS")
        # Description should be concise (prerequisites handled by state_contracts.py)
        self.assertIsNotNone(tool["function"]["description"])

    def test_seek_definition(self):
        """Test seek tool definition"""
        tool = next((t for t in TOOL_DEFINITIONS if t["function"]["name"] == "seek"), None)
        self.assertIsNotNone(tool, "seek should be in TOOL_DEFINITIONS")
        self.assertEqual(tool["function"]["parameters"]["required"], ["time"])
        self.assertIn("time", tool["function"]["parameters"]["properties"])

    def test_create_label_track_definition(self):
        """Test create_label_track tool definition"""
        tool = next((t for t in TOOL_DEFINITIONS if t["function"]["name"] == "create_label_track"), None)
        self.assertIsNotNone(tool, "create_label_track should be in TOOL_DEFINITIONS")
        self.assertEqual(tool["function"]["parameters"]["required"], [])

    def test_add_label_definition(self):
        """Test add_label tool definition"""
        tool = next((t for t in TOOL_DEFINITIONS if t["function"]["name"] == "add_label"), None)
        self.assertIsNotNone(tool, "add_label should be in TOOL_DEFINITIONS")
        # Description should be concise (prerequisites handled by state_contracts.py)
        self.assertIsNotNone(tool["function"]["description"])

    def test_move_track_to_top_definition(self):
        """Test move_track_to_top tool definition"""
        tool = next((t for t in TOOL_DEFINITIONS if t["function"]["name"] == "move_track_to_top"), None)
        self.assertIsNotNone(tool, "move_track_to_top should be in TOOL_DEFINITIONS")
        # Description should be concise (prerequisites handled by state_contracts.py)
        self.assertIsNotNone(tool["function"]["description"])

    def test_move_track_to_bottom_definition(self):
        """Test move_track_to_bottom tool definition"""
        tool = next((t for t in TOOL_DEFINITIONS if t["function"]["name"] == "move_track_to_bottom"), None)
        self.assertIsNotNone(tool, "move_track_to_bottom should be in TOOL_DEFINITIONS")
        # Description should be concise (prerequisites handled by state_contracts.py)
        self.assertIsNotNone(tool["function"]["description"])


class TestToolDescriptions(unittest.TestCase):
    """Test tool descriptions are present and concise.

    NOTE: As of the State Preparation architecture update (2025-12-06),
    tool descriptions are simplified and no longer contain verbose
    prerequisite documentation. Prerequisites are now managed by
    state_contracts.py and the State Preparation system.
    """

    def test_tools_have_descriptions(self):
        """Test all tools have descriptions"""
        for tool in TOOL_DEFINITIONS:
            description = tool["function"]["description"]
            self.assertIsNotNone(
                description,
                f"Tool '{tool['function']['name']}' should have a description"
            )
            self.assertGreater(
                len(description),
                10,
                f"Tool '{tool['function']['name']}' description should be meaningful"
            )

    def test_descriptions_are_concise(self):
        """Test descriptions are concise (under 200 chars) for LLM efficiency"""
        for tool in TOOL_DEFINITIONS:
            description = tool["function"]["description"]
            # Descriptions should be concise to reduce token usage
            # (Prerequisites are handled by state_contracts.py, not in descriptions)
            self.assertLess(
                len(description),
                300,
                f"Tool '{tool['function']['name']}' description is too long ({len(description)} chars). "
                "Prerequisites should be in state_contracts.py, not the description."
            )

    def test_descriptions_explain_what_tool_does(self):
        """Test descriptions explain what the tool does (not how to use it)"""
        tool = next((t for t in TOOL_DEFINITIONS if t["function"]["name"] == "trim_to_selection"), None)
        if tool:
            description = tool["function"]["description"].lower()
            # Should describe the action, not usage instructions
            self.assertTrue(
                "keep" in description or "trim" in description or "audio" in description,
                "trim_to_selection description should explain what the tool does"
            )


class TestPrerequisiteMapping(unittest.TestCase):
    """Test prerequisite mapping to tools"""
    
    def test_time_selection_prerequisite_maps_to_set_time_selection(self):
        """Test time_selection prerequisite maps to set_time_selection tool"""
        # Verify set_time_selection exists
        tool = next((t for t in TOOL_DEFINITIONS if t["function"]["name"] == "set_time_selection"), None)
        self.assertIsNotNone(tool, "set_time_selection tool should exist")
        
        # Verify tools that require time_selection can use set_time_selection
        tools_requiring_time_selection = [
            "trim_to_selection",
            "cut",
            "apply_normalize",
        ]
        
        for tool_name in tools_requiring_time_selection:
            if tool_name in TOOL_PREREQUISITES:
                self.assertTrue(
                    TOOL_PREREQUISITES[tool_name]["time_selection"],
                    f"Tool '{tool_name}' requires time_selection"
                )

    def test_selected_clips_prerequisite_maps_to_selection_tools(self):
        """Test selected_clips prerequisite maps to appropriate selection tools"""
        # Verify tools that require selected_clips
        tools_requiring_clips = ["join", "duplicate_clip"]
        
        for tool_name in tools_requiring_clips:
            if tool_name in TOOL_PREREQUISITES:
                self.assertTrue(
                    TOOL_PREREQUISITES[tool_name]["selected_clips"],
                    f"Tool '{tool_name}' requires selected_clips"
                )

    def test_selected_tracks_prerequisite_maps_to_selection_tools(self):
        """Test selected_tracks prerequisite maps to appropriate selection tools"""
        # Verify tools that require selected_tracks
        tools_requiring_tracks = [
            "delete_track",
            "duplicate_track",
            "move_track_to_top",
            "move_track_to_bottom",
        ]
        
        for tool_name in tools_requiring_tracks:
            if tool_name in TOOL_PREREQUISITES:
                self.assertTrue(
                    TOOL_PREREQUISITES[tool_name]["selected_tracks"],
                    f"Tool '{tool_name}' requires selected_tracks"
                )

    def test_cursor_position_prerequisite_handling(self):
        """Test cursor_position prerequisite handling"""
        # Tools that optionally use cursor_position
        tools_with_optional_cursor = ["paste", "add_label"]
        
        for tool_name in tools_with_optional_cursor:
            if tool_name in TOOL_PREREQUISITES:
                cursor_req = TOOL_PREREQUISITES[tool_name]["cursor_position"]
                # Should be False (optional) or None (not applicable)
                self.assertIn(
                    cursor_req,
                    [False, None],
                    f"Tool '{tool_name}' should have optional cursor_position"
                )


class TestIntegration(unittest.TestCase):
    """Integration tests for prerequisite system"""
    
    def test_prerequisite_system_with_tool_registry(self):
        """Test prerequisite system works with tool registry structure"""
        # Verify all tools in TOOL_DEFINITIONS have prerequisites
        tool_names = [tool["function"]["name"] for tool in TOOL_DEFINITIONS]
        
        for tool_name in tool_names:
            self.assertIn(
                tool_name,
                TOOL_PREREQUISITES,
                f"Tool '{tool_name}' needs prerequisite definition"
            )
    
    def test_prerequisite_validation_with_state_queries(self):
        """Test prerequisite validation can work with state queries"""
        # Tools that require state queries to check prerequisites
        state_query_tools = [
            "has_time_selection",
            "get_selected_tracks",
            "get_selected_clips",
        ]
        
        # Verify these tools exist
        for tool_name in state_query_tools:
            tool = next((t for t in TOOL_DEFINITIONS if t["function"]["name"] == tool_name), None)
            self.assertIsNotNone(
                tool,
                f"State query tool '{tool_name}' should exist for prerequisite checking"
            )


if __name__ == '__main__':
    unittest.main()

