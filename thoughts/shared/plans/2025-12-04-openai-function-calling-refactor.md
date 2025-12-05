# OpenAI Function Calling Refactor Implementation Plan

## Overview

Replace the current two-stage intent parsing + manual task mapping architecture with OpenAI's native function calling. This allows the LLM to directly specify which tools to call with what parameters, eliminating manual mapping layers and enabling automatic multi-tool "cocktail" responses.

## Current State Analysis

### Current Architecture (Two-Stage with Manual Mapping)

```
User message
    ↓
[Stage 1: LLM Intent Parsing - _parse_intent_with_llm()]
    → Sends INTENT_PARSING_PROMPT asking for JSON with intent + parameters
    → Returns: {intent: "edit", parameters: {edit_type: "trim", start_time: 2}}
    ↓
[Stage 2: Manual Task Planning - _create_task_plan()]
    → 100+ lines of if/elif chains mapping intent → task list
    → Each intent has hardcoded logic for what tools to call
    → Multi-step operations manually coded per-intent
    ↓
[Stage 3: Manual Task Execution - _execute_tasks() + _execute_*_task()]
    → Another layer of if/elif chains mapping action → tool method
    → _execute_editing_task(), _execute_track_task(), _execute_playback_task()
```

### Problems with Current Architecture

1. **Two manual mapping layers** - intent→tasks and action→tool
2. **Each new tool requires changes in 3+ places** - prompt, _create_task_plan(), _execute_*_task()
3. **Multi-step "cocktails" manually coded** - "trim to 2-5s" requires hardcoded [select, trim] sequence
4. **Parameter passing is fragile** - special cases like `split_time` vs `start_time`
5. **Trim doesn't work** because the mapping logic is incomplete

### Key Files

- `src/chat/python/orchestrator.py` - Main orchestration logic (850+ lines)
- `src/chat/python/tools.py` - Tool definitions and execution (560+ lines)
- `src/chat/python/selection_agent.py` - Selection agent
- `src/chat/python/config.py` - OpenAI configuration

## Desired End State

### New Architecture (Single-Stage, Direct Tool Calling)

```
User message
    ↓
[Single LLM call with tools=TOOL_DEFINITIONS]
    → OpenAI returns: tool_calls: [
        {name: "set_time_selection", arguments: {start_time: 2, end_time: 5}},
        {name: "trim_to_selection", arguments: {}}
      ]
    ↓
[Direct Execution Loop]
    → For each tool_call: lookup and call tools method
    → No manual mapping - tool name directly maps to method
```

### Benefits

| Before | After |
|--------|-------|
| LLM returns abstract "intent" | LLM returns exact tool names |
| WE decide what tools to call | LLM decides what tools to call |
| WE figure out multi-step chains | LLM returns multi-step chains |
| 2 manual mapping layers | 0 manual mapping layers |
| Each new tool = 3+ code changes | Each new tool = 1 schema definition |

### Verification

1. "split at 2s" → LLM returns `[{name: "split_at_time", arguments: {time: 2.0}}]`
2. "trim to 2-5 seconds" → LLM returns `[{name: "set_time_selection", arguments: {start_time: 2, end_time: 5}}, {name: "trim_to_selection", arguments: {}}]`
3. "select from 1s to 3s and apply fade in" → LLM returns `[{name: "set_time_selection", ...}, {name: "apply_fade_in", ...}]`
4. "hello" → LLM returns no tool_calls, just a conversational message
5. Missing required param → LLM asks follow-up question

## What We're NOT Doing

- Not changing the C++ side (PythonBridge, AgentActionExecutor)
- Not changing tools.py execution methods (they work fine)
- Not removing conversation handling
- Not changing the approval flow (keep it for destructive operations)
- Not adding new tools in this refactor (that comes after)

## Implementation Approach

The key insight is that `tools.py` already has all the execution methods working. We just need to:
1. Generate OpenAI-compatible tool schemas from our existing tools
2. Replace the orchestrator's two-stage flow with a single function-calling API call
3. Add a dynamic dispatcher that maps tool names to methods

---

## Phase 1: Define Tool Schemas

### Overview

Create a comprehensive `TOOL_DEFINITIONS` list in OpenAI function calling format. This becomes the single source of truth for what tools exist and what parameters they accept.

