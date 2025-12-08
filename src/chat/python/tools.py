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

    def _send_state_query(self, query_type: str, parameters: Dict[str, Any] = None) -> str:
        """Send state query request to C++ and return call_id"""
        call_id = self._generate_call_id()

        if parameters is None:
            parameters = {}

        request = {
            "type": "state_query",
            "call_id": call_id,
            "query_type": query_type,
            "parameters": parameters
        }

        # Write to stdout (C++ reads from Python's stdout)
        json_str = json.dumps(request) + "\n"
        self.stdout.write(json_str)
        self.stdout.flush()

        return call_id

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

    def execute_state_query(self, query_type: str, parameters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Execute a state query and return result.

        Args:
            query_type: Type of state query (e.g., "get_selection_start_time")
            parameters: Optional parameters dict

        Returns:
            Dict with 'success', 'value' (if successful), 'error' (if failed)
        """
        if parameters is None:
            parameters = {}

        call_id = self._send_state_query(query_type, parameters)
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

    def set_selection_start_time(self, time: float) -> Dict[str, Any]:
        """Set only the start time of the selection"""
        # Use action:// URL pattern similar to set_time_selection
        return self.executor.execute_tool(
            "set_selection_start_time",
            f"action://trackedit/set-selection-start-time?time={time}",
            {}
        )

    def set_selection_end_time(self, time: float) -> Dict[str, Any]:
        """Set only the end time of the selection"""
        # Use action:// URL pattern similar to set_time_selection
        return self.executor.execute_tool(
            "set_selection_end_time",
            f"action://trackedit/set-selection-end-time?time={time}",
            {}
        )

    def reset_selection(self) -> Dict[str, Any]:
        """Reset/clear the time selection"""
        # resetDataSelection is the method name, but we need an action code
        # Using clear-selection as fallback, or we might need a new action
        return self.executor.execute_tool(
            "reset_selection",
            "clear-selection",  # TODO: Check if resetDataSelection action exists
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

    def move_track_to_top(self) -> Dict[str, Any]:
        """Move selected track(s) to top"""
        return self.executor.execute_tool(
            "move_track_to_top",
            "track-move-top",
            {}
        )

    def move_track_to_bottom(self) -> Dict[str, Any]:
        """Move selected track(s) to bottom"""
        return self.executor.execute_tool(
            "move_track_to_bottom",
            "track-move-bottom",
            {}
        )

    def create_label_track(self) -> Dict[str, Any]:
        """Create new label track"""
        return self.executor.execute_tool(
            "create_label_track",
            "new-label-track",
            {}
        )


class ClipTools:
    """Clip operation tools"""

    def __init__(self, executor: ToolExecutor):
        self.executor = executor

    def split(self) -> Dict[str, Any]:
        """
        Split selected tracks at cursor position or time selection.
        Queries state explicitly to avoid stale state issues.
        """
        # Query cursor position
        cursor_result = self.executor.execute_state_query("get_cursor_position")
        cursor_pos = cursor_result.get("value") if cursor_result.get("success") else None
        
        # Query time selection
        has_selection_result = self.executor.execute_state_query("has_time_selection")
        has_selection = has_selection_result.get("value", False) if has_selection_result.get("success") else False
        
        # Query selected tracks
        tracks_result = self.executor.execute_state_query("get_selected_tracks")
        selected_tracks = tracks_result.get("value", []) if tracks_result.get("success") else []
        
        # Determine split times
        split_times = []
        if has_selection:
            # If time selection exists, split at both start and end
            start_result = self.executor.execute_state_query("get_selection_start_time")
            end_result = self.executor.execute_state_query("get_selection_end_time")
            if start_result.get("success") and end_result.get("success"):
                start_time = start_result.get("value")
                end_time = end_result.get("value")
                if start_time is not None and end_time is not None:
                    split_times = [start_time, end_time]
        elif cursor_pos is not None:
            # If no time selection, split at cursor position
            split_times = [cursor_pos]
        else:
            # No valid split point
            return {
                "success": False,
                "error": "No cursor position or time selection available for split"
            }
        
        # Ensure tracks are selected - if none selected, we can't split
        # (split_at_time uses orderedTrackList which should have tracks, but we check anyway)
        if not split_times:
            return {
                "success": False,
                "error": "No valid split time determined"
            }
        
        # Split at each time point
        # Note: split_at_time uses orderedTrackList() which gets all tracks,
        # but it's more reliable than doGlobalSplit() which reads stale selection state
        results = []
        for split_time in split_times:
            result = self.split_at_time(split_time)
            results.append(result)
            if not result.get("success"):
                # Return first error
                return result
        
        # Return success if all splits succeeded
        return {
            "success": True,
            "message": f"Split at {len(split_times)} time point(s)",
            "split_times": split_times
        }

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

    def delete_all_tracks_ripple(self) -> Dict[str, Any]:
        """Delete selection with ripple across all tracks"""
        return self.executor.execute_tool(
            "delete_all_tracks_ripple",
            "delete-all-tracks-ripple",
            {}
        )

    def cut_all_tracks_ripple(self) -> Dict[str, Any]:
        """Cut selection with ripple across all tracks"""
        return self.executor.execute_tool(
            "cut_all_tracks_ripple",
            "cut-all-tracks-ripple",
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

    def apply_normalize_loudness(self) -> Dict[str, Any]:
        """Apply normalize loudness effect"""
        return self.open_effect("NormalizeLoudness")

    def apply_compressor(self) -> Dict[str, Any]:
        """Apply compressor effect"""
        return self.open_effect("Compressor")

    def apply_limiter(self) -> Dict[str, Any]:
        """Apply limiter effect"""
        return self.open_effect("Limiter")

    def apply_truncate_silence(self) -> Dict[str, Any]:
        """Apply truncate silence effect"""
        return self.open_effect("TruncateSilence")

    def repeat_last_effect(self) -> Dict[str, Any]:
        """Repeat last applied effect"""
        return self.executor.execute_tool(
            "repeat_last_effect",
            "repeat-last-effect",
            {}
        )


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

    def seek(self, time: float) -> Dict[str, Any]:
        """Move playhead to specific time position"""
        # seek action requires seekTime and triggerPlay parameters
        # ActionQuery will parse these from the URL
        return self.executor.execute_tool(
            "seek",
            f"action://playback/seek?seekTime={time}&triggerPlay=false",
            {}
        )


class LabelTools:
    """Label track operation tools"""

    def __init__(self, executor: ToolExecutor):
        self.executor = executor

    def add_label(self) -> Dict[str, Any]:
        """Add label at cursor position or selection"""
        return self.executor.execute_tool(
            "add_label",
            "label-add",
            {}
        )


class TranscriptionTools:
    """Transcription tools for speech-to-text with filler word detection"""

    def __init__(self, executor: ToolExecutor):
        self.executor = executor
        self._cached_transcript: Optional[Dict[str, Any]] = None
        self._transcription_service = None

    def _get_service(self):
        """Lazy-load transcription service."""
        if self._transcription_service is None:
            from transcription_service import get_transcription_service
            self._transcription_service = get_transcription_service()
        return self._transcription_service

    def transcribe_audio(
        self,
        enable_diarization: bool = False,
        language: str = "en"
    ) -> Dict[str, Any]:
        """
        Transcribe the project audio.

        Args:
            enable_diarization: Enable speaker diarization
            language: Language code

        Returns:
            Transcript data with word-level timestamps
        """
        service = self._get_service()

        if not service.is_configured():
            return {
                "success": False,
                "error": "Transcription not configured. Set ASSEMBLYAI_API_KEY in environment."
            }

        # Check total project time before exporting
        total_time_result = self.executor.execute_state_query("get_total_project_time")
        if total_time_result.get("success"):
            total_duration = total_time_result.get("value", 0.0)
            if total_duration == 0.0:
                return {
                    "success": False,
                    "error": f"Project has no audio duration (total time is 0). Cannot export empty project."
                }
        else:
            print(f"Failed to get total time: {total_time_result.get('error')}", file=sys.stderr)

        # Get audio file path from project
        # For now, we request the exported audio path via state query
        result = self.executor.execute_state_query("get_project_audio_path")

        if not result.get("success"):
            return {
                "success": False,
                "error": result.get("error", "Failed to get project audio path")
            }

        audio_path = result.get("value")
        if not audio_path:
            return {
                "success": False,
                "error": "No audio file available for transcription"
            }

        # Transcribe
        transcript_result = service.transcribe_file(
            audio_path,
            enable_diarization=enable_diarization,
            language=language
        )

        if transcript_result.get("error"):
            return {
                "success": False,
                "error": transcript_result["error"]
            }

        # Cache the transcript for subsequent searches
        self._cached_transcript = transcript_result.get("transcript")

        # Send transcript data to C++ via stdout
        if self._cached_transcript:
            import json
            transcript_message = {
                "type": "transcript_data",
                "transcript": self._cached_transcript
            }
            print(json.dumps(transcript_message), flush=True)

        return {
            "success": True,
            "transcript": self._cached_transcript,
            "word_count": len(self._cached_transcript.get("words", [])),
            "duration": self._cached_transcript.get("duration", 0),
            "filler_count": self._cached_transcript.get("filler_count", 0)
        }

    def search_transcript(
        self,
        query: str,
        case_sensitive: bool = False
    ) -> Dict[str, Any]:
        """
        Search the transcript for a word or phrase.

        Args:
            query: Text to search for
            case_sensitive: Case-sensitive search

        Returns:
            List of matches with timestamps
        """
        # If no cached transcript, try to get it from C++
        if not self._cached_transcript:
            result = self.executor.execute_state_query("get_transcript")
            if result.get("success") and result.get("value"):
                self._cached_transcript = result.get("value")
            else:
                return {
                    "success": False,
                    "error": "No transcript available. Call transcribe_audio first."
                }

        service = self._get_service()
        matches = service.search_transcript(
            self._cached_transcript,
            query,
            case_sensitive=case_sensitive
        )

        return {
            "success": True,
            "query": query,
            "matches": matches,
            "count": len(matches)
        }

    def find_filler_words(self) -> Dict[str, Any]:
        """
        Find all filler words in the transcript.

        Returns:
            Filler words with timestamps and summary
        """
        # If no cached transcript, try to get it from C++
        if not self._cached_transcript:
            result = self.executor.execute_state_query("get_transcript")
            if result.get("success") and result.get("value"):
                self._cached_transcript = result.get("value")
            else:
                return {
                    "success": False,
                    "error": "No transcript available. Call transcribe_audio first."
                }

        service = self._get_service()
        return service.get_filler_words(self._cached_transcript)

    def analyze_transcript(self) -> Dict[str, Any]:
        """
        Analyze transcript using a dedicated LLM call.
        Returns both raw stats and AI narrative with timestamps.
        For long transcripts (>10 min), analyzes in chunks.

        Returns:
            Dict with analysis narrative, stats, and chunk breakdowns
        """
        # If no cached transcript, try to get it from C++
        if not self._cached_transcript:
            result = self.executor.execute_state_query("get_transcript")
            if result.get("success") and result.get("value"):
                # Convert C++ transcript format to Python format
                transcript_data = result.get("value")
                self._cached_transcript = transcript_data
            else:
                return {
                    "success": False,
                    "error": "No transcript available. Call transcribe_audio first."
                }

        # Check OpenAI availability
        from config import is_openai_configured, get_openai_api_key, get_chat_model
        if not is_openai_configured():
            return {
                "success": False,
                "error": "OpenAI API key not configured. Cannot perform transcript analysis."
            }

        # Get transcript data
        words = self._cached_transcript.get("words", [])
        filler_words = self._cached_transcript.get("filler_words", [])
        duration = self._cached_transcript.get("duration", 0)

        if not words:
            return {
                "success": False,
                "error": "Transcript has no words to analyze."
            }

        # Calculate overall stats
        word_count = len(words)
        filler_count = len(filler_words)
        words_per_minute = (word_count / (duration / 60)) if duration > 0 else 0
        fillers_per_minute = (filler_count / (duration / 60)) if duration > 0 else 0

        # Build filler breakdown
        filler_breakdown = {}
        for fw in filler_words:
            word = fw["word"].lower()
            filler_breakdown[word] = filler_breakdown.get(word, 0) + 1

        # Determine if chunking is needed (>10 minutes)
        chunk_threshold_seconds = 600  # 10 minutes
        chunk_size_seconds = 300  # 5 minutes per chunk

        if duration > chunk_threshold_seconds:
            # Chunk the transcript
            chunks = self._split_into_chunks(words, filler_words, chunk_size_seconds)
            analyses = []
            chunk_stats = []

            for i, chunk in enumerate(chunks):
                chunk_analysis = self._analyze_chunk(
                    chunk, i + 1, len(chunks), get_openai_api_key(), get_chat_model()
                )
                if chunk_analysis.get("success"):
                    analyses.append(chunk_analysis["analysis"])
                    chunk_stats.append(chunk_analysis["chunk_stats"])
                else:
                    analyses.append(f"## Chunk {i + 1}\nAnalysis failed: {chunk_analysis.get('error', 'unknown')}")
                    chunk_stats.append(chunk_analysis.get("chunk_stats", {}))

            combined_analysis = "\n\n".join(analyses)
        else:
            # Single analysis for short transcripts
            single_result = self._analyze_single(
                words, filler_words, duration, get_openai_api_key(), get_chat_model()
            )
            if not single_result.get("success"):
                return single_result
            combined_analysis = single_result["analysis"]
            chunk_stats = [single_result.get("chunk_stats", {})]

        return {
            "success": True,
            "analysis": combined_analysis,
            "stats": {
                "duration_seconds": round(duration, 1),
                "duration_formatted": self._format_time(duration),
                "word_count": word_count,
                "words_per_minute": round(words_per_minute, 1),
                "filler_count": filler_count,
                "fillers_per_minute": round(fillers_per_minute, 1),
                "filler_breakdown": filler_breakdown,
                "chunks": chunk_stats
            }
        }

    def _split_into_chunks(
        self,
        words: List[Dict],
        filler_words: List[Dict],
        chunk_size_seconds: float
    ) -> List[Dict]:
        """Split transcript into time-based chunks."""
        if not words:
            return []

        chunks = []
        current_chunk_words = []
        current_chunk_fillers = []
        chunk_start = 0.0
        chunk_end = chunk_size_seconds

        for word in words:
            word_start = word.get("start_time", 0)

            # Start new chunk if word is past current chunk boundary
            if word_start >= chunk_end and current_chunk_words:
                chunks.append({
                    "words": current_chunk_words,
                    "filler_words": current_chunk_fillers,
                    "start_time": chunk_start,
                    "end_time": chunk_end
                })
                current_chunk_words = []
                current_chunk_fillers = []
                chunk_start = chunk_end
                chunk_end += chunk_size_seconds

            current_chunk_words.append(word)

        # Add final chunk
        if current_chunk_words:
            actual_end = current_chunk_words[-1].get("end_time", chunk_end)
            chunks.append({
                "words": current_chunk_words,
                "filler_words": [],  # Will populate below
                "start_time": chunk_start,
                "end_time": actual_end
            })

        # Assign filler words to chunks
        for fw in filler_words:
            fw_start = fw.get("start_time", 0)
            for chunk in chunks:
                if chunk["start_time"] <= fw_start < chunk["end_time"]:
                    chunk["filler_words"].append(fw)
                    break

        return chunks

    def _analyze_chunk(
        self,
        chunk: Dict,
        chunk_num: int,
        total_chunks: int,
        api_key: str,
        model: str
    ) -> Dict[str, Any]:
        """Analyze a single chunk of the transcript."""
        words = chunk["words"]
        filler_words = chunk["filler_words"]
        start_time = chunk["start_time"]
        end_time = chunk["end_time"]
        duration = end_time - start_time

        # Calculate chunk stats
        word_count = len(words)
        filler_count = len(filler_words)
        words_per_minute = (word_count / (duration / 60)) if duration > 0 else 0
        fillers_per_minute = (filler_count / (duration / 60)) if duration > 0 else 0

        chunk_stats = {
            "chunk": chunk_num,
            "start_time": round(start_time, 1),
            "end_time": round(end_time, 1),
            "start_formatted": self._format_time(start_time),
            "end_formatted": self._format_time(end_time),
            "word_count": word_count,
            "filler_count": filler_count,
            "words_per_minute": round(words_per_minute, 1),
            "fillers_per_minute": round(fillers_per_minute, 1)
        }

        # Build timestamped transcript
        timestamped_text = self._build_timestamped_transcript(words)

        # Build filler list with timestamps
        filler_list = self._build_filler_list(filler_words, max_items=30)

        # Build prompt
        prompt = self._build_analysis_prompt(
            timestamped_text, duration, word_count, words_per_minute,
            filler_count, fillers_per_minute, filler_list,
            chunk_label=f"Section {chunk_num} of {total_chunks} [{self._format_time(start_time)}-{self._format_time(end_time)}]"
        )

        # Make API call
        try:
            from openai import OpenAI
            client = OpenAI(api_key=api_key)
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are an experienced podcast editor. Provide constructive feedback with specific timestamps."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=500,
                temperature=0.3
            )
            analysis = f"## Section {chunk_num} [{self._format_time(start_time)}-{self._format_time(end_time)}]\n\n{response.choices[0].message.content}"
            return {"success": True, "analysis": analysis, "chunk_stats": chunk_stats}
        except Exception as e:
            return {"success": False, "error": str(e), "chunk_stats": chunk_stats}

    def _analyze_single(
        self,
        words: List[Dict],
        filler_words: List[Dict],
        duration: float,
        api_key: str,
        model: str
    ) -> Dict[str, Any]:
        """Analyze a single (non-chunked) transcript."""
        word_count = len(words)
        filler_count = len(filler_words)
        words_per_minute = (word_count / (duration / 60)) if duration > 0 else 0
        fillers_per_minute = (filler_count / (duration / 60)) if duration > 0 else 0

        chunk_stats = {
            "chunk": 1,
            "start_time": 0,
            "end_time": round(duration, 1),
            "start_formatted": "0:00",
            "end_formatted": self._format_time(duration),
            "word_count": word_count,
            "filler_count": filler_count,
            "words_per_minute": round(words_per_minute, 1),
            "fillers_per_minute": round(fillers_per_minute, 1)
        }

        # Build timestamped transcript
        timestamped_text = self._build_timestamped_transcript(words)

        # Build filler list
        filler_list = self._build_filler_list(filler_words, max_items=50)

        # Build prompt
        prompt = self._build_analysis_prompt(
            timestamped_text, duration, word_count, words_per_minute,
            filler_count, fillers_per_minute, filler_list
        )

        # Make API call
        try:
            from openai import OpenAI
            client = OpenAI(api_key=api_key)
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are an experienced podcast editor. Provide constructive feedback with specific timestamps."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=600,
                temperature=0.3
            )
            return {"success": True, "analysis": response.choices[0].message.content, "chunk_stats": chunk_stats}
        except Exception as e:
            return {"success": False, "error": str(e), "chunk_stats": chunk_stats}

    def _build_analysis_prompt(
        self,
        timestamped_text: str,
        duration: float,
        word_count: int,
        words_per_minute: float,
        filler_count: int,
        fillers_per_minute: float,
        filler_list: str,
        chunk_label: str = None
    ) -> str:
        """Build the analysis prompt for OpenAI."""
        header = f"Analyze this podcast/audio transcript{f' ({chunk_label})' if chunk_label else ''} and provide editorial feedback."

        return f"""{header}
Reference specific timestamps when identifying issues.

TRANSCRIPT WITH TIMESTAMPS:
{timestamped_text}

DURATION: {self._format_time(duration)} ({duration:.1f} seconds)
WORD COUNT: {word_count} words
PACE: {words_per_minute:.0f} words per minute

FILLER WORDS ({filler_count} total, {fillers_per_minute:.1f}/minute):
{filler_list}

Provide feedback on:
1. **Filler Words**: Which are most problematic? Reference timestamps.
2. **Pacing**: Any sections that feel rushed or slow? Give time ranges.
3. **Clarity**: Unclear phrases or repetitions? Give timestamps.
4. **Suggestions**: 2-3 specific improvements with timestamps where applicable.

Be concise and constructive. Reference [MM:SS] timestamps."""

    def _build_timestamped_transcript(self, words: List[Dict], interval: float = 15.0) -> str:
        """Build transcript with timestamp markers every ~15 seconds."""
        if not words:
            return ""

        result = []
        current_marker = 0.0
        current_chunk = []

        for word in words:
            start_time = word.get("start_time", 0)

            # Add timestamp marker when we cross interval boundary
            while start_time >= current_marker:
                if current_chunk:
                    result.append(" ".join(current_chunk))
                result.append(f"\n[{self._format_time(current_marker)}] ")
                current_chunk = []
                current_marker += interval

            current_chunk.append(word.get("word", ""))

        # Add remaining words
        if current_chunk:
            result.append(" ".join(current_chunk))

        return "".join(result).strip()

    def _build_filler_list(self, filler_words: List[Dict], max_items: int = 50) -> str:
        """Build formatted list of filler words with timestamps."""
        if not filler_words:
            return "  (none detected)"

        lines = [
            f"  [{self._format_time(fw['start_time'])}] \"{fw['word']}\""
            for fw in filler_words[:max_items]
        ]
        if len(filler_words) > max_items:
            lines.append(f"  ... and {len(filler_words) - max_items} more")
        return "\n".join(lines)

    def _format_time(self, seconds: float) -> str:
        """Format seconds as MM:SS."""
        mins = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{mins}:{secs:02d}"

    def get_cached_transcript(self) -> Optional[Dict[str, Any]]:
        """Get the cached transcript, if any."""
        return self._cached_transcript

    def clear_transcript_cache(self):
        """Clear the cached transcript."""
        self._cached_transcript = None


class StateQueryTools:
    """State query tools - read-only queries of project state"""

    def __init__(self, executor: ToolExecutor):
        self.executor = executor

    def get_selection_start_time(self) -> Optional[float]:
        """Get the start time of the current selection in seconds"""
        result = self.executor.execute_state_query("get_selection_start_time")
        if result.get("success"):
            return result.get("value", 0.0)
        return None

    def get_selection_end_time(self) -> Optional[float]:
        """Get the end time of the current selection in seconds"""
        result = self.executor.execute_state_query("get_selection_end_time")
        if result.get("success"):
            return result.get("value", 0.0)
        return None

    def has_time_selection(self) -> bool:
        """Check if there is a time selection"""
        result = self.executor.execute_state_query("has_time_selection")
        if result.get("success"):
            return result.get("value", False)
        return False

    def get_selected_tracks(self) -> List[str]:
        """Get list of selected track IDs"""
        result = self.executor.execute_state_query("get_selected_tracks")
        if result.get("success"):
            return result.get("value", [])
        return []

    def get_selected_clips(self) -> List[Dict[str, str]]:
        """Get list of selected clip keys (each with track_id and clip_id)"""
        result = self.executor.execute_state_query("get_selected_clips")
        if result.get("success"):
            return result.get("value", [])
        return []

    def get_cursor_position(self) -> Optional[float]:
        """Get the current cursor/playhead position in seconds"""
        result = self.executor.execute_state_query("get_cursor_position")
        if result.get("success"):
            return result.get("value", 0.0)
        return None

    def get_total_project_time(self) -> float:
        """Get the total duration of the project in seconds"""
        result = self.executor.execute_state_query("get_total_project_time")
        if result.get("success"):
            return result.get("value", 0.0)
        return 0.0

    def get_track_list(self) -> List[Dict[str, str]]:
        """Get list of all tracks in the project"""
        result = self.executor.execute_state_query("get_track_list")
        if result.get("success"):
            return result.get("value", [])
        return []

    def get_clips_on_track(self, track_id: str) -> List[Dict[str, str]]:
        """Get list of clips on a specific track"""
        result = self.executor.execute_state_query("get_clips_on_track", {"track_id": track_id})
        if result.get("success"):
            return result.get("value", [])
        return []

    def get_all_labels(self) -> List[Dict[str, Any]]:
        """Get all label track data"""
        result = self.executor.execute_state_query("get_all_labels")
        if result.get("success"):
            return result.get("value", [])
        return []

    def action_enabled(self, action_code: str) -> bool:
        """Check if an action is currently enabled"""
        result = self.executor.execute_state_query("action_enabled", {"action_code": action_code})
        if result.get("success"):
            return result.get("value", False)
        return False


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
        self.label = LabelTools(executor)
        self.state = StateQueryTools(executor)
        self.transcription = TranscriptionTools(executor)

        # Build tool name -> method mapping
        self._tool_map = self._build_tool_map()

    def _build_tool_map(self) -> Dict[str, Callable]:
        """Build mapping from tool names to methods"""
        return {
            # Selection tools
            "select_all": self.selection.select_all,
            "clear_selection": self.selection.clear_selection,
            "set_time_selection": self._set_time_selection_wrapper,
            "set_selection_start_time": self._set_selection_start_time_wrapper,
            "set_selection_end_time": self._set_selection_end_time_wrapper,
            "reset_selection": self.selection.reset_selection,
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
            "delete_all_tracks_ripple": self.editing.delete_all_tracks_ripple,
            "cut_all_tracks_ripple": self.editing.cut_all_tracks_ripple,
            "undo": self.editing.undo,
            "redo": self.editing.redo,

            # Track tools
            "create_mono_track": self.track.create_mono_track,
            "create_stereo_track": self.track.create_stereo_track,
            "delete_track": self.track.delete_track,
            "duplicate_track": self.track.duplicate_track,
            "move_track_up": self.track.move_track_up,
            "move_track_down": self.track.move_track_down,
            "move_track_to_top": self.track.move_track_to_top,
            "move_track_to_bottom": self.track.move_track_to_bottom,
            "create_label_track": self.track.create_label_track,

            # Effect tools
            "apply_noise_reduction": self.effect.apply_noise_reduction,
            "apply_amplify": self.effect.apply_amplify,
            "apply_normalize": self.effect.apply_normalize,
            "apply_normalize_loudness": self.effect.apply_normalize_loudness,
            "apply_compressor": self.effect.apply_compressor,
            "apply_limiter": self.effect.apply_limiter,
            "apply_truncate_silence": self.effect.apply_truncate_silence,
            "apply_fade_in": self.effect.apply_fade_in,
            "apply_fade_out": self.effect.apply_fade_out,
            "apply_reverse": self.effect.apply_reverse,
            "apply_invert": self.effect.apply_invert,
            "repeat_last_effect": self.effect.repeat_last_effect,

            # Playback tools
            "play": self.playback.play,
            "stop": self.playback.stop,
            "pause": self.playback.pause,
            "seek": self._seek_wrapper,
            "rewind_to_start": self.playback.rewind_start,
            "toggle_loop": self.playback.toggle_loop,

            # Label tools
            "add_label": self.label.add_label,

            # Transcription tools
            "transcribe_audio": self._transcribe_audio_wrapper,
            "search_transcript": self._search_transcript_wrapper,
            "find_filler_words": self._find_filler_words_wrapper,
            "analyze_transcript": self._analyze_transcript_wrapper,

            # State query tools
            "get_selection_start_time": self._get_selection_start_time_wrapper,
            "get_selection_end_time": self._get_selection_end_time_wrapper,
            "has_time_selection": self._has_time_selection_wrapper,
            "get_selected_tracks": self._get_selected_tracks_wrapper,
            "get_selected_clips": self._get_selected_clips_wrapper,
            "get_cursor_position": self._get_cursor_position_wrapper,
            "get_total_project_time": self._get_total_project_time_wrapper,
            "get_track_list": self._get_track_list_wrapper,
            "get_clips_on_track": self._get_clips_on_track_wrapper,
            "get_all_labels": self._get_all_labels_wrapper,
            "action_enabled": self._action_enabled_wrapper,
        }

    def _set_time_selection_wrapper(self, start_time: float, end_time: float) -> Dict[str, Any]:
        """Wrapper for set_time_selection to accept keyword arguments"""
        return self.selection.set_time_selection(start_time, end_time)

    def _set_selection_start_time_wrapper(self, time: float) -> Dict[str, Any]:
        """Wrapper for set_selection_start_time to accept keyword arguments"""
        return self.selection.set_selection_start_time(time)

    def _set_selection_end_time_wrapper(self, time: float) -> Dict[str, Any]:
        """Wrapper for set_selection_end_time to accept keyword arguments"""
        return self.selection.set_selection_end_time(time)

    def _split_at_time_wrapper(self, time: float) -> Dict[str, Any]:
        """Wrapper for split_at_time to accept keyword arguments"""
        return self.clip.split_at_time(time)

    def _seek_wrapper(self, time: float) -> Dict[str, Any]:
        """Wrapper for seek to accept keyword arguments"""
        return self.playback.seek(time)

    # State query wrappers
    def _get_selection_start_time_wrapper(self) -> Dict[str, Any]:
        """Wrapper for get_selection_start_time"""
        value = self.state.get_selection_start_time()
        return {"success": value is not None, "value": value}

    def _get_selection_end_time_wrapper(self) -> Dict[str, Any]:
        """Wrapper for get_selection_end_time"""
        value = self.state.get_selection_end_time()
        return {"success": value is not None, "value": value}

    def _has_time_selection_wrapper(self) -> Dict[str, Any]:
        """Wrapper for has_time_selection"""
        value = self.state.has_time_selection()
        return {"success": True, "value": value}

    def _get_selected_tracks_wrapper(self) -> Dict[str, Any]:
        """Wrapper for get_selected_tracks"""
        value = self.state.get_selected_tracks()
        return {"success": True, "value": value}

    def _get_selected_clips_wrapper(self) -> Dict[str, Any]:
        """Wrapper for get_selected_clips"""
        value = self.state.get_selected_clips()
        return {"success": True, "value": value}

    def _get_cursor_position_wrapper(self) -> Dict[str, Any]:
        """Wrapper for get_cursor_position"""
        value = self.state.get_cursor_position()
        return {"success": value is not None, "value": value}

    def _get_total_project_time_wrapper(self) -> Dict[str, Any]:
        """Wrapper for get_total_project_time"""
        value = self.state.get_total_project_time()
        return {"success": True, "value": value}

    def _get_track_list_wrapper(self) -> Dict[str, Any]:
        """Wrapper for get_track_list"""
        value = self.state.get_track_list()
        return {"success": True, "value": value}

    def _get_clips_on_track_wrapper(self, track_id: str) -> Dict[str, Any]:
        """Wrapper for get_clips_on_track"""
        value = self.state.get_clips_on_track(track_id)
        return {"success": True, "value": value}

    def _get_all_labels_wrapper(self) -> Dict[str, Any]:
        """Wrapper for get_all_labels"""
        value = self.state.get_all_labels()
        return {"success": True, "value": value}

    def _action_enabled_wrapper(self, action_code: str) -> Dict[str, Any]:
        """Wrapper for action_enabled"""
        value = self.state.action_enabled(action_code)
        return {"success": True, "value": value}

    # Transcription tool wrappers
    def _transcribe_audio_wrapper(
        self,
        enable_diarization: bool = False,
        language: str = "en"
    ) -> Dict[str, Any]:
        """Wrapper for transcribe_audio"""
        return self.transcription.transcribe_audio(
            enable_diarization=enable_diarization,
            language=language
        )

    def _search_transcript_wrapper(
        self,
        query: str,
        case_sensitive: bool = False
    ) -> Dict[str, Any]:
        """Wrapper for search_transcript"""
        return self.transcription.search_transcript(
            query=query,
            case_sensitive=case_sensitive
        )

    def _find_filler_words_wrapper(self) -> Dict[str, Any]:
        """Wrapper for find_filler_words"""
        return self.transcription.find_filler_words()

    def _analyze_transcript_wrapper(self) -> Dict[str, Any]:
        """Wrapper for analyze_transcript"""
        return self.transcription.analyze_transcript()

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

