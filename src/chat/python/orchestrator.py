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

from config import get_openai_api_key, is_openai_configured


class Intent(Enum):
    """User intent categories"""
    SELECT = "select"
    APPLY_EFFECT = "apply_effect"
    EDIT = "edit"
    CREATE_TRACK = "create_track"
    DELETE = "delete"
    PLAYBACK = "playback"
    UNKNOWN = "unknown"
    CLARIFICATION_NEEDED = "clarification_needed"


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
            # Parse intent
            intent = self._parse_intent(user_message)
            
            if intent == Intent.CLARIFICATION_NEEDED:
                return {
                    "type": "message",
                    "content": "I need more information to help you. Could you clarify what you'd like to do?"
                }
            
            # Break down task
            task_plan = self._create_task_plan(user_message, intent)
            
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
            
            # Generate response
            response_message = self._generate_response(user_message, intent, results)
            
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
    
    def _parse_intent(self, message: str) -> Intent:
        """
        Parse user intent from message
        Uses simple keyword matching for now, will use LLM later
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
    
    def _create_task_plan(self, message: str, intent: Intent) -> List[Dict[str, Any]]:
        """
        Create a plan of tasks to execute
        Returns list of task dictionaries
        """
        tasks = []
        
        if intent == Intent.SELECT:
            # Parse selection parameters from message
            tasks.append({
                "agent": "selection",
                "action": "select",
                "parameters": self._extract_selection_params(message)
            })
        
        elif intent == Intent.APPLY_EFFECT:
            # First select, then apply effect
            selection_params = self._extract_selection_params(message)
            if selection_params:
                tasks.append({
                    "agent": "selection",
                    "action": "select",
                    "parameters": selection_params
                })
            
            effect_name = self._extract_effect_name(message)
            tasks.append({
                "agent": "effect",
                "action": "apply",
                "parameters": {"effect": effect_name}
            })
        
        elif intent == Intent.EDIT:
            # Parse edit operation
            edit_type = self._extract_edit_type(message)
            tasks.append({
                "agent": "editing",
                "action": edit_type,
                "parameters": {}
            })
        
        elif intent == Intent.CREATE_TRACK:
            track_type = "stereo" if "stereo" in message.lower() else "mono"
            tasks.append({
                "agent": "track",
                "action": "create",
                "parameters": {"type": track_type}
            })
        
        elif intent == Intent.PLAYBACK:
            playback_action = self._extract_playback_action(message)
            tasks.append({
                "agent": "playback",
                "action": playback_action,
                "parameters": {}
            })
        
        return tasks
    
    def _extract_selection_params(self, message: str) -> Optional[Dict[str, Any]]:
        """Extract selection parameters from message"""
        # Simple extraction - look for time ranges
        # TODO: Use LLM to extract more complex parameters
        import re
        
        # Look for time patterns like "0:30" or "30 seconds" or "first 30 seconds"
        time_pattern = r"(\d+):(\d+)|(\d+)\s*(?:second|sec|minute|min)"
        matches = re.findall(time_pattern, message.lower())
        
        if matches:
            # For now, return placeholder
            return {"start_time": 0.0, "end_time": 30.0}
        
        # Look for "first X seconds"
        first_match = re.search(r"first\s+(\d+)\s*(?:second|sec)", message.lower())
        if first_match:
            seconds = float(first_match.group(1))
            return {"start_time": 0.0, "end_time": seconds}
        
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
            return self.tools.clip.split()
        elif action == "join":
            return self.tools.clip.join()
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