### Changes Required:

#### 1.1 Create Tool Schema Definitions

**File**: `src/chat/python/tool_schemas.py` (new file)

```python
"""
OpenAI Function Calling Tool Schemas

This file defines all available tools in OpenAI's function calling format.
Each tool maps directly to a method in tools.py.
"""

TOOL_DEFINITIONS = [
    # === Selection Tools ===
    {
        "type": "function",
        "function": {
            "name": "select_all",
            "description": "Select all audio in the project",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "clear_selection",
            "description": "Clear the current selection",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "set_time_selection",
            "description": "Set the time selection to a specific range. Use this before operations that work on a selection (trim, cut, delete, apply effects).",
            "parameters": {
                "type": "object",
                "properties": {
                    "start_time": {
                        "type": "number",
                        "description": "Start time in seconds"
                    },
                    "end_time": {
                        "type": "number",
                        "description": "End time in seconds"
                    }
                },
                "required": ["start_time", "end_time"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "select_all_tracks",
            "description": "Select all tracks in the project",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },

    # === Clip Tools ===
    {
        "type": "function",
        "function": {
            "name": "split_at_time",
            "description": "Split all tracks at a specific time point",
            "parameters": {
                "type": "object",
                "properties": {
                    "time": {
                        "type": "number",
                        "description": "Time in seconds where to split"
                    }
                },
                "required": ["time"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "split",
            "description": "Split clips at the current cursor position or selection boundaries",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "join",
            "description": "Join/merge adjacent clips",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "trim_to_selection",
            "description": "Remove all audio outside the current selection, keeping only the selected portion. Must set_time_selection first.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "silence_selection",
            "description": "Replace the selected audio with silence",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "duplicate_clip",
            "description": "Duplicate the selected clips",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },

    # === Editing Tools ===
    {
        "type": "function",
        "function": {
            "name": "cut",
            "description": "Cut the selected audio to clipboard",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "copy",
            "description": "Copy the selected audio to clipboard",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "paste",
            "description": "Paste audio from clipboard at current position",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "delete_selection",
            "description": "Delete the selected audio (does not copy to clipboard)",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "undo",
            "description": "Undo the last operation",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "redo",
            "description": "Redo the last undone operation",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },

    # === Track Tools ===
    {
        "type": "function",
        "function": {
            "name": "create_mono_track",
            "description": "Create a new mono audio track",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_stereo_track",
            "description": "Create a new stereo audio track",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "delete_track",
            "description": "Delete the currently selected track",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "duplicate_track",
            "description": "Duplicate the currently selected track",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },

    # === Effect Tools ===
    {
        "type": "function",
        "function": {
            "name": "apply_noise_reduction",
            "description": "Open the noise reduction effect dialog",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "apply_normalize",
            "description": "Open the normalize effect dialog",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "apply_amplify",
            "description": "Open the amplify effect dialog",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "apply_fade_in",
            "description": "Apply a fade in effect to the selection",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "apply_fade_out",
            "description": "Apply a fade out effect to the selection",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "apply_reverse",
            "description": "Reverse the selected audio",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "apply_invert",
            "description": "Invert/flip the selected audio waveform",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },

    # === Playback Tools ===
    {
        "type": "function",
        "function": {
            "name": "play",
            "description": "Start audio playback",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "stop",
            "description": "Stop audio playback",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "pause",
            "description": "Pause audio playback",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "rewind_to_start",
            "description": "Move playback position to the beginning",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "toggle_loop",
            "description": "Toggle loop playback mode",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
]

# System prompt for function calling
FUNCTION_CALLING_SYSTEM_PROMPT = """You are a helpful audio editing assistant for Audacity.

When the user asks you to perform audio editing tasks, use the available tools to accomplish them.
You can call multiple tools in sequence when needed.

Examples:
- "trim to 2-5 seconds" → call set_time_selection(start_time=2, end_time=5), then trim_to_selection()
- "split at 3s" → call split_at_time(time=3)
- "select the first 10 seconds and apply fade in" → call set_time_selection(start_time=0, end_time=10), then apply_fade_in()
- "delete from 1s to 2s" → call set_time_selection(start_time=1, end_time=2), then delete_selection()

For greetings, questions about capabilities, or general conversation, respond naturally without calling tools.

Time parsing:
- "2s", "2 seconds", "2sec" → 2.0
- "1:30" → 90.0 (1 minute 30 seconds)
- "at 5s" → single point at 5.0 seconds
- "from X to Y" → range from X to Y
"""
```

