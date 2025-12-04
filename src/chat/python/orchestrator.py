#!/usr/bin/env python3
"""
Orchestrator Agent
Main orchestration logic that receives user requests, parses intent,
and coordinates specialized agents to complete tasks.
"""

import json
import os
import sys
import uuid
from typing import Dict, Any, List, Optional
from enum import Enum

# Import OpenAI SDK when available
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

from config import get_openai_api_key, is_openai_configured, get_chat_model


class Intent(Enum):
    """User intent categories"""
    SELECT = "select"
    APPLY_EFFECT = "apply_effect"
    EDIT = "edit"
    CREATE_TRACK = "create_track"
    DELETE = "delete"
    PLAYBACK = "playback"
    ANALYZE = "analyze"
    GENERATE_TEXT = "generate_text"
    CONVERSATION = "conversation"  # General chat, greetings, questions
    UNKNOWN = "unknown"
    CLARIFICATION_NEEDED = "clarification_needed"


# System prompt for LLM-based intent parsing
INTENT_PARSING_PROMPT = """You are a friendly audio editing assistant for Audacity. Parse the user's request and return JSON with:

{
  "intent": "select|apply_effect|edit|create_track|delete|playback|analyze|generate_text|conversation|unknown",
  "parameters": {
    "effect_name": "noise_reduction|normalize|amplify|fade_in|fade_out|compressor|limiter|reverb (if applying effect)",
    "start_time": "float in seconds (if ANY time is mentioned)",
    "end_time": "float in seconds (if time range specified)",
    "edit_type": "cut|copy|paste|delete|split|join|trim|undo|redo (if editing)",
    "playback_action": "play|stop|pause|loop (if playback)",
    "track_type": "mono|stereo|label (if creating track)",
    "analysis_type": "transcribe|summarize|find_issues|detect_filler (if analyzing)",
    "generation_type": "show_notes|description|social_post (if generating text)"
  },
  "requires_transcription": true or false,
  "confidence": "high|medium|low"
}

IMPORTANT: Use "conversation" intent for:
- Greetings (hi, hello, hey, good morning, etc.)
- Questions about capabilities (what can you do?, help, etc.)
- General chat that is not an audio editing command
- Gratitude (thanks, thank you, etc.)

IMPORTANT: Always extract time parameters when mentioned, even for edit commands!
- "split at 2s" → intent: edit, edit_type: split, start_time: 2.0
- "cut from 1s to 3s" → intent: edit, edit_type: cut, start_time: 1.0, end_time: 3.0
- "trim the last second" → intent: edit, edit_type: trim (trim removes audio outside selection)
- "delete at 5 seconds" → intent: edit, edit_type: delete, start_time: 5.0

Available tools:
- Selection: select all, clear selection, set time selection (start/end in seconds)
- Effects: noise reduction, normalize, amplify, fade in/out, compressor, limiter, reverb (open dialogs, user adjusts)
- Editing: cut, copy, paste, delete, split, join, trim, undo, redo
- Playback: play, stop, pause, loop
- Track: create mono/stereo/label track, delete track

Time parsing examples:
- "from 2s to 5s" → start_time: 2.0, end_time: 5.0
- "at 3 seconds" → start_time: 3.0 (single point)
- "first 10 seconds" → start_time: 0.0, end_time: 10.0
- "0:30 to 1:00" → start_time: 30.0, end_time: 60.0
- "split at 2s" → start_time: 2.0

Always return valid JSON. If unsure, set confidence to "low".
"""


