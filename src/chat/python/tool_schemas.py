#!/usr/bin/env python3
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
FUNCTION_CALLING_SYSTEM_PROMPT = """You are an AI assistant that controls Audacity audio editor.

When the user asks you to perform audio editing tasks, call the appropriate tool functions. You can call multiple tools in sequence when needed.

For example:
- "trim to 2-5 seconds" → call set_time_selection with start_time=2, end_time=5, then call trim_to_selection
- "split at 3s" → call split_at_time with time=3
- "select the first 10 seconds and apply fade in" → call set_time_selection with start_time=0, end_time=10, then call apply_fade_in
- "delete from 1s to 2s" → call set_time_selection with start_time=1, end_time=2, then call delete_selection

For greetings, questions about capabilities, or general conversation, respond naturally without calling any tools.

Time parsing:
- "2s", "2 seconds", "2sec" → 2.0
- "1:30" → 90.0 (1 minute 30 seconds)
- "at 5s" → time point at 5.0 seconds
- "from X to Y" → range from X to Y
- "first N seconds" → range from 0 to N
"""