### Success Criteria:

#### Automated Verification:
- [x] File exists: `src/chat/python/tool_schemas.py`
- [x] Python syntax valid: `python3 -m py_compile src/chat/python/tool_schemas.py`
- [x] Imports work: `python3 -c "from tool_schemas import TOOL_DEFINITIONS; print(len(TOOL_DEFINITIONS))"` (32 tools)

#### Manual Verification:
- [ ] Review schema definitions match tools.py methods
- [ ] Descriptions are clear and helpful for LLM

---

## Phase 2: Create Tool Dispatcher

### Overview

Create a dispatcher that maps tool names to their execution methods. This replaces the manual if/elif chains in `_execute_editing_task()`, `_execute_track_task()`, etc.

### Changes Required:

#### 2.1 Add Tool Dispatcher to ToolRegistry

**File**: `src/chat/python/tools.py`
**Changes**: Add `execute_by_name()` method to `ToolRegistry` class

```python
class ToolRegistry:
    """
    Central registry for all available tools
    Provides easy access to tool categories
    """

    def __init__(self, executor: ToolExecutor):
        self.executor = executor
        self.selection = SelectionTools(executor)
        self.track = TrackTools(executor)
        self.clip = ClipTools(executor)
        self.editing = EditingTools(executor)
        self.effect = EffectTools(executor)
        self.playback = PlaybackTools(executor)

        # Build tool name -> method mapping
        self._tool_map = self._build_tool_map()

    def _build_tool_map(self) -> Dict[str, Callable]:
        """Build mapping from tool names to methods"""
        return {
            # Selection tools
            "select_all": self.selection.select_all,
            "clear_selection": self.selection.clear_selection,
            "set_time_selection": self.selection.set_time_selection,
            "select_all_tracks": self.selection.select_all_tracks,
            "select_track_start_to_cursor": self.selection.select_track_start_to_cursor,
            "select_cursor_to_track_end": self.selection.select_cursor_to_track_end,
            "select_track_start_to_end": self.selection.select_track_start_to_end,

            # Clip tools
            "split": self.clip.split,
            "split_at_time": self.clip.split_at_time,
            "join": self.clip.join,
            "duplicate_clip": self.clip.duplicate,
            "trim_to_selection": self.clip.trim_outside_selection,
            "silence_selection": self.clip.silence_selection,

            # Editing tools
            "cut": self.editing.cut,
            "copy": self.editing.copy,
            "paste": self.editing.paste,
            "delete_selection": self.editing.delete,
            "undo": self.editing.undo,
            "redo": self.editing.redo,

            # Track tools
            "create_mono_track": self.track.create_mono_track,
            "create_stereo_track": self.track.create_stereo_track,
            "delete_track": self.track.delete_track,
            "duplicate_track": self.track.duplicate_track,
            "move_track_up": self.track.move_track_up,
            "move_track_down": self.track.move_track_down,

            # Effect tools
            "apply_noise_reduction": self.effect.apply_noise_reduction,
            "apply_amplify": self.effect.apply_amplify,
            "apply_normalize": self.effect.apply_normalize,
            "apply_fade_in": self.effect.apply_fade_in,
            "apply_fade_out": self.effect.apply_fade_out,
            "apply_reverse": self.effect.apply_reverse,
            "apply_invert": self.effect.apply_invert,

            # Playback tools
            "play": self.playback.play,
            "stop": self.playback.stop,
            "pause": self.playback.pause,
            "rewind_to_start": self.playback.rewind_start,
            "toggle_loop": self.playback.toggle_loop,
        }

    def execute_by_name(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a tool by name with given arguments.

        Args:
            tool_name: Name of the tool (must match TOOL_DEFINITIONS)
            arguments: Dictionary of arguments to pass to the tool

        Returns:
            Tool execution result dict
        """
        if tool_name not in self._tool_map:
            return {
                "success": False,
                "error": f"Unknown tool: {tool_name}"
            }

        method = self._tool_map[tool_name]

        try:
            # Call method with arguments (unpacked as kwargs)
            if arguments:
                return method(**arguments)
            else:
                return method()
        except TypeError as e:
            return {
                "success": False,
                "error": f"Invalid arguments for {tool_name}: {str(e)}"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Tool execution failed: {str(e)}"
            }

    def get_available_tools(self) -> List[str]:
        """Get list of available tool names"""
        return list(self._tool_map.keys())
```