class OrchestratorAgent:
    """
    Main orchestrator that:
    1. Receives user requests
    2. Parses intent using LLM
    3. Breaks down tasks
    4. Delegates to specialized agents
    5. Aggregates results
    """
    
    def __init__(self, selection_agent, effect_agent, tools):
        """
        Initialize orchestrator

        Args:
            selection_agent: SelectionAgent instance
            effect_agent: EffectAgent instance
            tools: ToolRegistry instance
        """
        self.selection_agent = selection_agent
        self.effect_agent = effect_agent
        self.tools = tools

        # Conversation memory
        self.conversation_history: List[Dict[str, str]] = []
        self.last_action: Optional[Dict[str, Any]] = None
        self.last_parameters: Optional[Dict[str, Any]] = None

        # Initialize OpenAI client if available and configured
        self.openai_client = None
        if OPENAI_AVAILABLE and is_openai_configured():
            api_key = get_openai_api_key()
            self.openai_client = OpenAI(api_key=api_key)
            print("OpenAI client initialized", file=sys.stderr)
        elif OPENAI_AVAILABLE and not is_openai_configured():
            print("Warning: OpenAI SDK available but OPENAI_API_KEY not set. Using keyword-based intent parsing.", file=sys.stderr)
    
    def process_request(self, user_message: str) -> Dict[str, Any]:
        """
        Process user request and return response

        Args:
            user_message: User's natural language request

        Returns:
            Dict with 'message', 'approval_request', or 'error'
        """
        try:
            # Add to conversation history
            self.conversation_history.append({"role": "user", "content": user_message})

            # Limit history to last 10 exchanges
            if len(self.conversation_history) > 20:
                self.conversation_history = self.conversation_history[-20:]

            # Parse intent using LLM if available, otherwise keyword-based
            intent, parameters = self._parse_intent_with_llm(user_message)

            if intent == Intent.CLARIFICATION_NEEDED:
                response = {
                    "type": "message",
                    "content": "I need more information to help you. Could you clarify what you'd like to do?"
                }
                self.conversation_history.append({"role": "assistant", "content": response["content"]})
                return response

            # Handle conversational messages (greetings, questions, etc.)
            if intent == Intent.CONVERSATION or intent == Intent.UNKNOWN:
                response_message = self._generate_conversational_response(user_message)
                self.conversation_history.append({"role": "assistant", "content": response_message})
                return {
                    "type": "message",
                    "content": response_message,
                    "can_undo": False
                }

            # Store parameters for potential "do it again" requests
            self.last_parameters = parameters

            # Break down task (now passing parameters from LLM)
            task_plan = self._create_task_plan(user_message, intent, parameters)
            
            # Check if operations require approval
            requires_approval = self._requires_approval(task_plan)
            
            if requires_approval:
                # Generate preview and request approval
                preview = self._generate_preview(task_plan, user_message)
                approval_id = self._generate_approval_id()
                
                # Determine approval mode: step-by-step for multi-step, batch for single
                approval_mode = "step_by_step" if len(task_plan) > 1 else "batch"
                
                return {
                    "type": "approval_request",
                    "approval_id": approval_id,
                    "description": self._generate_approval_description(task_plan, user_message),
                    "preview": preview,
                    "task_plan": task_plan,  # Store for execution after approval
                    "approval_mode": approval_mode,  # "batch" or "step_by_step"
                    "current_step": 0 if approval_mode == "step_by_step" else None,
                    "total_steps": len(task_plan) if approval_mode == "step_by_step" else None
                }
            
            # Execute tasks directly (no approval needed)
            results = self._execute_tasks(task_plan)

            # Store last action for "do it again" requests
            self.last_action = {"intent": intent, "task_plan": task_plan, "results": results}

            # Generate response
            response_message = self._generate_response(user_message, intent, results)

            # Add to conversation history
            self.conversation_history.append({"role": "assistant", "content": response_message})

            # Determine if operation can be undone
            can_undo = self._should_mark_undoable(intent)

            return {
                "type": "message",
                "content": response_message,
                "can_undo": can_undo
            }

        except Exception as e:
            return {
                "type": "error",
                "content": f"Error processing request: {str(e)}"
            }
    
    def process_approval(self, approval_id: str, approved: bool, task_plan: List[Dict[str, Any]] = None, 
                        approval_mode: str = "batch", current_step: int = 0, batch_mode: bool = False) -> Dict[str, Any]:
        """
        Process approval response and execute tasks if approved
        
        Args:
            approval_id: ID of the approval request
            approved: Whether user approved
            task_plan: Task plan to execute (if approved)
            approval_mode: "batch" or "step_by_step"
            current_step: Current step index for step-by-step mode
            
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
        
        # If batch_mode is requested, switch to batch execution
        if batch_mode and approval_mode == "step_by_step":
            approval_mode = "batch"
        
        if approval_mode == "step_by_step":
            # Execute one step at a time
            if current_step < len(task_plan):
                # Execute current step
                step_task = task_plan[current_step]
                results = self._execute_tasks([step_task])
                
                # Check if there are more steps
                if current_step + 1 < len(task_plan):
                    # Request approval for next step
                    next_step_preview = self._generate_preview([task_plan[current_step + 1]], "")
                    return {
                        "type": "approval_request",
                        "approval_id": f"{approval_id}_step_{current_step + 1}",
                        "description": f"Step {current_step + 2} of {len(task_plan)}: {self._generate_approval_description([task_plan[current_step + 1]], '')}",
                        "preview": next_step_preview,
                        "task_plan": task_plan,
                        "approval_mode": "step_by_step",
                        "current_step": current_step + 1,
                        "total_steps": len(task_plan)
                    }
                else:
                    # All steps completed
                    response_message = self._generate_response("", Intent.UNKNOWN, results)
                    can_undo = True  # Multi-step operations can be undone
                    return {
                        "type": "message",
                        "content": f"All {len(task_plan)} steps completed successfully. {response_message}",
                        "can_undo": can_undo
                    }
            else:
                return {
                    "type": "message",
                    "content": "All steps already completed."
                }
        else:
            # Batch mode: execute all tasks at once
            results = self._execute_tasks(task_plan)
            
            # Generate response
            response_message = self._generate_response("", Intent.UNKNOWN, results)
            
            # Determine if operation can be undone
            can_undo = len(task_plan) > 0  # Batch operations can be undone
            
            return {
                "type": "message",
                "content": response_message,
                "can_undo": can_undo
            }
    
    def _parse_intent_with_llm(self, message: str) -> tuple:
        """
        Parse user intent using LLM if available, with keyword fallback.

        Returns:
            tuple: (Intent, parameters dict)
        """
        # If no OpenAI client, fall back to keyword parsing
        if not self.openai_client:
            intent = self._parse_intent(message)
            parameters = self._extract_selection_params(message) or {}
            return intent, parameters

        try:
            response = self.openai_client.chat.completions.create(
                model=get_chat_model(),
                messages=[
                    {"role": "system", "content": INTENT_PARSING_PROMPT},
                    {"role": "user", "content": message}
                ],
                response_format={"type": "json_object"},
                max_tokens=500,
                temperature=0.1
            )

            result = json.loads(response.choices[0].message.content)

            # Parse intent from result
            intent_str = result.get("intent", "unknown")
            try:
                intent = Intent(intent_str)
            except ValueError:
                intent = Intent.UNKNOWN

            # Extract parameters
            parameters = result.get("parameters", {})

            # Log for debugging
            print(f"LLM parsed: intent={intent_str}, params={parameters}", file=sys.stderr)

            return intent, parameters

        except Exception as e:
            # On any error, fall back to keyword parsing
            print(f"LLM parsing failed: {e}, falling back to keywords", file=sys.stderr)
            intent = self._parse_intent(message)
            parameters = self._extract_selection_params(message) or {}
            return intent, parameters

    def _parse_intent(self, message: str) -> Intent:
        """
        Parse user intent from message using keyword matching.
        Used as fallback when LLM is not available.
        """
        message_lower = message.lower()
        
        # Selection keywords
        if any(word in message_lower for word in ["select", "choose", "pick", "highlight"]):
            return Intent.SELECT
        
        # Effect keywords
        if any(word in message_lower for word in ["apply", "add", "use", "effect", "filter", "noise", "fade", "amplify"]):
            return Intent.APPLY_EFFECT
        
        # Edit keywords
        if any(word in message_lower for word in ["cut", "copy", "paste", "delete", "remove", "split", "join"]):
            return Intent.EDIT
        
        # Track creation
        if any(word in message_lower for word in ["create", "new", "add track"]):
            return Intent.CREATE_TRACK
        
        # Playback
        if any(word in message_lower for word in ["play", "stop", "pause", "seek"]):
            return Intent.PLAYBACK
        
        # Delete
        if any(word in message_lower for word in ["delete", "remove", "clear"]):
            return Intent.DELETE
        
        return Intent.UNKNOWN
    
    def _create_task_plan(self, message: str, intent: Intent, parameters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Create a plan of tasks to execute.

        Args:
            message: Original user message
            intent: Parsed intent
            parameters: Parameters from LLM parsing (if available)

        Returns:
            List of task dictionaries
        """
        tasks = []
        params = parameters or {}

        if intent == Intent.SELECT:
            # Use LLM-extracted time parameters, or fall back to regex extraction
            selection_params = {}
            if "start_time" in params and "end_time" in params:
                selection_params = {
                    "start_time": params["start_time"],
                    "end_time": params["end_time"]
                }
            else:
                selection_params = self._extract_selection_params(message) or {}

            tasks.append({
                "agent": "selection",
                "action": "select",
                "parameters": selection_params
            })

        elif intent == Intent.APPLY_EFFECT:
            # First select if time range specified, then apply effect
            selection_params = {}
            if "start_time" in params and "end_time" in params:
                selection_params = {
                    "start_time": params["start_time"],
                    "end_time": params["end_time"]
                }
            else:
                selection_params = self._extract_selection_params(message)

            if selection_params:
                tasks.append({
                    "agent": "selection",
                    "action": "select",
                    "parameters": selection_params
                })

            # Get effect name from LLM params or extract from message
            effect_name = params.get("effect_name") or self._extract_effect_name(message)
            tasks.append({
                "agent": "effect",
                "action": "apply",
                "parameters": {"effect": effect_name}
            })

        elif intent == Intent.EDIT:
            # Get edit type from LLM params or extract from message
            edit_type = params.get("edit_type") or self._extract_edit_type(message)

            # Build parameters for the edit action
            edit_params = {}

            # For split operations with a time, pass the time directly
            if edit_type == "split" and "start_time" in params:
                edit_params["split_time"] = float(params["start_time"])
            # For other operations that need a time range (cut, delete, trim)
            elif "start_time" in params and edit_type in ("cut", "delete", "trim"):
                start_time = float(params["start_time"])
                end_time = float(params.get("end_time", start_time + 0.5))  # Default 0.5s range
                tasks.append({
                    "agent": "selection",
                    "action": "select",
                    "parameters": {
                        "start_time": start_time,
                        "end_time": end_time
                    }
                })

            tasks.append({
                "agent": "editing",
                "action": edit_type,
                "parameters": edit_params
            })

        elif intent == Intent.CREATE_TRACK:
            # Get track type from LLM params or extract from message
            track_type = params.get("track_type") or ("stereo" if "stereo" in message.lower() else "mono")
            tasks.append({
                "agent": "track",
                "action": "create",
                "parameters": {"type": track_type}
            })
        
        elif intent == Intent.PLAYBACK:
            playback_action = params.get("playback_action") or self._extract_playback_action(message)
            tasks.append({
                "agent": "playback",
                "action": playback_action,
                "parameters": {}
            })

        return tasks
    
    def _extract_selection_params(self, message: str) -> Optional[Dict[str, Any]]:
        """Extract selection parameters from message"""
        import re
        msg = message.lower()

        # Pattern: "from Xs to Ys" or "from X to Y seconds"
        from_to_match = re.search(
            r"from\s+(\d+(?:\.\d+)?)\s*(?:s|sec|seconds?)?\s+to\s+(\d+(?:\.\d+)?)\s*(?:s|sec|seconds?)?",
            msg
        )
        if from_to_match:
            return {
                "start_time": float(from_to_match.group(1)),
                "end_time": float(from_to_match.group(2))
            }

        # Pattern: "Xs to Ys" or "X to Y seconds"
        range_match = re.search(
            r"(\d+(?:\.\d+)?)\s*(?:s|sec|seconds?)?\s+to\s+(\d+(?:\.\d+)?)\s*(?:s|sec|seconds?)?",
            msg
        )
        if range_match:
            return {
                "start_time": float(range_match.group(1)),
                "end_time": float(range_match.group(2))
            }

        # Pattern: "at Xs" - select a small range around that point
        at_match = re.search(r"at\s+(\d+(?:\.\d+)?)\s*(?:s|sec|seconds?)?", msg)
        if at_match:
            time_point = float(at_match.group(1))
            # Select 0.5s around the point
            return {
                "start_time": max(0, time_point - 0.25),
                "end_time": time_point + 0.25
            }

        # Pattern: "first X seconds"
        first_match = re.search(r"first\s+(\d+(?:\.\d+)?)\s*(?:s|sec|seconds?)?", msg)
        if first_match:
            seconds = float(first_match.group(1))
            return {"start_time": 0.0, "end_time": seconds}

        # Pattern: "last X seconds" - would need track length, skip for now

        # Pattern: time format "M:SS" like "0:30" to "1:00"
        time_range_match = re.search(
            r"(\d+):(\d+)\s*(?:to|-)\s*(\d+):(\d+)",
            msg
        )
        if time_range_match:
            start_min, start_sec = int(time_range_match.group(1)), int(time_range_match.group(2))
            end_min, end_sec = int(time_range_match.group(3)), int(time_range_match.group(4))
            return {
                "start_time": start_min * 60 + start_sec,
                "end_time": end_min * 60 + end_sec
            }

        return None
    
    def _extract_effect_name(self, message: str) -> str:
        """Extract effect name from message"""
        message_lower = message.lower()
        
        if "noise" in message_lower:
            return "NoiseReduction"
        elif "amplify" in message_lower or "volume" in message_lower:
            return "Amplify"
        elif "normalize" in message_lower:
            return "Normalize"
        elif "fade in" in message_lower:
            return "FadeIn"
        elif "fade out" in message_lower:
            return "FadeOut"
        
        return "Amplify"  # Default
    
    def _extract_edit_type(self, message: str) -> str:
        """Extract edit operation type"""
        message_lower = message.lower()
        
        if "cut" in message_lower:
            return "cut"
        elif "copy" in message_lower:
            return "copy"
        elif "paste" in message_lower:
            return "paste"
        elif "delete" in message_lower or "remove" in message_lower:
            return "delete"
        elif "split" in message_lower:
            return "split"
        elif "join" in message_lower:
            return "join"
        
        return "cut"  # Default
    
    def _extract_playback_action(self, message: str) -> str:
        """Extract playback action"""
        message_lower = message.lower()
        
        if "play" in message_lower:
            return "play"
        elif "stop" in message_lower:
            return "stop"
        elif "pause" in message_lower:
            return "pause"
        
        return "play"
    
    def _execute_tasks(self, task_plan: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Execute task plan and return results
        """
        results = []
        
        for task in task_plan:
            agent = task["agent"]
            action = task["action"]
            parameters = task.get("parameters", {})
            
            try:
                if agent == "selection":
                    result = self.selection_agent.handle_task(action, parameters)
                elif agent == "effect":
                    result = self.effect_agent.handle_task(action, parameters)
                elif agent == "editing":
                    result = self._execute_editing_task(action, parameters)
                elif agent == "track":
                    result = self._execute_track_task(action, parameters)
                elif agent == "playback":
                    result = self._execute_playback_task(action, parameters)
                else:
                    result = {"success": False, "error": f"Unknown agent: {agent}"}
                
                results.append(result)
                
            except Exception as e:
                results.append({
                    "success": False,
                    "error": str(e),
                    "task": task
                })
        
        return results
    
    def _execute_editing_task(self, action: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Execute editing task"""
        if action == "cut":
            return self.tools.editing.cut()
        elif action == "copy":
            return self.tools.editing.copy()
        elif action == "paste":
            return self.tools.editing.paste()
        elif action == "delete":
            return self.tools.editing.delete()
        elif action == "split":
            # If we have a split_time parameter, use split_at_time
            split_time = parameters.get("split_time")
            if split_time is not None:
                return self.tools.clip.split_at_time(float(split_time))
            # Otherwise, ensure all tracks are selected and split at cursor
            self.tools.selection.select_all_tracks()
            return self.tools.clip.split()
        elif action == "join":
            # Ensure all tracks are selected before join
            self.tools.selection.select_all_tracks()
            return self.tools.clip.join()
        elif action == "trim":
            return self.tools.clip.trim_outside_selection()
        elif action == "undo":
            return self.tools.editing.undo()
        elif action == "redo":
            return self.tools.editing.redo()
        else:
            return {"success": False, "error": f"Unknown edit action: {action}"}
    
    def _execute_track_task(self, action: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Execute track task"""
        if action == "create":
            track_type = parameters.get("type", "mono")
            if track_type == "stereo":
                return self.tools.track.create_stereo_track()
            else:
                return self.tools.track.create_mono_track()
        else:
            return {"success": False, "error": f"Unknown track action: {action}"}
    
    def _execute_playback_task(self, action: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Execute playback task"""
        if action == "play":
            return self.tools.playback.play()
        elif action == "stop":
            return self.tools.playback.stop()
        elif action == "pause":
            return self.tools.playback.pause()
        else:
            return {"success": False, "error": f"Unknown playback action: {action}"}
    
    def _requires_approval(self, task_plan: List[Dict[str, Any]]) -> bool:
        """
        Determine if operations require user approval
        Destructive operations or effects typically require approval
        """
        destructive_actions = ["delete", "cut", "remove", "apply_effect"]
        
        for task in task_plan:
            action = task.get("action", "")
            agent = task.get("agent", "")
            
            # Effects always require approval
            if agent == "effect":
                return True
            
            # Destructive editing operations require approval
            if agent == "editing" and action in ["delete", "cut"]:
                return True
            
            # Track deletion requires approval
            if agent == "track" and action == "delete":
                return True
        
        return False
    
    def _generate_approval_id(self) -> str:
        """Generate unique approval ID"""
        return f"approval_{uuid.uuid4().hex[:8]}"
    
    def _generate_preview(self, task_plan: List[Dict[str, Any]], user_message: str) -> str:
        """
        Generate preview description of what will happen
        """
        preview_parts = []
        
        for task in task_plan:
            agent = task.get("agent", "")
            action = task.get("action", "")
            parameters = task.get("parameters", {})
            
            if agent == "selection":
                if "start_time" in parameters and "end_time" in parameters:
                    preview_parts.append(
                        f"Select time range: {parameters['start_time']:.2f}s - {parameters['end_time']:.2f}s"
                    )
                elif "track_ids" in parameters:
                    preview_parts.append(f"Select {len(parameters['track_ids'])} track(s)")
                elif "clip_keys" in parameters:
                    preview_parts.append(f"Select {len(parameters['clip_keys'])} clip(s)")
            
            elif agent == "effect":
                effect_name = parameters.get("effect", "effect")
                preview_parts.append(f"Apply effect: {effect_name}")
            
            elif agent == "editing":
                preview_parts.append(f"Edit operation: {action}")
            
            elif agent == "track":
                if action == "create":
                    track_type = parameters.get("type", "mono")
                    preview_parts.append(f"Create new {track_type} track")
                elif action == "delete":
                    preview_parts.append("Delete selected track(s)")
        
        if not preview_parts:
            return "Execute operation"
        
        return " • ".join(preview_parts)
    
    def _generate_approval_description(self, task_plan: List[Dict[str, Any]], user_message: str) -> str:
        """
        Generate human-readable description for approval request
        """
        if len(task_plan) == 1:
            task = task_plan[0]
            agent = task.get("agent", "")
            action = task.get("action", "")
            
            if agent == "effect":
                effect = task.get("parameters", {}).get("effect", "effect")
                return f"Apply {effect} effect to selection"
            elif agent == "editing":
                return f"Perform {action} operation"
            elif agent == "track":
                if action == "create":
                    return "Create new track"
                elif action == "delete":
                    return "Delete track(s)"
        
        return f"Execute {len(task_plan)} operation(s)"
    
    def _generate_response(self, original_message: str, intent: Intent, results: List[Dict[str, Any]]) -> str:
        """
        Generate human-readable response from results
        """
        # Check if all tasks succeeded
        all_success = all(r.get("success", False) for r in results)
        
        if all_success:
            if intent == Intent.SELECT:
                return "Selection updated successfully."
            elif intent == Intent.APPLY_EFFECT:
                return "Effect applied successfully."
            elif intent == Intent.EDIT:
                return "Edit operation completed."
            elif intent == Intent.CREATE_TRACK:
                return "Track created successfully."
            elif intent == Intent.PLAYBACK:
                return "Playback control executed."
            else:
                return "Operation completed successfully."
        else:
            # Some tasks failed
            errors = [r.get("error", "Unknown error") for r in results if not r.get("success", False)]
            return f"Operation completed with errors: {', '.join(errors)}"
    
    def _should_mark_undoable(self, intent: Intent) -> bool:
        """
        Determine if an operation should be marked as undoable
        """
        # Most operations can be undone except playback controls
        return intent != Intent.PLAYBACK

    def _generate_conversational_response(self, user_message: str) -> str:
        """
        Generate a friendly conversational response using LLM or fallback.
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
- Editing (cut, copy, paste, delete, split, join)
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
            return "I can help you with: selecting audio ranges, applying effects (like noise reduction or normalization), editing (cut, copy, paste), playback controls, and creating tracks. Just tell me what you'd like to do!"
        elif any(word in msg_lower for word in ["how are you", "how's it going"]):
            return "I'm doing great, ready to help you edit some audio! What would you like to work on?"
        else:
            return "I'm not sure I understood that. I can help you select audio, apply effects, edit tracks, or control playback. What would you like to do?"

