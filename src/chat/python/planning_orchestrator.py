#!/usr/bin/env python3
"""
Planning Orchestrator
Coordinates all planning phases and manages state machine transitions.
Wraps OrchestratorAgent for execution.
"""

import json
import sys
import logging
from typing import Dict, Any, Optional, List

from planning_state import PlanningState, PlanningPhase
from state_discovery import StateDiscovery
from intent_planner import IntentPlanner
from prerequisite_resolver import PrerequisiteResolver
from pre_execution_validator import PreExecutionValidator
from state_preparation import StatePreparationOrchestrator, PreparationStep
from orchestrator import OrchestratorAgent

# Set up logging
logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    ))
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)  # Changed to DEBUG to see retry logic


class PlanningOrchestrator:
    """
    Main orchestrator that coordinates planning phases and execution.
    Wraps OrchestratorAgent for actual tool execution.
    """

    def __init__(self, tool_registry, orchestrator_agent: OrchestratorAgent):
        """
        Initialize planning orchestrator.

        Args:
            tool_registry: ToolRegistry instance
            orchestrator_agent: OrchestratorAgent instance for execution
        """
        self.tool_registry = tool_registry
        self.orchestrator_agent = orchestrator_agent

        # Initialize phases
        self.state_discovery = StateDiscovery(tool_registry)
        self.intent_planner = IntentPlanner(tool_registry)
        self.prerequisite_resolver = PrerequisiteResolver(tool_registry)
        self.pre_execution_validator = PreExecutionValidator(tool_registry)
        self.state_preparation = StatePreparationOrchestrator(tool_registry)

    def process_request(self, user_message: str) -> Dict[str, Any]:
        """
        Process user request through planning phases.

        Args:
            user_message: User's request

        Returns:
            Response dictionary
        """
        logger.info(f"Processing request: {user_message[:100]}...")
        
        # Initialize planning state
        planning_state = PlanningState(user_message)

        try:
            # Phase 1: State Discovery
            logger.info("Phase 1: State Discovery")
            if not planning_state.transition_to(PlanningPhase.STATE_DISCOVERY):
                error_msg = "Failed to transition to state discovery"
                logger.error(error_msg)
                return self._error_response(error_msg)

            try:
                discovered_state = self.state_discovery.discover_state(
                    user_message,
                    planning_state.discovered_state
                )
                logger.info(f"State discovered: {list(discovered_state.keys())}")
                planning_state.set_state_snapshot(discovered_state)
            except Exception as e:
                error_msg = f"State discovery failed: {str(e)}"
                logger.error(error_msg, exc_info=True)
                planning_state.set_error(error_msg)
                return self._error_response(error_msg)

            # Phase 2: Intent Planning
            logger.info("Phase 2: Intent Planning")
            if not planning_state.transition_to(PlanningPhase.PLANNING):
                error_msg = "Failed to transition to planning"
                logger.error(error_msg)
                return self._error_response(error_msg)

            try:
                tool_calls, needs_more_state, error = self.intent_planner.plan(
                    user_message,
                    planning_state.discovered_state
                )

                if error:
                    logger.error(f"Intent planning error: {error}")
                    planning_state.set_error(error)
                    return self._error_response(error)
                
                logger.info(f"Planned {len(tool_calls)} tool calls: {[tc.get('tool_name') for tc in tool_calls]}")
            except Exception as e:
                error_msg = f"Intent planning failed: {str(e)}"
                logger.error(error_msg, exc_info=True)
                planning_state.set_error(error_msg)
                return self._error_response(error_msg)

            # If LLM wants more state, loop back to state discovery
            if needs_more_state:
                logger.info("LLM requested more state, executing state queries")
                # Execute any state queries from the plan
                state_queries = [tc for tc in tool_calls if tc["tool_name"].startswith("get_") or tc["tool_name"] == "has_time_selection"]
                if state_queries:
                    logger.info(f"Executing {len(state_queries)} state queries")
                    # Execute state queries and update state
                    for query in state_queries:
                        try:
                            logger.debug(f"Executing state query: {query['tool_name']}")
                            result = self.tool_registry.execute_by_name(
                                query["tool_name"],
                                query.get("arguments", {})
                            )
                            if result.get("success"):
                                # Update state snapshot
                                value = result.get("value")
                                state_key_map = {
                                    "has_time_selection": "has_time_selection",
                                    "get_selection_start_time": "selection_start_time",
                                    "get_selection_end_time": "selection_end_time",
                                    "get_cursor_position": "cursor_position",
                                    "get_total_project_time": "total_project_time",
                                    "get_track_list": "track_list",
                                    "get_selected_tracks": "selected_tracks",
                                    "get_selected_clips": "selected_clips",
                                    "get_all_labels": "all_labels"
                                }
                                state_key = state_key_map.get(query["tool_name"])
                                if state_key:
                                    planning_state.discovered_state[state_key] = value
                                    logger.debug(f"Updated state: {state_key} = {value}")
                            else:
                                logger.warning(f"State query failed: {query['tool_name']}: {result.get('error')}")
                        except Exception as e:
                            logger.error(f"Error executing state query {query['tool_name']}: {e}", exc_info=True)

                    # Remove state queries from plan (they're done)
                    tool_calls = [tc for tc in tool_calls if not (tc["tool_name"].startswith("get_") or tc["tool_name"] == "has_time_selection")]
                    logger.info(f"Removed state queries, {len(tool_calls)} tools remaining in plan")

            # CRITICAL FIX: If plan is empty after executing state queries, re-query LLM with updated state
            # This handles the case where LLM only returns state queries in the first call
            logger.info(f"After state query processing: tool_calls={len(tool_calls) if tool_calls else 0}, needs_more_state={needs_more_state}")
            if not tool_calls:
                logger.warning("CRITICAL: Plan is empty after state queries - re-querying LLM with updated state")
                logger.info(f"Current state snapshot keys: {list(planning_state.discovered_state.keys())}")
                try:
                    # Call intent planner again with updated state
                    tool_calls, needs_more_state_retry, error = self.intent_planner.plan(
                        user_message,
                        planning_state.discovered_state
                    )

                    if error:
                        logger.error(f"Intent planning error on retry: {error}")
                        planning_state.set_error(error)
                        return self._error_response(error)
                    
                    logger.info(f"Retry planned {len(tool_calls)} tool calls: {[tc.get('tool_name') for tc in tool_calls]}")
                    
                    # If LLM returns more state queries on retry, execute them and try once more
                    if needs_more_state_retry and tool_calls:
                        state_queries_retry = [tc for tc in tool_calls if tc["tool_name"].startswith("get_") or tc["tool_name"] == "has_time_selection"]
                        if state_queries_retry:
                            logger.info(f"Retry also returned {len(state_queries_retry)} state queries - executing them")
                            # Execute retry state queries
                            for query in state_queries_retry:
                                try:
                                    result = self.tool_registry.execute_by_name(
                                        query["tool_name"],
                                        query.get("arguments", {})
                                    )
                                    if result.get("success"):
                                        value = result.get("value")
                                        state_key_map = {
                                            "has_time_selection": "has_time_selection",
                                            "get_selection_start_time": "selection_start_time",
                                            "get_selection_end_time": "selection_end_time",
                                            "get_cursor_position": "cursor_position",
                                            "get_total_project_time": "total_project_time",
                                            "get_track_list": "track_list",
                                            "get_selected_tracks": "selected_tracks",
                                            "get_selected_clips": "selected_clips",
                                            "get_all_labels": "all_labels"
                                        }
                                        state_key = state_key_map.get(query["tool_name"])
                                        if state_key:
                                            planning_state.discovered_state[state_key] = value
                                except Exception as e:
                                    logger.warning(f"Error executing retry state query {query['tool_name']}: {e}")
                            
                            # Remove state queries and check if we have actual tool calls
                            tool_calls = [tc for tc in tool_calls if not (tc["tool_name"].startswith("get_") or tc["tool_name"] == "has_time_selection")]
                            logger.info(f"After retry state queries, {len(tool_calls)} tools remaining")
                    
                    # If still no tool calls after retry, return error
                    if not tool_calls:
                        logger.error("No tool calls generated even after state queries and retry")
                        return {
                            "type": "message",
                            "content": "I'm not sure how to help with that. Could you provide more details?",
                            "can_undo": False
                        }
                except Exception as e:
                    error_msg = f"Intent planning retry failed: {str(e)}"
                    logger.error(error_msg, exc_info=True)
                    planning_state.set_error(error_msg)
                    return self._error_response(error_msg)

            if not tool_calls:
                # No tool calls generated - might be conversational
                return {
                    "type": "message",
                    "content": "I'm not sure how to help with that. Could you provide more details?",
                    "can_undo": False
                }

            planning_state.set_execution_plan(tool_calls)

            # Phase 3: State Preparation (replaces Prerequisite Resolution and Pre-Execution Validation)
            logger.info("Phase 3: State Preparation")
            if not planning_state.transition_to(PlanningPhase.STATE_PREPARATION):
                error_msg = "Failed to transition to state preparation"
                logger.error(error_msg)
                return self._error_response(error_msg)

            try:
                # Use new State Preparation Orchestrator
                final_plan = []

                for tool_call in planning_state.execution_plan:
                    tool_name = tool_call.get("tool_name")
                    tool_args = tool_call.get("arguments", {})

                    # Prepare state for this tool
                    prep_result = self.state_preparation.prepare(
                        tool_name=tool_name,
                        tool_arguments=tool_args,
                        user_message=user_message,
                        initial_state=planning_state.discovered_state
                    )

                    # Handle clarification needed
                    if prep_result.needs_clarification:
                        logger.info(f"Tool {tool_name} needs clarification: {prep_result.clarification_message}")
                        return {
                            "type": "clarification_needed",
                            "content": prep_result.clarification_message,
                            "can_undo": False
                        }

                    # Handle errors
                    if prep_result.error:
                        logger.error(f"State preparation error for {tool_name}: {prep_result.error}")
                        # Fall back to legacy prerequisite resolver for this tool
                        logger.info(f"Falling back to legacy prerequisite resolver for {tool_name}")
                        resolved_plan_legacy, errors = self.prerequisite_resolver.resolve(
                            [tool_call],
                            planning_state.discovered_state
                        )
                        if errors:
                            error_msg = "; ".join(errors)
                            planning_state.set_error(error_msg)
                            return self._error_response(error_msg)
                        final_plan.extend(resolved_plan_legacy)
                        continue

                    # Add preparation steps to plan
                    for step in prep_result.preparation_steps:
                        final_plan.append({
                            "tool_name": step.tool_name,
                            "arguments": step.arguments
                        })
                        logger.debug(f"Added prep step: {step.tool_name} - {step.purpose}")

                    # Add the operation tool with potentially updated arguments
                    final_plan.append({
                        "tool_name": prep_result.operation_tool,
                        "arguments": prep_result.operation_arguments
                    })

                    # Update state snapshot with simulated changes for next tool
                    for step in prep_result.preparation_steps:
                        self.state_preparation._simulate_state_change(
                            step,
                            planning_state.discovered_state,
                            None  # InferenceResult not needed for simulation
                        )

                logger.info(f"State preparation complete. Final plan: {len(final_plan)} tools")
                logger.debug(f"Final plan: {[tc.get('tool_name') for tc in final_plan]}")
                resolved_plan = final_plan
                planning_state.set_execution_plan(resolved_plan)
                planning_state.mark_prerequisites_resolved()

            except Exception as e:
                error_msg = f"State preparation failed: {str(e)}"
                logger.error(error_msg, exc_info=True)
                planning_state.set_error(error_msg)
                return self._error_response(error_msg)

            # Re-query critical state before execution if stale or missing
            try:
                self._synchronize_state_before_execution(planning_state)
            except Exception as e:
                logger.warning(f"State synchronization warning: {e}", exc_info=True)
                # Continue with execution even if sync fails

            # Phase 4: Execution
            logger.info("Phase 4: Execution")
            if not planning_state.transition_to(PlanningPhase.EXECUTION):
                error_msg = "Failed to transition to execution"
                logger.error(error_msg)
                return self._error_response(error_msg)

            # Convert execution plan to format expected by OrchestratorAgent
            # We need to create tool_call objects that OrchestratorAgent expects
            # For now, we'll execute tools directly through tool_registry
            # and handle approval flow through orchestrator_agent

            # Check if any tools require approval
            destructive_tools = {"cut", "delete_selection", "delete_track", "trim_to_selection", "delete_all_tracks_ripple", "cut_all_tracks_ripple"}
            effect_tools = {
                "apply_noise_reduction", "apply_normalize", "apply_amplify",
                "apply_fade_in", "apply_fade_out", "apply_reverse", "apply_invert",
                "apply_normalize_loudness", "apply_compressor", "apply_limiter",
                "apply_truncate_silence", "repeat_last_effect"
            }

            requires_approval = any(
                tc.get("tool_name") in destructive_tools or tc.get("tool_name") in effect_tools
                for tc in resolved_plan
            )

            logger.info(f"Execution plan requires approval: {requires_approval}")

            if requires_approval:
                logger.info("Requesting approval for destructive/effect operations")
                # Use orchestrator's approval flow
                # Convert our plan format to orchestrator's format
                # Create mock tool_call objects for orchestrator
                class MockToolCall:
                    def __init__(self, tool_name, arguments, tool_call_id=None):
                        class Function:
                            def __init__(self, name, args):
                                self.name = name
                                self.arguments = json.dumps(args) if args else "{}"
                        self.function = Function(tool_name, arguments)
                        self.id = tool_call_id or f"call_{tool_name}"

                mock_tool_calls = [
                    MockToolCall(tc["tool_name"], tc.get("arguments", {}), tc.get("tool_call_id"))
                    for tc in resolved_plan
                ]

                return self.orchestrator_agent._execute_tool_calls(mock_tool_calls, user_message)
            else:
                # Execute directly
                logger.info(f"Executing {len(resolved_plan)} tools directly (no approval needed)")
                results = []
                failed_tools = []
                
                for tool_call in resolved_plan:
                    tool_name = tool_call.get("tool_name")
                    arguments = tool_call.get("arguments", {})
                    
                    try:
                        logger.info(f"Executing tool: {tool_name}({arguments})")
                        result = self.tool_registry.execute_by_name(tool_name, arguments)
                        
                        if result.get("success"):
                            logger.info(f"Tool {tool_name} succeeded")
                        else:
                            error_msg = result.get("error", "unknown error")
                            logger.error(f"Tool {tool_name} failed: {error_msg}")
                            failed_tools.append(tool_name)
                        
                        results.append({
                            "tool_name": tool_name,
                            "result": result
                        })
                        planning_state.add_execution_result({
                            "tool_name": tool_name,
                            "result": result
                        })
                    except Exception as e:
                        logger.error(f"Exception executing tool {tool_name}: {e}", exc_info=True)
                        failed_tools.append(tool_name)
                        results.append({
                            "tool_name": tool_name,
                            "result": {"success": False, "error": str(e)}
                        })
                        planning_state.add_execution_result({
                            "tool_name": tool_name,
                            "result": {"success": False, "error": str(e)}
                        })

                # Generate response
                all_success = all(r["result"].get("success", False) for r in results)
                tool_names = [r["tool_name"] for r in results]

                # Check for special result types that should be displayed directly
                response_text = None
                can_undo = True
                
                # Check if analyze_transcript returned analysis content
                for r in results:
                    if r["tool_name"] == "analyze_transcript" and r["result"].get("success"):
                        analysis = r["result"].get("analysis")
                        stats = r["result"].get("stats", {})
                        
                        if analysis:
                            # Build formatted response with analysis and stats
                            response_parts = [analysis]
                            
                            # Add stats summary if available
                            if stats:
                                stats_lines = [
                                    f"\n## Summary Statistics",
                                    f"- Duration: {stats.get('duration_formatted', 'N/A')}",
                                    f"- Word count: {stats.get('word_count', 0):,}",
                                    f"- Words per minute: {stats.get('words_per_minute', 0):.1f}",
                                    f"- Filler words: {stats.get('filler_count', 0)} ({stats.get('fillers_per_minute', 0):.1f}/min)"
                                ]
                                response_parts.append("\n".join(stats_lines))
                            
                            response_text = "\n\n".join(response_parts)
                            logger.info("Including transcript analysis in response")
                            break
                
                # If no special content, use default response
                if response_text is None:
                    if all_success:
                        response_text = f"Done! Executed: {', '.join(tool_names)}"
                        can_undo = True
                        logger.info("All tools executed successfully")
                    else:
                        errors = [f"{r['tool_name']}: {r['result'].get('error', 'unknown')}"
                                  for r in results if not r["result"].get("success", False)]
                        response_text = f"Completed with errors: {'; '.join(errors)}"
                        can_undo = False
                        logger.warning(f"Partial execution failure: {failed_tools}")

                planning_state.transition_to(PlanningPhase.COMPLETE)

                return {
                    "type": "message",
                    "content": response_text,
                    "can_undo": can_undo
                }

        except Exception as e:
            error_msg = f"Unexpected error in process_request: {str(e)}"
            logger.error(error_msg, exc_info=True)
            planning_state.set_error(str(e))
            return self._error_response(error_msg)

    def _synchronize_state_before_execution(self, planning_state: PlanningState):
        """
        Re-query critical state before execution if stale or missing.
        
        Args:
            planning_state: Planning state to synchronize
        """
        # Check if state is stale
        if planning_state.is_state_stale():
            logger.info("State is stale, re-querying critical state before execution")
        
        # Get critical state keys needed for execution
        critical_keys = planning_state.get_critical_state_keys()
        
        if not critical_keys:
            logger.debug("No critical state keys identified for execution plan")
            return
        
        # Map state keys to query tool names
        key_to_query = {
            "has_time_selection": "has_time_selection",
            "selection_start_time": "get_selection_start_time",
            "selection_end_time": "get_selection_end_time",
            "cursor_position": "get_cursor_position",
            "selected_tracks": "get_selected_tracks",
            "selected_clips": "get_selected_clips"
        }
        
        # Re-query critical state
        updated = False
        for key in critical_keys:
            query_tool = key_to_query.get(key)
            if not query_tool:
                continue
            
            # Check if we need to re-query (stale or missing)
            current_value = planning_state.get_state_value(key)
            needs_query = (
                planning_state.is_state_stale() or
                current_value is None or
                (key == "has_time_selection" and current_value is None)
            )
            
            if needs_query:
                try:
                    logger.debug(f"Re-querying critical state: {query_tool}")
                    result = self.tool_registry.execute_by_name(query_tool, {})
                    if result.get("success"):
                        value = result.get("value")
                        planning_state.discovered_state[key] = value
                        updated = True
                        logger.debug(f"Updated critical state: {key} = {value}")
                    else:
                        logger.warning(f"Failed to re-query {query_tool}: {result.get('error')}")
                except Exception as e:
                    logger.warning(f"Exception re-querying {query_tool}: {e}")
        
        if updated:
            # Update timestamp since we refreshed state
            import time
            planning_state.state_discovery_timestamp = time.time()
            logger.info("Critical state synchronized before execution")

    def _error_response(self, error_message: str) -> Dict[str, Any]:
        """
        Create error response with helpful message.

        Args:
            error_message: Error description

        Returns:
            Error response dictionary
        """
        # Make error messages more user-friendly
        user_friendly_msg = error_message
        if "prerequisite" in error_message.lower():
            user_friendly_msg = f"{error_message}. Please ensure the required selection or state exists before running this operation."
        elif "state discovery" in error_message.lower():
            user_friendly_msg = f"Could not determine project state. {error_message}"
        elif "planning" in error_message.lower():
            user_friendly_msg = f"Could not plan the operation. {error_message}"
        
        logger.error(f"Returning error response: {user_friendly_msg}")
        return {
            "type": "error",
            "content": f"Error: {user_friendly_msg}"
        }

    def process_approval(
        self,
        approval_id: str,
        approved: bool,
        task_plan: List[Dict[str, Any]] = None,
        approval_mode: str = "batch",
        current_step: int = 0,
        batch_mode: bool = False
    ) -> Dict[str, Any]:
        """
        Process approval response (delegates to OrchestratorAgent).

        Args:
            approval_id: Approval ID
            approved: Whether approved
            task_plan: Task plan
            approval_mode: Approval mode
            current_step: Current step
            batch_mode: Batch mode flag

        Returns:
            Response dictionary
        """
        return self.orchestrator_agent.process_approval(
            approval_id,
            approved,
            task_plan,
            approval_mode,
            current_step,
            batch_mode
        )