### Success Criteria:

#### Automated Verification:
- [x] Python syntax valid: `python3 -m py_compile src/chat/python/tools.py`
- [x] Tool map builds without error (37 tools)
- [x] `execute_by_name("split_at_time", {"time": 2.0})` returns valid result structure

#### Manual Verification:
- [ ] All tool names in `_tool_map` match `TOOL_DEFINITIONS`
- [ ] No duplicate tool names

---

## Phase 3: Refactor Orchestrator to Use Function Calling

### Overview

Replace `_parse_intent_with_llm()` + `_create_task_plan()` + `_execute_tasks()` with a single function-calling flow.

### Changes Required:

#### 3.1 Update Orchestrator Imports and Init

**File**: `src/chat/python/orchestrator.py`
**Changes**: Add imports and update initialization

```python
# At top of file, add import:
from tool_schemas import TOOL_DEFINITIONS, FUNCTION_CALLING_SYSTEM_PROMPT
```

#### 3.2 Replace Core Processing Logic

**File**: `src/chat/python/orchestrator.py`
**Changes**: Replace `process_request()` method

```python
def process_request(self, user_message: str) -> Dict[str, Any]:
    """
    Process user request using OpenAI function calling.
    """
    try:
        # Add to conversation history
        self.conversation_history.append({"role": "user", "content": user_message})

        # Limit history
        if len(self.conversation_history) > 20:
            self.conversation_history = self.conversation_history[-20:]

        # If no OpenAI client, use fallback
        if not self.openai_client:
            return self._process_without_llm(user_message)

        # Call OpenAI with function calling
        response = self.openai_client.chat.completions.create(
            model=get_chat_model(),
            messages=[
                {"role": "system", "content": FUNCTION_CALLING_SYSTEM_PROMPT},
                *self.conversation_history
            ],
            tools=TOOL_DEFINITIONS,
            tool_choice="auto",  # Let model decide whether to use tools
            max_tokens=1000,
            temperature=0.1
        )

        message = response.choices[0].message

        # Check if model wants to call tools
        if message.tool_calls:
            return self._execute_tool_calls(message.tool_calls, user_message)
        else:
            # Pure conversation response
            response_text = message.content or "I'm not sure how to help with that."
            self.conversation_history.append({"role": "assistant", "content": response_text})
            return {
                "type": "message",
                "content": response_text,
                "can_undo": False
            }

    except Exception as e:
        print(f"Error in process_request: {e}", file=sys.stderr)
        return {
            "type": "error",
            "content": f"Error processing request: {str(e)}"
        }

def _execute_tool_calls(self, tool_calls: List, user_message: str) -> Dict[str, Any]:
    """
    Execute a list of tool calls from the LLM.
    """
    results = []
    tool_descriptions = []
    requires_approval = False

    # Check if any tools require approval
    destructive_tools = {"cut", "delete_selection", "delete_track", "trim_to_selection"}
    effect_tools = {"apply_noise_reduction", "apply_normalize", "apply_amplify",
                    "apply_fade_in", "apply_fade_out", "apply_reverse", "apply_invert"}

    for tool_call in tool_calls:
        tool_name = tool_call.function.name
        if tool_name in destructive_tools or tool_name in effect_tools:
            requires_approval = True
            break

    # Build task plan for approval flow
    task_plan = []
    for tool_call in tool_calls:
        tool_name = tool_call.function.name
        try:
            arguments = json.loads(tool_call.function.arguments) if tool_call.function.arguments else {}
        except json.JSONDecodeError:
            arguments = {}

        task_plan.append({
            "tool_name": tool_name,
            "arguments": arguments,
            "tool_call_id": tool_call.id
        })
        tool_descriptions.append(f"{tool_name}({arguments})")

    # If requires approval, return approval request
    if requires_approval:
        approval_id = self._generate_approval_id()
        return {
            "type": "approval_request",
            "approval_id": approval_id,
            "description": f"Execute: {', '.join(tool_descriptions)}",
            "preview": " → ".join(tool_descriptions),
            "task_plan": task_plan,
            "approval_mode": "batch",
            "current_step": None,
            "total_steps": len(task_plan)
        }

    # Execute tools directly
    for task in task_plan:
        tool_name = task["tool_name"]
        arguments = task["arguments"]

        print(f"Executing tool: {tool_name}({arguments})", file=sys.stderr)
        result = self.tools.execute_by_name(tool_name, arguments)
        results.append({
            "tool_name": tool_name,
            "result": result
        })

    # Generate response
    all_success = all(r["result"].get("success", False) for r in results)

    if all_success:
        response_text = f"Done! Executed: {', '.join(tool_descriptions)}"
        can_undo = True
    else:
        errors = [f"{r['tool_name']}: {r['result'].get('error', 'unknown')}"
                  for r in results if not r["result"].get("success", False)]
        response_text = f"Completed with errors: {'; '.join(errors)}"
        can_undo = False

    self.conversation_history.append({"role": "assistant", "content": response_text})

    return {
        "type": "message",
        "content": response_text,
        "can_undo": can_undo
    }

def _process_without_llm(self, user_message: str) -> Dict[str, Any]:
    """
    Fallback processing when OpenAI is not available.
    Uses simple keyword matching.
    """
    # Keep existing keyword-based fallback for when OpenAI isn't configured
    msg_lower = user_message.lower()

    # Simple keyword-based tool selection
    if "play" in msg_lower:
        result = self.tools.execute_by_name("play", {})
    elif "stop" in msg_lower:
        result = self.tools.execute_by_name("stop", {})
    elif "pause" in msg_lower:
        result = self.tools.execute_by_name("pause", {})
    elif "undo" in msg_lower:
        result = self.tools.execute_by_name("undo", {})
    elif "redo" in msg_lower:
        result = self.tools.execute_by_name("redo", {})
    else:
        return {
            "type": "message",
            "content": "OpenAI API key not configured. Only basic commands (play, stop, pause, undo, redo) are available.",
            "can_undo": False
        }

    success = result.get("success", False)
    return {
        "type": "message",
        "content": "Done!" if success else f"Error: {result.get('error', 'unknown')}",
        "can_undo": success
    }
```

