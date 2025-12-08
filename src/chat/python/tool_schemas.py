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
            "name": "set_selection_start_time",
            "description": "Set only the start time of the selection. Use this to adjust the beginning of an existing selection.",
            "parameters": {
                "type": "object",
                "properties": {
                    "time": {
                        "type": "number",
                        "description": "Start time in seconds"
                    }
                },
                "required": ["time"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "set_selection_end_time",
            "description": "Set only the end time of the selection. Use this to adjust the end of an existing selection.",
            "parameters": {
                "type": "object",
                "properties": {
                    "time": {
                        "type": "number",
                        "description": "End time in seconds"
                    }
                },
                "required": ["time"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "reset_selection",
            "description": "Reset/clear the time selection. Same as clear_selection but specifically for time selection.",
            "parameters": {"type": "object", "properties": {}, "required": []}
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
            "description": "Split all tracks at a specific time. Works on all tracks.",
            "parameters": {
                "type": "object",
                "properties": {
                    "time": {
                        "type": "number",
                        "description": "Time in seconds where to split (e.g., '20s' → 20.0, '1:30' → 90.0)"
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
            "description": "Split at the cursor position. If time selection exists, splits at both start and end.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "join",
            "description": "Join/merge adjacent clips into one.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "trim_to_selection",
            "description": "Keep only the audio within a time range, removing everything outside it.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "silence_selection",
            "description": "Replace the audio in a time range with silence.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "duplicate_clip",
            "description": "Duplicate the selected clips.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },

    # === Editing Tools ===
    {
        "type": "function",
        "function": {
            "name": "cut",
            "description": "Cut the audio in a time range to clipboard.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "copy",
            "description": "Copy the audio in a time range to clipboard.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "paste",
            "description": "Paste audio from clipboard at the cursor position.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "delete_selection",
            "description": "Delete audio in a time range (does not copy to clipboard).",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "delete_all_tracks_ripple",
            "description": "Delete audio in a time range across all tracks with ripple (shifts remaining audio to fill gap).",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "cut_all_tracks_ripple",
            "description": "Cut audio in a time range across all tracks to clipboard with ripple.",
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
            "description": "Create a new mono audio track.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_stereo_track",
            "description": "Create a new stereo audio track.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "delete_track",
            "description": "Delete the selected track.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "duplicate_track",
            "description": "Duplicate the selected track.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "move_track_to_top",
            "description": "Move the selected track to the top of the track list.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "move_track_to_bottom",
            "description": "Move the selected track to the bottom of the track list.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },

    # === Effect Tools ===
    {
        "type": "function",
        "function": {
            "name": "apply_noise_reduction",
            "description": "Apply noise reduction to audio.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "apply_normalize",
            "description": "Normalize audio levels to a target peak.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "apply_amplify",
            "description": "Amplify or reduce audio volume.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "apply_fade_in",
            "description": "Apply a fade in effect to the audio.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "apply_fade_out",
            "description": "Apply a fade out effect to the audio.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "apply_reverse",
            "description": "Reverse the audio.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "apply_invert",
            "description": "Invert/flip the audio waveform.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "apply_normalize_loudness",
            "description": "Normalize audio loudness to a standard level (LUFS).",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "apply_compressor",
            "description": "Apply dynamic range compression to audio.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "apply_limiter",
            "description": "Apply a limiter to prevent peaks from exceeding a threshold.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "apply_truncate_silence",
            "description": "Remove or shorten silence periods in audio.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "repeat_last_effect",
            "description": "Repeat the last applied effect with the same settings.",
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
            "name": "seek",
            "description": "Move the playhead/cursor to a specific time position. This is where playback will start or where paste operations will insert.",
            "parameters": {
                "type": "object",
                "properties": {
                    "time": {
                        "type": "number",
                        "description": "Time in seconds to move the playhead to"
                    }
                },
                "required": ["time"]
            }
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

    # === Label Tools ===
    {
        "type": "function",
        "function": {
            "name": "create_label_track",
            "description": "Create a new label track for marking points or regions.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "add_label",
            "description": "Add a label at the cursor or selection.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },

    # === State Query Tools ===
    {
        "type": "function",
        "function": {
            "name": "get_selection_start_time",
            "description": "Get the start time of the current selection in seconds. Returns 0.0 if no selection exists.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_selection_end_time",
            "description": "Get the end time of the current selection in seconds. Returns 0.0 if no selection exists.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "has_time_selection",
            "description": "Check if there is currently a time selection. Use this before operations that require a selection.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_selected_tracks",
            "description": "Get a list of currently selected track IDs. Returns empty list if no tracks are selected.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_selected_clips",
            "description": "Get a list of currently selected clip keys. Each clip has a track_id and clip_id. Returns empty list if no clips are selected.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_cursor_position",
            "description": "Get the current cursor/playhead position in seconds. This is where playback will start or where paste operations will insert.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_total_project_time",
            "description": "Get the total duration of the project in seconds. Useful for calculating relative times like 'last 30 seconds'.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_track_list",
            "description": "Get a list of all tracks in the project. Each track has track_id, name, and type.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_clips_on_track",
            "description": "Get a list of all clips on a specific track. Use this to inspect track contents.",
            "parameters": {
                "type": "object",
                "properties": {
                    "track_id": {
                        "type": "string",
                        "description": "The track ID to query"
                    }
                },
                "required": ["track_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_all_labels",
            "description": "Get all label track data. Returns empty list if no label tracks exist.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "action_enabled",
            "description": "Check if a specific action is currently enabled. Use this to verify if an operation can be performed.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action_code": {
                        "type": "string",
                        "description": "The action code to check (e.g., 'action://trackedit/undo')"
                    }
                },
                "required": ["action_code"]
            }
        }
    },

    # === Transcription Tools ===
    {
        "type": "function",
        "function": {
            "name": "transcribe_audio",
            "description": "Transcribe the project audio to text with word-level timestamps. Preserves filler words (um, uh, like, etc.) for identification. Returns full transcript with timing for each word. Use this before searching for specific words or finding filler words.",
            "parameters": {
                "type": "object",
                "properties": {
                    "enable_diarization": {
                        "type": "boolean",
                        "description": "Enable speaker diarization to identify different speakers. Default false."
                    },
                    "language": {
                        "type": "string",
                        "description": "Language code for transcription (default: 'en')"
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_transcript",
            "description": "Search the transcript for a word or phrase. Returns all occurrences with timestamps. Must call transcribe_audio first.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Word or phrase to search for"
                    },
                    "case_sensitive": {
                        "type": "boolean",
                        "description": "Whether search is case-sensitive. Default false."
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "find_filler_words",
            "description": "Find all filler words (um, uh, like, you know, actually, basically, etc.) in the transcript. Returns locations with timestamps and summary statistics. Must call transcribe_audio first.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_transcript",
            "description": "Analyze the transcript and provide AI-generated editorial feedback on filler words, pacing, clarity, and suggestions for improvement. Returns narrative with timestamps and statistics. If no transcript exists, call transcribe_audio first, then analyze_transcript. When user asks to 'analyze transcript', 'analyze the transcript', 'get feedback on transcript', or similar, call this tool directly.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
]

# Tool Prerequisites (DEPRECATED - see state_contracts.py for ground truth)
# This dictionary is kept for backward compatibility with prerequisite_resolver.py.
# The new State Preparation system (state_contracts.py, state_gap_analyzer.py,
# value_inference.py, state_preparation.py) is now the primary mechanism for
# handling tool prerequisites.
#
# Values:
#   True = Required (tool will fail if prerequisite not met)
#   False = Optional (tool may work differently or have limited functionality)
#   None = Not applicable (prerequisite doesn't apply to this tool)
TOOL_PREREQUISITES = {
    # === Selection Tools ===
    "set_time_selection": {
        "project_open": True,  # Always required
        "time_selection": None,
        "selected_clips": None,
        "selected_tracks": None,
        "cursor_position": False,  # Optional, can use cursor if no times provided
    },
    "set_selection_start_time": {
        "project_open": True,
        "time_selection": None,
        "selected_clips": None,
        "selected_tracks": None,
        "cursor_position": None,
    },
    "set_selection_end_time": {
        "project_open": True,
        "time_selection": None,
        "selected_clips": None,
        "selected_tracks": None,
        "cursor_position": None,
    },
    "select_all": {
        "project_open": True,
        "time_selection": None,
        "selected_clips": None,
        "selected_tracks": None,
        "cursor_position": None,
    },
    "clear_selection": {
        "project_open": True,  # Optional, can work without project
        "time_selection": False,  # Optional, can clear even if no selection
        "selected_clips": False,
        "selected_tracks": False,
        "cursor_position": None,
    },
    "reset_selection": {
        "project_open": True,  # Optional, can work without project
        "time_selection": False,  # Optional, can reset even if no selection
        "selected_clips": False,
        "selected_tracks": False,
        "cursor_position": None,
    },
    "select_all_tracks": {
        "project_open": True,
        "time_selection": None,
        "selected_clips": None,
        "selected_tracks": None,
        "cursor_position": None,
    },

    # === Clip Tools ===
    "split_at_time": {
        "project_open": True,
        "time_selection": None,
        "selected_clips": None,
        "selected_tracks": None,
        "cursor_position": None,
    },
    "split": {
        "project_open": True,
        "time_selection": False,  # Optional, can split at cursor
        "selected_clips": False,  # Optional, can split selected clips
        "selected_tracks": None,  # Uses UI track selection (always has at least one track selected)
        "cursor_position": False,  # Optional, can split at cursor
    },
    "join": {
        "project_open": True,
        "time_selection": None,
        "selected_clips": True,  # Required, needs clips to join
        "selected_tracks": None,
        "cursor_position": None,
    },
    "trim_to_selection": {
        "project_open": True,
        "time_selection": True,  # Required, needs selection to trim
        "selected_clips": None,
        "selected_tracks": None,
        "cursor_position": None,
    },
    "silence_selection": {
        "project_open": True,
        "time_selection": True,  # Required, needs selection to silence
        "selected_clips": None,
        "selected_tracks": None,
        "cursor_position": None,
    },
    "duplicate_clip": {
        "project_open": True,
        "time_selection": None,
        "selected_clips": True,  # Required, needs clips to duplicate
        "selected_tracks": None,
        "cursor_position": None,
    },

    # === Editing Tools ===
    "cut": {
        "project_open": True,
        "time_selection": True,  # Required, needs selection to cut
        "selected_clips": None,
        "selected_tracks": None,
        "cursor_position": None,
    },
    "cut_all_tracks_ripple": {
        "project_open": True,
        "time_selection": True,  # Required, needs selection to cut
        "selected_clips": None,
        "selected_tracks": None,
        "cursor_position": None,
    },
    "copy": {
        "project_open": True,
        "time_selection": True,  # Required, needs selection to copy
        "selected_clips": None,
        "selected_tracks": None,
        "cursor_position": None,
    },
    "paste": {
        "project_open": True,
        "time_selection": None,
        "selected_clips": None,
        "selected_tracks": None,
        "cursor_position": False,  # Optional, uses cursor if available
    },
    "delete_selection": {
        "project_open": True,
        "time_selection": True,  # Required, needs selection to delete
        "selected_clips": None,
        "selected_tracks": None,
        "cursor_position": None,
    },
    "delete_all_tracks_ripple": {
        "project_open": True,
        "time_selection": True,  # Required, needs selection to delete
        "selected_clips": None,
        "selected_tracks": None,
        "cursor_position": None,
    },
    "undo": {
        "project_open": True,
        "time_selection": None,
        "selected_clips": None,
        "selected_tracks": None,
        "cursor_position": None,
        # Note: undo_history is checked via action_enabled, not a prerequisite
    },
    "redo": {
        "project_open": True,
        "time_selection": None,
        "selected_clips": None,
        "selected_tracks": None,
        "cursor_position": None,
        # Note: redo_history is checked via action_enabled, not a prerequisite
    },

    # === Track Tools ===
    "create_mono_track": {
        "project_open": True,
        "time_selection": None,
        "selected_clips": None,
        "selected_tracks": None,
        "cursor_position": None,
    },
    "create_stereo_track": {
        "project_open": True,
        "time_selection": None,
        "selected_clips": None,
        "selected_tracks": None,
        "cursor_position": None,
    },
    "delete_track": {
        "project_open": True,
        "time_selection": None,
        "selected_clips": None,
        "selected_tracks": True,  # Required, needs tracks to delete
        "cursor_position": None,
    },
    "duplicate_track": {
        "project_open": True,
        "time_selection": None,
        "selected_clips": None,
        "selected_tracks": True,  # Required, needs tracks to duplicate
        "cursor_position": None,
    },
    "move_track_to_top": {
        "project_open": True,
        "time_selection": None,
        "selected_clips": None,
        "selected_tracks": True,  # Required, needs tracks to move
        "cursor_position": None,
    },
    "move_track_to_bottom": {
        "project_open": True,
        "time_selection": None,
        "selected_clips": None,
        "selected_tracks": True,  # Required, needs tracks to move
        "cursor_position": None,
    },

    # === Effect Tools ===
    "apply_noise_reduction": {
        "project_open": True,
        "time_selection": True,  # Required, needs selection for noise reduction
        "selected_clips": None,
        "selected_tracks": None,
        "cursor_position": None,
    },
    "apply_normalize": {
        "project_open": True,
        "time_selection": True,  # Required, needs selection to normalize
        "selected_clips": None,
        "selected_tracks": None,
        "cursor_position": None,
    },
    "apply_normalize_loudness": {
        "project_open": True,
        "time_selection": True,  # Required, needs selection to normalize loudness
        "selected_clips": None,
        "selected_tracks": None,
        "cursor_position": None,
    },
    "apply_compressor": {
        "project_open": True,
        "time_selection": True,  # Required, needs selection to apply compressor
        "selected_clips": None,
        "selected_tracks": None,
        "cursor_position": None,
    },
    "apply_limiter": {
        "project_open": True,
        "time_selection": True,  # Required, needs selection to apply limiter
        "selected_clips": None,
        "selected_tracks": None,
        "cursor_position": None,
    },
    "apply_truncate_silence": {
        "project_open": True,
        "time_selection": True,  # Required, needs selection to truncate silence
        "selected_clips": None,
        "selected_tracks": None,
        "cursor_position": None,
    },
    "apply_amplify": {
        "project_open": True,
        "time_selection": True,  # Required, needs selection to amplify
        "selected_clips": None,
        "selected_tracks": None,
        "cursor_position": None,
    },
    "apply_fade_in": {
        "project_open": True,
        "time_selection": True,  # Required, needs selection for fade in
        "selected_clips": None,
        "selected_tracks": None,
        "cursor_position": None,
    },
    "apply_fade_out": {
        "project_open": True,
        "time_selection": True,  # Required, needs selection for fade out
        "selected_clips": None,
        "selected_tracks": None,
        "cursor_position": None,
    },
    "apply_reverse": {
        "project_open": True,
        "time_selection": True,  # Required, needs selection to reverse
        "selected_clips": None,
        "selected_tracks": None,
        "cursor_position": None,
    },
    "apply_invert": {
        "project_open": True,
        "time_selection": True,  # Required, needs selection to invert
        "selected_clips": None,
        "selected_tracks": None,
        "cursor_position": None,
    },
    "repeat_last_effect": {
        "project_open": True,
        "time_selection": True,  # Required, needs selection to apply effect
        "selected_clips": None,
        "selected_tracks": None,
        "cursor_position": None,
        # Note: previous effect is checked via action_enabled, not a prerequisite
    },

    # === Playback Tools ===
    "play": {
        "project_open": True,
        "time_selection": None,
        "selected_clips": None,
        "selected_tracks": None,
        "cursor_position": None,
    },
    "stop": {
        "project_open": True,
        "time_selection": None,
        "selected_clips": None,
        "selected_tracks": None,
        "cursor_position": None,
        # Note: playback_active is checked via action_enabled, not a prerequisite
    },
    "pause": {
        "project_open": True,
        "time_selection": None,
        "selected_clips": None,
        "selected_tracks": None,
        "cursor_position": None,
        # Note: playback_active is checked via action_enabled, not a prerequisite
    },
    "seek": {
        "project_open": True,
        "time_selection": None,
        "selected_clips": None,
        "selected_tracks": None,
        "cursor_position": None,
    },
    "rewind_to_start": {
        "project_open": True,
        "time_selection": None,
        "selected_clips": None,
        "selected_tracks": None,
        "cursor_position": None,
    },
    "toggle_loop": {
        "project_open": True,
        "time_selection": None,
        "selected_clips": None,
        "selected_tracks": None,
        "cursor_position": None,
    },

    # === State Query Tools ===
    # State query tools don't have prerequisites (they're used to check state)
    "get_selection_start_time": {
        "project_open": True,  # Optional, returns 0.0 if no project
        "time_selection": None,
        "selected_clips": None,
        "selected_tracks": None,
        "cursor_position": None,
    },
    "get_selection_end_time": {
        "project_open": True,  # Optional, returns 0.0 if no project
        "time_selection": None,
        "selected_clips": None,
        "selected_tracks": None,
        "cursor_position": None,
    },
    "has_time_selection": {
        "project_open": True,  # Optional, returns False if no project
        "time_selection": None,
        "selected_clips": None,
        "selected_tracks": None,
        "cursor_position": None,
    },
    "get_selected_tracks": {
        "project_open": True,  # Optional, returns empty list if no project
        "time_selection": None,
        "selected_clips": None,
        "selected_tracks": None,
        "cursor_position": None,
    },
    "get_selected_clips": {
        "project_open": True,  # Optional, returns empty list if no project
        "time_selection": None,
        "selected_clips": None,
        "selected_tracks": None,
        "cursor_position": None,
    },
    "get_cursor_position": {
        "project_open": True,  # Optional, returns 0.0 if no project
        "time_selection": None,
        "selected_clips": None,
        "selected_tracks": None,
        "cursor_position": None,
    },
    "get_total_project_time": {
        "project_open": True,  # Optional, returns 0.0 if no project
        "time_selection": None,
        "selected_clips": None,
        "selected_tracks": None,
        "cursor_position": None,
    },
    "get_track_list": {
        "project_open": True,  # Optional, returns empty list if no project
        "time_selection": None,
        "selected_clips": None,
        "selected_tracks": None,
        "cursor_position": None,
    },
    "get_clips_on_track": {
        "project_open": True,  # Optional, returns empty list if no project
        "time_selection": None,
        "selected_clips": None,
        "selected_tracks": None,
        "cursor_position": None,
    },
    "get_all_labels": {
        "project_open": True,  # Optional, returns empty list if no project
        "time_selection": None,
        "selected_clips": None,
        "selected_tracks": None,
        "cursor_position": None,
    },
    "action_enabled": {
        "project_open": True,  # Optional, returns False if no project
        "time_selection": None,
        "selected_clips": None,
        "selected_tracks": None,
        "cursor_position": None,
    },

    # === Label Tools ===
    "create_label_track": {
        "project_open": True,
        "time_selection": None,
        "selected_clips": None,
        "selected_tracks": None,
        "cursor_position": None,
    },
    "add_label": {
        "project_open": True,
        "time_selection": False,  # Optional, can add label at cursor or selection
        "selected_clips": None,
        "selected_tracks": None,
        "cursor_position": False,  # Optional, can add label at cursor
    },
}

# System prompt for function calling
# Note: The State Preparation system now handles prerequisite setup automatically.
# This simplified prompt focuses on intent parsing - the backend handles state prep.
FUNCTION_CALLING_SYSTEM_PROMPT = """You are an AI assistant that controls Audacity audio editor.

When the user asks you to perform audio editing tasks, call the appropriate tool functions.

## Core Principle: Just State the Intent

You don't need to worry about prerequisites or state setup - the backend will automatically:
1. Detect what state is needed for each operation
2. Infer values from the user's message (time references, track mentions)
3. Set up the required state (selections, cursor position)
4. Execute the operation

Simply call the tool that matches what the user wants to do.

## Time Parsing

Parse time values from user messages:
- "20s", "20 seconds" → 20.0
- "1:30" → 90.0 (1 minute 30 seconds)
- "first 30 seconds" → start=0.0, end=30.0
- "last 10 seconds" → needs project duration, backend will calculate
- "from 10 to 20" → start=10.0, end=20.0

## Examples

**"Split at 20 seconds"**
→ Call `split_at_time(time=20.0)`

**"Trim first 30 seconds"**
→ Call `trim_to_selection()`
(Backend infers: set selection 0-30s, select all tracks, then trim)

**"Delete from 1:00 to 2:00"**
→ Call `delete_selection()`
(Backend infers: set selection 60-120s, then delete)

**"Normalize the audio"**
→ Call `apply_normalize()`
(Backend will set up selection if needed)

**"Play"**
→ Call `play()`

## State Query Tools (When Needed)

Use these only when the user asks about the current state:
- `has_time_selection()` - Check if a selection exists
- `get_cursor_position()` - Get playhead position
- `get_total_project_time()` - Get project duration
- `get_track_list()` - List all tracks
- `get_selected_tracks()` - List selected tracks

For greetings, questions about capabilities, or general conversation, respond naturally without calling tools.
"""
