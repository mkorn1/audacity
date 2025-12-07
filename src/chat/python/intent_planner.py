#!/usr/bin/env python3
"""
Intent Planner Phase
Uses LLM to analyze user intent and generate tool execution plan.
"""

import json
import sys
from typing import Dict, Any, List, Optional, Tuple

# Import OpenAI SDK when available
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

from config import get_openai_api_key, is_openai_configured, get_chat_model
from tool_schemas import TOOL_DEFINITIONS, FUNCTION_CALLING_SYSTEM_PROMPT
from location_parser import LocationParser


class IntentPlanner:
    """
    Plans tool execution by analyzing user intent with LLM.
    """

    def __init__(self, tool_registry):
        """
        Initialize intent planner.

        Args:
            tool_registry: ToolRegistry instance
        """
        self.tool_registry = tool_registry
        self.openai_client = None
        if OPENAI_AVAILABLE and is_openai_configured():
            api_key = get_openai_api_key()
            self.openai_client = OpenAI(api_key=api_key)

    def _build_planning_prompt(
        self,
        user_message: str,
        state_snapshot: Dict[str, Any]
    ) -> str:
        """
        Build enhanced system prompt with state snapshot.

        Args:
            user_message: User's request
            state_snapshot: Current state snapshot

        Returns:
            Enhanced system prompt
        """
        base_prompt = FUNCTION_CALLING_SYSTEM_PROMPT

        # Add state snapshot context
        state_context = "\n## Current Project State\n"
        if state_snapshot.get("project_open"):
            state_context += "- Project is open\n"
            if state_snapshot.get("has_time_selection"):
                start = state_snapshot.get("selection_start_time", 0.0)
                end = state_snapshot.get("selection_end_time", 0.0)
                state_context += f"- Time selection: {start}s to {end}s\n"
            else:
                state_context += "- No time selection\n"

            cursor = state_snapshot.get("cursor_position")
            if cursor is not None:
                state_context += f"- Cursor position: {cursor}s\n"

            total_time = state_snapshot.get("total_project_time", 0.0)
            if total_time > 0:
                state_context += f"- Project duration: {total_time}s\n"

            tracks = state_snapshot.get("track_list", [])
            if tracks:
                state_context += f"- Tracks: {len(tracks)} track(s)\n"

            labels = state_snapshot.get("all_labels", [])
            if labels:
                state_context += f"- Labels: {len(labels)} label(s)\n"
        else:
            state_context += "- No project open\n"

        # Add multi-step operation examples
        examples = """

## Multi-Step Operation Examples

1. "Delete from 3:10 to 4:02"
   → set_selection_start_time(190) + set_selection_end_time(242) + delete_all_tracks_ripple

2. "Trim the last 30 seconds"
   → get_total_project_time (already done) + set_time_selection(total-30, total) + trim_to_selection

3. "Split at 12:05" or "Split at 20s"
   → **split_at_time(725)** or **split_at_time(20.0)** - Extract time from message and call directly
   → NO need for get_selected_tracks() - split_at_time works on all tracks by default

4. "Normalize this" (when selection exists)
   → Use current selection (already known) + apply_normalize

5. "Apply fade in to the first 10 seconds"
   → set_time_selection(0, 10) + apply_fade_in

6. "Balance the volume"
   → set_time_selection (if needed) + apply_compressor + apply_normalize

7. "Select the first 3 seconds of the clip"
   → get_selected_tracks() (check) + set_time_selection(0, 3) + [select_all_tracks() only if no tracks selected]
   Note: When time selection + track selection exist, clips intersecting the time range are automatically selected

8. "Select the clip" (when user wants clip selection, not just time)
   → get_selected_tracks() (check) + [select_all_tracks() only if needed] + time selection exists → clips auto-select

## Prerequisite Awareness

- Tools that require time_selection: trim_to_selection, cut, delete_selection, apply_* effects
- Tools that require selected_clips: join, duplicate_clip
- Tools that require selected_tracks: delete_track, duplicate_track
- Always check prerequisites before calling tools. Use state query tools if needed.

## Track Selection - CRITICAL RULES

**Tools that respect track selection (operate only on selected tracks):**
- trim_to_selection, cut, copy, delete_selection, split, split_at_time, silence_selection, all effect tools

**IMPORTANT - Track Selection Rules:**
1. **ALWAYS** call `get_selected_tracks()` BEFORE using tools that respect track selection
2. **If tracks are already selected**: Use them directly - do NOT call `select_all_tracks()`
3. **If no tracks selected**: Only call `select_all_tracks()` if user explicitly wants "all tracks"
4. **NEVER** automatically call `select_all()` or `select_all_tracks()` - always check existing selection first
5. **Default behavior**: Tools operate on currently selected tracks. If none selected, they do nothing.

**CRITICAL - Split Operations:**
- "Split at X seconds" or "Split at X" → **DIRECTLY call split_at_time(X)** - NO state queries needed
- `split_at_time` works on ALL tracks by default if none are selected
- Only call `get_selected_tracks()` if user explicitly wants to split only selected tracks
- **DO NOT** loop on state queries - when user provides explicit time, call `split_at_time(time)` immediately

**Examples:**
- "Trim to 4-6 seconds" → get_selected_tracks() + set_time_selection(4, 6) + trim_to_selection() (uses existing selection)
- "Split at 5 seconds" → **split_at_time(5.0)** (works on all tracks, no state query needed)
- "Split at 20s" → **split_at_time(20.0)** (extract time from message, call directly)
- "Split selected tracks at 10" → get_selected_tracks() + split_at_time(10.0) (only if user says "selected")
- "Delete selection" → get_selected_tracks() + delete_selection() (uses existing selection)
- "Trim all tracks" → select_all_tracks() + set_time_selection() + trim_to_selection() (user explicitly said "all")

## Clip Selection vs Time Selection

**Important distinction:**
- "Select the first 3 seconds" → time selection only (set_time_selection)
- "Select the first 3 seconds of the clip" → time selection + clip selection
  - Check get_selected_tracks() first
  - Set time selection
  - Only call select_all_tracks() if no tracks selected AND needed for clip selection
  - Clips intersecting the time range on selected tracks will be automatically selected

**Keywords indicating clip selection:**
- "of the clip"
- "the clip"
- "clip" (when used with selection operations)
- When user explicitly mentions "clip", they want clip selection, not just time selection
"""

        return base_prompt + state_context + examples

    def analyze_intent(
        self,
        user_message: str,
        state_snapshot: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Analyze user intent and get tool calls from LLM.

        Args:
            user_message: User's request
            state_snapshot: Current state snapshot

        Returns:
            Dictionary with 'tool_calls' (list) or 'error'
        """
        if not self.openai_client:
            return {
                "error": "OpenAI client not available",
                "tool_calls": []
            }

        try:
            # Build enhanced prompt
            system_prompt = self._build_planning_prompt(user_message, state_snapshot)

            # Call OpenAI with function calling
            response = self.openai_client.chat.completions.create(
                model=get_chat_model(),
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                tools=TOOL_DEFINITIONS,
                tool_choice="auto",
                max_tokens=1000,
                temperature=0.1
            )

            message = response.choices[0].message

            # Debug: Log what OpenAI returned
            print(f"Intent Planner - OpenAI response - tool_calls: {len(message.tool_calls) if message.tool_calls else 0}, content: {message.content[:100] if message.content else None}", file=sys.stderr)

            # Check if model wants to call tools
            if message.tool_calls:
                tool_names = [tc.function.name for tc in message.tool_calls]
                print(f"Intent Planner - OpenAI returned {len(message.tool_calls)} tool call(s): {tool_names}", file=sys.stderr)
                return {
                    "tool_calls": message.tool_calls,
                    "content": message.content
                }
            else:
                # Model returned text response (might need more state queries)
                print(f"Intent Planner - OpenAI did not return tool calls. Response: {message.content[:200] if message.content else 'None'}", file=sys.stderr)
                return {
                    "tool_calls": [],
                    "content": message.content or "I need more information to proceed."
                }

        except Exception as e:
            print(f"Error in analyze_intent: {e}", file=sys.stderr)
            return {
                "error": str(e),
                "tool_calls": []
            }

    def parse_tool_calls(
        self,
        llm_response: Dict[str, Any]
    ) -> Tuple[List[Dict[str, Any]], bool]:
        """
        Parse tool calls from LLM response.

        Args:
            llm_response: Response from analyze_intent

        Returns:
            Tuple of (tool_calls, needs_more_state)
            tool_calls: List of tool call dicts with 'tool_name' and 'arguments'
            needs_more_state: True if LLM returned state queries (loop back)
        """
        if "error" in llm_response:
            return [], False

        tool_calls = []
        needs_more_state = False

        # Check if response contains tool calls
        if "tool_calls" in llm_response:
            for tool_call in llm_response["tool_calls"]:
                tool_name = tool_call.function.name
                try:
                    arguments = json.loads(tool_call.function.arguments) if tool_call.function.arguments else {}
                except json.JSONDecodeError:
                    arguments = {}

                # Check if this is a state query
                if tool_name.startswith("get_") or tool_name == "has_time_selection" or tool_name == "action_enabled":
                    needs_more_state = True
                    # Still add to plan - state discovery will handle it
                    tool_calls.append({
                        "tool_name": tool_name,
                        "arguments": arguments,
                        "tool_call_id": getattr(tool_call, 'id', None)
                    })
                else:
                    # Regular tool call
                    tool_calls.append({
                        "tool_name": tool_name,
                        "arguments": arguments,
                        "tool_call_id": getattr(tool_call, 'id', None)
                    })

        return tool_calls, needs_more_state

    def parse_location_references(
        self,
        user_message: str,
        state_snapshot: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Parse location references from user message.

        Args:
            user_message: User's request
            state_snapshot: Current state snapshot

        Returns:
            Location information dictionary
        """
        return LocationParser.parse_location(user_message, state_snapshot)

    def plan(
        self,
        user_message: str,
        state_snapshot: Dict[str, Any]
    ) -> Tuple[List[Dict[str, Any]], bool, Optional[str]]:
        """
        Complete planning process.

        Args:
            user_message: User's request
            state_snapshot: Current state snapshot

        Returns:
            Tuple of (tool_calls, needs_more_state, error_message)
        """
        # Analyze intent with LLM
        llm_response = self.analyze_intent(user_message, state_snapshot)

        if "error" in llm_response:
            return [], False, llm_response["error"]

        # Parse tool calls
        tool_calls, needs_more_state = self.parse_tool_calls(llm_response)

        # If LLM returned text instead of tool calls, might need clarification
        if not tool_calls and llm_response.get("content"):
            # Check if content suggests we need more state
            content_lower = llm_response["content"].lower()
            if any(keyword in content_lower for keyword in ["need", "require", "check", "query"]):
                needs_more_state = True

        return tool_calls, needs_more_state, None