#### 3.3 Update Approval Processing

**File**: `src/chat/python/orchestrator.py`
**Changes**: Update `process_approval()` to work with new task_plan format

```python
def process_approval(self, approval_id: str, approved: bool, task_plan: List[Dict[str, Any]] = None,
                    approval_mode: str = "batch", current_step: int = 0, batch_mode: bool = False) -> Dict[str, Any]:
    """
    Process approval response and execute tools if approved.
    """
    if not approved:
        return {
            "type": "message",
            "content": "Operation cancelled."
        }

    if not task_plan:
        return {
            "type": "error",
            "content": "No task plan provided for approved operation"
        }

    # Execute all tools in the plan
    results = []
    tool_descriptions = []

    for task in task_plan:
        tool_name = task["tool_name"]
        arguments = task.get("arguments", {})

        print(f"Executing approved tool: {tool_name}({arguments})", file=sys.stderr)
        result = self.tools.execute_by_name(tool_name, arguments)
        results.append({
            "tool_name": tool_name,
            "result": result
        })
        tool_descriptions.append(tool_name)

    # Generate response
    all_success = all(r["result"].get("success", False) for r in results)

    if all_success:
        response_text = f"Completed: {', '.join(tool_descriptions)}"
    else:
        errors = [f"{r['tool_name']}: {r['result'].get('error', 'unknown')}"
                  for r in results if not r["result"].get("success", False)]
        response_text = f"Completed with errors: {'; '.join(errors)}"

    return {
        "type": "message",
        "content": response_text,
        "can_undo": all_success
    }
```

#### 3.4 Remove Obsolete Code

**File**: `src/chat/python/orchestrator.py`
**Changes**: Remove or mark as deprecated:

