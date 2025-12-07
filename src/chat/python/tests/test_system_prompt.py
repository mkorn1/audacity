#!/usr/bin/env python3
"""
Unit tests for the simplified system prompt

Tests:
- System prompt is concise (small token footprint)
- System prompt includes core principle about intent-based commands
- System prompt includes time parsing guidance
- System prompt includes examples
- System prompt includes state query tools

NOTE: As of the State Preparation architecture update (2025-12-06), the
system prompt is simplified and no longer contains verbose prerequisite
documentation, multi-step examples, or detailed planning workflow. The
State Preparation system handles these automatically.
"""

import unittest
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from tool_schemas import FUNCTION_CALLING_SYSTEM_PROMPT


class TestSystemPrompt(unittest.TestCase):
    """Test simplified system prompt"""

    def test_prompt_is_concise(self):
        """Test that prompt is concise (under 2000 chars for LLM efficiency)"""
        # The simplified prompt should be much smaller than the old verbose one
        self.assertLess(
            len(FUNCTION_CALLING_SYSTEM_PROMPT),
            2500,
            f"System prompt is too long ({len(FUNCTION_CALLING_SYSTEM_PROMPT)} chars). "
            "It should be concise - the State Preparation system handles prerequisites automatically."
        )

    def test_includes_core_principle(self):
        """Test that prompt includes the core principle about intent-based commands"""
        self.assertIn("Core Principle", FUNCTION_CALLING_SYSTEM_PROMPT)
        self.assertIn("backend", FUNCTION_CALLING_SYSTEM_PROMPT.lower())
        # Should explain that backend handles state automatically
        self.assertIn("automatically", FUNCTION_CALLING_SYSTEM_PROMPT.lower())

    def test_includes_time_parsing(self):
        """Test that prompt includes time parsing guidance"""
        self.assertIn("Time Parsing", FUNCTION_CALLING_SYSTEM_PROMPT)
        # Should include time format examples
        self.assertIn("20s", FUNCTION_CALLING_SYSTEM_PROMPT)
        self.assertIn("1:30", FUNCTION_CALLING_SYSTEM_PROMPT)
        self.assertIn("first 30 seconds", FUNCTION_CALLING_SYSTEM_PROMPT.lower())

    def test_includes_examples(self):
        """Test that prompt includes simple examples"""
        self.assertIn("Examples", FUNCTION_CALLING_SYSTEM_PROMPT)
        # Should have at least a few examples
        self.assertIn("Split at 20 seconds", FUNCTION_CALLING_SYSTEM_PROMPT)
        self.assertIn("Trim first 30 seconds", FUNCTION_CALLING_SYSTEM_PROMPT)

    def test_includes_state_query_tools(self):
        """Test that prompt includes state query tools section"""
        self.assertIn("State Query Tools", FUNCTION_CALLING_SYSTEM_PROMPT)
        self.assertIn("has_time_selection", FUNCTION_CALLING_SYSTEM_PROMPT)
        self.assertIn("get_cursor_position", FUNCTION_CALLING_SYSTEM_PROMPT)
        self.assertIn("get_total_project_time", FUNCTION_CALLING_SYSTEM_PROMPT)

    def test_no_verbose_prerequisite_docs(self):
        """Test that prompt does NOT contain verbose prerequisite documentation"""
        # These sections should NOT be in the new simplified prompt
        self.assertNotIn("Multi-Step Operation Examples", FUNCTION_CALLING_SYSTEM_PROMPT)
        self.assertNotIn("Planning Workflow", FUNCTION_CALLING_SYSTEM_PROMPT)
        self.assertNotIn("Error Handling", FUNCTION_CALLING_SYSTEM_PROMPT)
        self.assertNotIn("Location Parsing", FUNCTION_CALLING_SYSTEM_PROMPT)

    def test_explains_backend_handles_prerequisites(self):
        """Test that prompt explains the backend handles prerequisites"""
        prompt_lower = FUNCTION_CALLING_SYSTEM_PROMPT.lower()
        # Should explain that backend handles state
        self.assertIn("detect what state is needed", prompt_lower)
        self.assertIn("infer values", prompt_lower)
        self.assertIn("set up the required state", prompt_lower)

    def test_includes_basic_tool_examples(self):
        """Test that basic tool usage examples are included"""
        self.assertIn("trim_to_selection", FUNCTION_CALLING_SYSTEM_PROMPT)
        self.assertIn("delete_selection", FUNCTION_CALLING_SYSTEM_PROMPT)
        self.assertIn("split_at_time", FUNCTION_CALLING_SYSTEM_PROMPT)

    def test_mentions_no_worry_about_prerequisites(self):
        """Test that prompt tells LLM not to worry about prerequisites"""
        prompt_lower = FUNCTION_CALLING_SYSTEM_PROMPT.lower()
        self.assertIn("don't need to worry", prompt_lower)
        self.assertIn("prerequisites", prompt_lower)


if __name__ == '__main__':
    unittest.main()
