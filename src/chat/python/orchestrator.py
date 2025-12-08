#!/usr/bin/env python3
"""
Orchestrator Agent
Main orchestration logic that receives user requests and coordinates
tool execution using OpenAI function calling.
"""

import json
import sys
import uuid
from typing import Dict, Any, List, Optional

# Import OpenAI SDK when available
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

from config import get_openai_api_key, is_openai_configured, get_chat_model
from tool_schemas import TOOL_DEFINITIONS, FUNCTION_CALLING_SYSTEM_PROMPT


class OrchestratorAgent:
    """
    Main orchestrator that:
    1. Receives user requests
    2. Calls OpenAI with function calling enabled
    3. Executes returned tool calls directly
    4. Handles approval flow for destructive operations
    """

    def __init__(self, tools):
        """
        Initialize orchestrator with tool registry.

        Args:
            tools: ToolRegistry instance
        """
        self.tools = tools

        # Conversation memory
        self.conversation_history: List[Dict[str, str]] = []

        # Initialize OpenAI client if available and configured
        self.openai_client = None
        if OPENAI_AVAILABLE and is_openai_configured():
            api_key = get_openai_api_key()
            self.openai_client = OpenAI(api_key=api_key)
            print("OpenAI client initialized for function calling", file=sys.stderr)
        elif OPENAI_AVAILABLE and not is_openai_configured():
            print("Warning: OpenAI SDK available but OPENAI_API_KEY not set. Using keyword-based fallback.", file=sys.stderr)

    def process_request(self, user_message: str) -> Dict[str, Any]:
        """
        Process user request using OpenAI function calling.

        Args:
            user_message: User's natural language request

        Returns:
            Dict with 'type', 'content', and optional fields
        """
        try:
            # Add to conversation history
            self.conversation_history.append({"role": "user", "content": user_message})

            # Limit history to last 20 messages
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

            # Debug: Log what OpenAI returned
            print(f"OpenAI response - tool_calls: {message.tool_calls}, content: {message.content[:100] if message.content else None}", file=sys.stderr)

            # Check if model wants to call tools
            if message.tool_calls:
                print(f"OpenAI returned {len(message.tool_calls)} tool call(s): {[tc.function.name for tc in message.tool_calls]}", file=sys.stderr)
                return self._execute_tool_calls(message.tool_calls, user_message)
            else:
                # Pure conversation response
                response_text = message.content or "I'm not sure how to help with that."
                print(f"OpenAI did not return tool calls. Response: {response_text[:200]}", file=sys.stderr)
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

        Args:
            tool_calls: List of tool call objects from OpenAI
            user_message: Original user message

        Returns:
            Response dict with results or approval request
        """
        results = []
        tool_descriptions = []
        human_readable_steps = []

        # Define which tools require approval
        destructive_tools = {"cut", "delete_selection", "delete_track", "trim_to_selection"}
        effect_tools = {"apply_noise_reduction", "apply_normalize", "apply_amplify",
                        "apply_fade_in", "apply_fade_out", "apply_reverse", "apply_invert"}

        # Check if any tools require approval
        requires_approval = False
        for tool_call in tool_calls:
            tool_name = tool_call.function.name
            if tool_name in destructive_tools or tool_name in effect_tools:
                requires_approval = True
                break

        # Build task plan
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
            tool_descriptions.append(f"{tool_name}({json.dumps(arguments) if arguments else ''})")
            human_readable_steps.append(self._tool_to_human_readable(tool_name, arguments))

        # If requires approval, return approval request
        if requires_approval:
            approval_id = self._generate_approval_id()
            return {
                "type": "approval_request",
                "approval_id": approval_id,
                "description": " then ".join(human_readable_steps),
                "preview": " → ".join(human_readable_steps),
                "task_plan": task_plan,
                "approval_mode": "batch",
                "current_step": None,
                "total_steps": len(task_plan)
            }

        # Note: We no longer automatically select all tracks/audio
        # Tools that respect track selection (trim_to_selection, effects, etc.) will operate on
        # currently selected tracks only. If user wants all tracks, they must explicitly request it.

        # Execute tools directly (no approval needed)
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

    def process_approval(self, approval_id: str, approved: bool, task_plan: List[Dict[str, Any]] = None,
                         approval_mode: str = "batch", current_step: int = 0, batch_mode: bool = False) -> Dict[str, Any]:
        """
        Process approval response and execute tools if approved.

        Args:
            approval_id: ID of the approval request
            approved: Whether user approved
            task_plan: Task plan to execute (list of tool_name + arguments dicts)
            approval_mode: "batch" or "step_by_step"
            current_step: Current step index for step-by-step mode
            batch_mode: Force batch execution

        Returns:
            Dict with result or next approval request
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

        # Note: We no longer automatically select all tracks/audio
        # Tools that respect track selection (trim_to_selection, effects, etc.) will operate on
        # currently selected tracks only. If user wants all tracks, they must explicitly request it.

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

    def _process_without_llm(self, user_message: str) -> Dict[str, Any]:
        """
        Fallback processing when OpenAI is not available.
        Uses simple keyword matching for basic commands.

        Args:
            user_message: User's message

        Returns:
            Response dict
        """
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

    def _generate_approval_id(self) -> str:
        """Generate unique approval ID"""
        return f"approval_{uuid.uuid4().hex[:8]}"

    def _tool_to_human_readable(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """Convert a tool call to human-readable description."""
        # Selection tools
        if tool_name == "set_time_selection":
            start = arguments.get("start_time", 0)
            end = arguments.get("end_time", 0)
            return f"Select {start}s to {end}s"
        elif tool_name == "select_all":
            return "Select all"
        elif tool_name == "clear_selection":
            return "Clear selection"
        elif tool_name == "select_all_tracks":
            return "Select all tracks"

        # Clip tools
        elif tool_name == "split_at_time":
            time = arguments.get("time", 0)
            return f"Split at {time}s"
        elif tool_name == "split":
            return "Split at cursor"
        elif tool_name == "join":
            return "Join clips"
        elif tool_name == "trim_to_selection":
            return "Trim to selection"
        elif tool_name == "silence_selection":
            return "Silence selection"
        elif tool_name == "duplicate_clip":
            return "Duplicate clip"

        # Editing tools
        elif tool_name == "cut":
            return "Cut"
        elif tool_name == "copy":
            return "Copy"
        elif tool_name == "paste":
            return "Paste"
        elif tool_name == "delete_selection":
            return "Delete selection"
        elif tool_name == "undo":
            return "Undo"
        elif tool_name == "redo":
            return "Redo"

        # Track tools
        elif tool_name == "create_mono_track":
            return "Create mono track"
        elif tool_name == "create_stereo_track":
            return "Create stereo track"
        elif tool_name == "delete_track":
            return "Delete track"
        elif tool_name == "duplicate_track":
            return "Duplicate track"

        # Effect tools
        elif tool_name == "apply_noise_reduction":
            return "Apply noise reduction"
        elif tool_name == "apply_normalize":
            return "Apply normalize"
        elif tool_name == "apply_amplify":
            return "Apply amplify"
        elif tool_name == "apply_fade_in":
            return "Apply fade in"
        elif tool_name == "apply_fade_out":
            return "Apply fade out"
        elif tool_name == "apply_reverse":
            return "Apply reverse"
        elif tool_name == "apply_invert":
            return "Apply invert"

        # Playback tools
        elif tool_name == "play":
            return "Play"
        elif tool_name == "stop":
            return "Stop"
        elif tool_name == "pause":
            return "Pause"
        elif tool_name == "rewind_to_start":
            return "Rewind to start"
        elif tool_name == "toggle_loop":
            return "Toggle loop"

        # Transcription tools
        elif tool_name == "transcribe_audio":
            lang = arguments.get("language", "en")
            diarize = arguments.get("enable_diarization", False)
            desc = "Transcribe audio"
            if diarize:
                desc += " with speaker identification"
            if lang != "en":
                desc += f" ({lang})"
            return desc
        elif tool_name == "search_transcript":
            query = arguments.get("query", "")
            return f"Search transcript for '{query}'"
        elif tool_name == "find_filler_words":
            return "Find filler words (um, uh, like, etc.)"

        # Default fallback
        else:
            return tool_name.replace("_", " ").title()

    def _generate_conversational_response(self, user_message: str) -> str:
        """
        Generate a friendly conversational response using LLM or fallback.
        Used for greetings, questions, etc.
        """
        if self.openai_client:
            try:
                response = self.openai_client.chat.completions.create(
                    model=get_chat_model(),
                    messages=[
                        {"role": "system", "content": """You are a friendly audio editing assistant for Audacity.
Be helpful, warm, and concise. You can help with:
- Selecting audio (by time range, all, etc.)
- Applying effects (noise reduction, normalize, amplify, fade in/out, etc.)
- Editing (cut, copy, paste, delete, split, join, trim)
- Playback controls (play, stop, pause)
- Creating tracks

Keep responses brief (1-2 sentences). Be conversational and helpful."""},
                        *self.conversation_history[-6:],  # Include recent context
                        {"role": "user", "content": user_message}
                    ],
                    max_tokens=150,
                    temperature=0.7
                )
                return response.choices[0].message.content
            except Exception as e:
                print(f"Conversational response failed: {e}", file=sys.stderr)

        # Fallback responses
        msg_lower = user_message.lower().strip()
        if any(greet in msg_lower for greet in ["hello", "hi", "hey", "greetings"]):
            return "Hello! I'm your Audacity AI assistant. I can help you select audio, apply effects, edit tracks, and more. What would you like to do?"
        elif any(word in msg_lower for word in ["thank", "thanks"]):
            return "You're welcome! Let me know if you need anything else."
        elif any(word in msg_lower for word in ["help", "what can you do", "capabilities"]):
            return "I can help you with: selecting audio ranges, applying effects (like noise reduction or normalization), editing (cut, copy, paste, trim, split), playback controls, and creating tracks. Just tell me what you'd like to do!"
        elif any(word in msg_lower for word in ["how are you", "how's it going"]):
            return "I'm doing great, ready to help you edit some audio! What would you like to work on?"
        else:
            return "I'm not sure I understood that. I can help you select audio, apply effects, edit tracks, or control playback. What would you like to do?"