- `INTENT_PARSING_PROMPT` constant (replaced by `FUNCTION_CALLING_SYSTEM_PROMPT`)
- `Intent` enum (no longer needed)
- `_parse_intent_with_llm()` method
- `_parse_intent()` method
- `_create_task_plan()` method
- `_execute_tasks()` method
- `_execute_editing_task()` method
- `_execute_track_task()` method
- `_execute_playback_task()` method
- `_extract_selection_params()` method
- `_extract_effect_name()` method
- `_extract_edit_type()` method
- `_extract_playback_action()` method

Keep:
- `_generate_approval_id()`
- `_generate_conversational_response()` (for edge cases)
- `conversation_history` management

### Success Criteria:

#### Automated Verification:
- [x] Python syntax valid: `python3 -m py_compile src/chat/python/orchestrator.py`
- [x] No import errors when loading module
- [x] Agent service starts without errors

#### Manual Verification:
- [ ] "split at 2s" → executes split_at_time(time=2.0)
- [ ] "trim to 2-5 seconds" → executes set_time_selection + trim_to_selection
- [ ] "hello" → returns conversational response, no tools called
- [ ] "cut this" on destructive action → shows approval request
- [ ] Approval flow works correctly

---

## Phase 4: Clean Up and Polish

### Overview

Remove unused code, update error handling, and ensure all edge cases are covered.

### Changes Required:

#### 4.1 Simplify OrchestratorAgent Init

**File**: `src/chat/python/orchestrator.py`
**Changes**: Remove unused agent parameters

```python
class OrchestratorAgent:
    def __init__(self, tools):
        """
        Initialize orchestrator with tool registry.

        Args:
            tools: ToolRegistry instance
        """
        self.tools = tools
        self.conversation_history: List[Dict[str, str]] = []

        # Initialize OpenAI client if available
        self.openai_client = None
        if OPENAI_AVAILABLE and is_openai_configured():
            api_key = get_openai_api_key()
            self.openai_client = OpenAI(api_key=api_key)
            print("OpenAI client initialized for function calling", file=sys.stderr)
```

#### 4.2 Update agent_service.py

**File**: `src/chat/python/agent_service.py`
**Changes**: Update initialization to match new signature

```python
# Remove selection_agent and effect_agent if they're no longer needed
# Update orchestrator initialization:
orchestrator = OrchestratorAgent(tools=tools)
```

#### 4.3 Remove Unused Agent Files (if applicable)

If `selection_agent.py` and `effect_agent.py` are no longer needed after this refactor, they can be removed or kept for potential future use.

### Success Criteria:

#### Automated Verification:
- [x] `python3 src/chat/python/agent_service.py` starts without errors
- [x] No unused imports warnings
- [ ] All tests pass (if any exist)

#### Manual Verification:
- [ ] Full workflow test: "select 0-5s, apply fade in, then trim"
- [ ] Error handling: invalid tool name, missing params
- [ ] Conversation mode still works
- [ ] Approval flow for destructive operations

---

## Testing Strategy

### Unit Tests:
- Tool schema validation (all tools have required fields)
- Tool dispatcher mapping (all schema names map to methods)
- Argument validation (required params enforced)

### Integration Tests:
- End-to-end: user message → tool execution → result
- Multi-tool chains: "trim to 2-5s" → [set_selection, trim]
- Conversation fallback: "hello" → no tools, conversational response

### Manual Testing Steps:
1. Start Audacity with chat module
2. Test single-tool commands:
   - "split at 3 seconds"
   - "play"
   - "undo"
3. Test multi-tool chains:
   - "trim to 2-5 seconds"
   - "select 0-10s and apply fade in"
   - "delete from 1s to 2s"
4. Test conversation:
   - "hello"
   - "what can you do?"
   - "thanks"
5. Test approval flow:
   - "cut this" → should request approval
   - Approve → should execute
   - Deny → should cancel

## Performance Considerations

- Single API call instead of intent + planning = faster response
- Tool schemas are static, loaded once at startup
- Tool dispatcher uses dict lookup = O(1) vs if/elif chains

## Migration Notes

- No database changes required
- No C++ changes required
- Python-only refactor
- Backward compatible: approval flow preserved

## References

- OpenAI Function Calling docs: https://platform.openai.com/docs/guides/function-calling
- Current orchestrator: `src/chat/python/orchestrator.py`
- Current tools: `src/chat/python/tools.py`
