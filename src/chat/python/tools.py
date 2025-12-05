#!/usr/bin/env python3
"""
Tool execution wrapper for Python agents
Provides a Python-friendly interface to C++ actions
"""

import json
import sys
import threading
import queue
from typing import Dict, Any, Optional, List, Callable
from enum import Enum


class ToolCategory(Enum):
    """Categories of tools"""
    SELECTION = "selection"
    TRACK = "track"
    CLIP = "clip"
    EDITING = "editing"
    EFFECT = "effect"
    PLAYBACK = "playback"
    LABEL = "label"
    VIEW = "view"
    STATE = "state"


class ToolExecutor:
    """
    Executes tools by sending requests to C++ via stdin/stdout.
    Uses a message queue pattern to avoid blocking deadlocks.

    The stdin reader thread reads all incoming messages and routes them:
    - tool_result messages -> directly to pending call events
    - other messages -> to message_queue for main loop processing
    """

    def __init__(self, stdout=sys.stdout):
        self.stdout = stdout
        self._pending_calls: Dict[str, tuple] = {}  # call_id -> (event, result)
        self._call_counter = 0
        self._lock = threading.Lock()

        # Message queue for non-tool-result messages
        self.message_queue: queue.Queue = queue.Queue()

        # Reader thread (will be started by start_reader)
        self._reader_thread: Optional[threading.Thread] = None
        self._stop_reader = threading.Event()

    def start_reader(self, stdin=sys.stdin):
        """Start the background stdin reader thread"""
        if self._reader_thread is not None:
            return  # Already running

        self._stop_reader.clear()
        self._reader_thread = threading.Thread(
            target=self._reader_loop,
            args=(stdin,),
            daemon=True
        )
        self._reader_thread.start()

    def stop_reader(self):
        """Stop the background stdin reader thread"""
        self._stop_reader.set()
        if self._reader_thread:
            self._reader_thread.join(timeout=1.0)
            self._reader_thread = None

    def _reader_loop(self, stdin):
        """
        Background thread that reads stdin and routes messages.
        - tool_result -> signals pending call
        - other messages -> puts in message_queue
        """
        for line in stdin:
            if self._stop_reader.is_set():
                break

            try:
                request = json.loads(line.strip())
                request_type = request.get("type")

                if request_type == "tool_result":
                    # Route tool results directly to pending calls
                    result = request.get("result", {})
                    self._handle_tool_result(result)
                else:
                    # Put other messages in queue for main loop
                    self.message_queue.put(request)

            except json.JSONDecodeError:
                # Ignore non-JSON lines (like debug output)
                pass
            except Exception:
                # Don't crash the reader thread
                pass

    def _generate_call_id(self) -> str:
        """Generate unique call ID"""
        self._call_counter += 1
        return f"call_{self._call_counter}"

    def _send_tool_call(self, tool_name: str, action_code: str, parameters: Dict[str, Any]) -> str:
        """Send tool call request to C++ and return call_id"""
        call_id = self._generate_call_id()

        request = {
            "type": "tool_call",
            "call_id": call_id,
            "tool_name": tool_name,
            "action_code": action_code,
            "parameters": parameters
        }

        # Write to stdout (C++ reads from Python's stdout)
        json_str = json.dumps(request) + "\n"
        self.stdout.write(json_str)
        self.stdout.flush()

        return call_id

    def _wait_for_result(self, call_id: str, timeout: float = 150.0) -> Dict[str, Any]:
        """
        Wait for tool result from C++.
        The reader thread will signal when result arrives.
        """
        # Create event for this call
        event = threading.Event()
        with self._lock:
            self._pending_calls[call_id] = (event, None)

        # Wait for result (with timeout)
        event.wait(timeout=timeout)

        # Get result
        with self._lock:
            _, result = self._pending_calls.pop(call_id, (None, None))

        if result is None:
            return {
                "call_id": call_id,
                "success": False,
                "error": "Tool call timed out or result not received"
            }

        return result

    def _handle_tool_result(self, result: Dict[str, Any]):
        """
        Handle tool result from C++.
        Called by reader thread when tool_result message is received.
        """
        call_id = result.get("call_id")
        if not call_id:
            return

        with self._lock:
            if call_id in self._pending_calls:
                event, _ = self._pending_calls[call_id]
                self._pending_calls[call_id] = (event, result)
                event.set()  # Wake up waiting thread

    def execute_tool(self, tool_name: str, action_code: str, parameters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Execute a tool and return result.

        Args:
            tool_name: Human-readable tool name
            action_code: C++ action code
            parameters: Optional parameters dict

        Returns:
            Dict with 'success', 'error' (if failed), and other result data
        """
        if parameters is None:
            parameters = {}

        call_id = self._send_tool_call(tool_name, action_code, parameters)
        result = self._wait_for_result(call_id)
        return result


# Tool definitions based on Audacity 4 action codes
# See src/trackedit/internal/trackeditactionscontroller.cpp for action definitions
class SelectionTools:
    """Selection management tools"""

    def __init__(self, executor: ToolExecutor):
        self.executor = executor

    def select_all(self) -> Dict[str, Any]:
        """Select all audio in project"""
        return self.executor.execute_tool(
            "select_all",
            "select-all",
            {}
        )

    def clear_selection(self) -> Dict[str, Any]:
        """Clear current selection"""
        return self.executor.execute_tool(
            "clear_selection",
            "clear-selection",
            {}
        )

    def select_all_tracks(self) -> Dict[str, Any]:
        """Select all tracks"""
        return self.executor.execute_tool(
            "select_all_tracks",
            "select-all-tracks",
            {}
        )

    def select_track_start_to_cursor(self) -> Dict[str, Any]:
        """Select from track start to cursor"""
        return self.executor.execute_tool(
            "select_track_start_to_cursor",
            "select-track-start-to-cursor",
            {}
        )

    def select_cursor_to_track_end(self) -> Dict[str, Any]:
        """Select from cursor to track end"""
        return self.executor.execute_tool(
            "select_cursor_to_track_end",
            "select-cursor-to-track-end",
            {}
        )

    def select_track_start_to_end(self) -> Dict[str, Any]:
        """Select entire track (start to end)"""
        return self.executor.execute_tool(
            "select_track_start_to_end",
            "select-track-start-to-end",
            {}
        )

    def set_time_selection(self, start_seconds: float, end_seconds: float) -> Dict[str, Any]:
        """
        Set time selection to a specific range in seconds.

        Args:
            start_seconds: Start time in seconds (clamped to >= 0)
            end_seconds: End time in seconds (clamped to >= 0)

        Note: If start > end, they will be swapped automatically.
        """
        return self.executor.execute_tool(
            "set_time_selection",
            f"action://trackedit/set-time-selection?start={start_seconds}&end={end_seconds}",
            {}
        )


class TrackTools:
    """Track operation tools"""

    def __init__(self, executor: ToolExecutor):
        self.executor = executor

    def create_mono_track(self) -> Dict[str, Any]:
        """Create new mono audio track"""
        return self.executor.execute_tool(
            "create_mono_track",
            "action://trackedit/new-mono-track",
            {}
        )

    def create_stereo_track(self) -> Dict[str, Any]:
        """Create new stereo audio track"""
        return self.executor.execute_tool(
            "create_stereo_track",
            "action://trackedit/new-stereo-track",
            {}
        )

    def delete_track(self) -> Dict[str, Any]:
        """Delete selected track"""
        return self.executor.execute_tool(
            "delete_track",
            "action://trackedit/track-delete",
            {}
        )

    def duplicate_track(self) -> Dict[str, Any]:
        """Duplicate selected track"""
        return self.executor.execute_tool(
            "duplicate_track",
            "track-duplicate",
            {}
        )

    def move_track_up(self) -> Dict[str, Any]:
        """Move track up"""
        return self.executor.execute_tool(
            "move_track_up",
            "track-move-up",
            {}
        )

    def move_track_down(self) -> Dict[str, Any]:
        """Move track down"""
        return self.executor.execute_tool(
            "move_track_down",
            "track-move-down",
            {}
        )


class ClipTools:
    """Clip operation tools"""

    def __init__(self, executor: ToolExecutor):
        self.executor = executor

    def split(self) -> Dict[str, Any]:
        """Split clip at cursor/selection"""
        return self.executor.execute_tool(
            "split",
            "split",
            {}
        )

    def split_at_time(self, time_seconds: float) -> Dict[str, Any]:
        """
        Split all tracks at a specific time point.

        Args:
            time_seconds: Time in seconds where to split
        """
        return self.executor.execute_tool(
            "split_at_time",
            f"action://trackedit/split-at-time?time={time_seconds}",
            {}
        )

    def join(self) -> Dict[str, Any]:
        """Merge adjacent clips"""
        return self.executor.execute_tool(
            "join",
            "join",
            {}
        )

    def duplicate(self) -> Dict[str, Any]:
        """Duplicate selected clips"""
        return self.executor.execute_tool(
            "duplicate",
            "duplicate",
            {}
        )

    def trim_outside_selection(self) -> Dict[str, Any]:
        """Trim audio outside selection"""
        return self.executor.execute_tool(
            "trim_outside_selection",
            "trim-audio-outside-selection",
            {}
        )

    def silence_selection(self) -> Dict[str, Any]:
        """Silence audio in selection"""
        return self.executor.execute_tool(
            "silence_selection",
            "silence-audio-selection",
            {}
        )


class EditingTools:
    """Editing operation tools"""

    def __init__(self, executor: ToolExecutor):
        self.executor = executor

    def cut(self) -> Dict[str, Any]:
        """Cut selection to clipboard"""
        return self.executor.execute_tool(
            "cut",
            "action://trackedit/cut",
            {}
        )

    def copy(self) -> Dict[str, Any]:
        """Copy selection to clipboard"""
        return self.executor.execute_tool(
            "copy",
            "action://trackedit/copy",
            {}
        )

    def paste(self) -> Dict[str, Any]:
        """Paste from clipboard"""
        return self.executor.execute_tool(
            "paste",
            "action://trackedit/paste-default",
            {}
        )

    def delete(self) -> Dict[str, Any]:
        """Delete selection"""
        return self.executor.execute_tool(
            "delete",
            "action://trackedit/delete",
            {}
        )

    def undo(self) -> Dict[str, Any]:
        """Undo last operation"""
        return self.executor.execute_tool(
            "undo",
            "action://trackedit/undo",
            {}
        )

    def redo(self) -> Dict[str, Any]:
        """Redo last undone operation"""
        return self.executor.execute_tool(
            "redo",
            "action://trackedit/redo",
            {}
        )


class EffectTools:
    """Effect application tools"""

    def __init__(self, executor: ToolExecutor):
        self.executor = executor

    def open_effect(self, effect_id: str) -> Dict[str, Any]:
        """Open effect dialog"""
        return self.executor.execute_tool(
            "open_effect",
            f"action://effects/open?effectId={effect_id}",
            {}
        )

    def apply_noise_reduction(self) -> Dict[str, Any]:
        """Apply noise reduction effect"""
        return self.open_effect("noisereduction")

    def apply_amplify(self) -> Dict[str, Any]:
        """Apply amplify effect"""
        return self.open_effect("amplify")

    def apply_normalize(self) -> Dict[str, Any]:
        """Apply normalize effect"""
        return self.open_effect("normalize")

    def apply_fade_in(self) -> Dict[str, Any]:
        """Apply fade in effect"""
        return self.open_effect("fadein")

    def apply_fade_out(self) -> Dict[str, Any]:
        """Apply fade out effect"""
        return self.open_effect("fadeout")

    def apply_reverse(self) -> Dict[str, Any]:
        """Apply reverse effect"""
        return self.open_effect("reverse")

    def apply_invert(self) -> Dict[str, Any]:
        """Apply invert effect"""
        return self.open_effect("invert")


class PlaybackTools:
    """Playback control tools"""

    def __init__(self, executor: ToolExecutor):
        self.executor = executor

    def play(self) -> Dict[str, Any]:
        """Start playback"""
        return self.executor.execute_tool(
            "play",
            "action://playback/play",
            {}
        )

    def stop(self) -> Dict[str, Any]:
        """Stop playback"""
        return self.executor.execute_tool(
            "stop",
            "action://playback/stop",
            {}
        )

    def pause(self) -> Dict[str, Any]:
        """Pause playback"""
        return self.executor.execute_tool(
            "pause",
            "action://playback/pause",
            {}
        )

    def rewind_start(self) -> Dict[str, Any]:
        """Rewind to start"""
        return self.executor.execute_tool(
            "rewind_start",
            "action://playback/rewind-start",
            {}
        )

    def rewind_end(self) -> Dict[str, Any]:
        """Rewind to end"""
        return self.executor.execute_tool(
            "rewind_end",
            "action://playback/rewind-end",
            {}
        )

    def toggle_loop(self) -> Dict[str, Any]:
        """Toggle loop playback"""
        return self.executor.execute_tool(
            "toggle_loop",
            "toggle-loop-region",
            {}
        )


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
            "set_time_selection": self._set_time_selection_wrapper,
            "select_all_tracks": self.selection.select_all_tracks,
            "select_track_start_to_cursor": self.selection.select_track_start_to_cursor,
            "select_cursor_to_track_end": self.selection.select_cursor_to_track_end,
            "select_track_start_to_end": self.selection.select_track_start_to_end,

            # Clip tools
            "split": self.clip.split,
            "split_at_time": self._split_at_time_wrapper,
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

    def _set_time_selection_wrapper(self, start_time: float, end_time: float) -> Dict[str, Any]:
        """Wrapper for set_time_selection to accept keyword arguments"""
        return self.selection.set_time_selection(start_time, end_time)

    def _split_at_time_wrapper(self, time: float) -> Dict[str, Any]:
        """Wrapper for split_at_time to accept keyword arguments"""
        return self.clip.split_at_time(time)

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

    def get_tool_list(self) -> List[Dict[str, Any]]:
        """
        Get list of all available tools
        Returns list of tool definitions for LLM function calling
        """
        # Import here to avoid circular imports
        from tool_schemas import TOOL_DEFINITIONS
        return TOOL_DEFINITIONS

