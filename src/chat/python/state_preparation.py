#!/usr/bin/env python3
"""
State Preparation Orchestrator

Implements the iterative state preparation loop:
1. Discover current state
2. Analyze gaps for target tool
3. Infer missing values
4. Execute state-setting tools
5. Verify state changes
6. Repeat until ready or max iterations

Only when all prerequisites are satisfied does execution proceed.
"""

import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from state_contracts import get_contract, StateKey, get_state_setting_tool
from state_gap_analyzer import StateGapAnalyzer, GapAnalysisResult
from value_inference import ValueInferenceEngine, InferenceResult

logger = logging.getLogger(__name__)


@dataclass
class PreparationStep:
    """A single state preparation step."""
    tool_name: str
    arguments: Dict[str, Any]
    purpose: str  # Human-readable description


@dataclass
class PreparationResult:
    """Result of state preparation."""
    ready_to_execute: bool
    preparation_steps: List[PreparationStep]  # Tools to run before operation
    operation_tool: str
    operation_arguments: Dict[str, Any]
    error: Optional[str]
    needs_clarification: bool
    clarification_message: Optional[str]


class StatePreparationOrchestrator:
    """
    Orchestrates the state preparation loop.
    """

    MAX_ITERATIONS = 5  # Prevent infinite loops

    def __init__(self, tool_registry=None):
        """
        Args:
            tool_registry: ToolRegistry instance for executing state queries (optional)
        """
        self.tool_registry = tool_registry
        self.gap_analyzer = StateGapAnalyzer()
        self.value_inference = ValueInferenceEngine()

    def prepare(
        self,
        tool_name: str,
        tool_arguments: Dict[str, Any],
        user_message: str,
        initial_state: Dict[str, Any]
    ) -> PreparationResult:
        """
        Prepare state for tool execution.

        Args:
            tool_name: Target operation tool
            tool_arguments: Arguments provided by LLM
            user_message: Original user request
            initial_state: Initial state snapshot

        Returns:
            PreparationResult with preparation steps or error
        """
        current_state = initial_state.copy()
        preparation_steps = []
        iteration = 0
        tool_args = tool_arguments.copy()

        while iteration < self.MAX_ITERATIONS:
            iteration += 1
            logger.info(f"State preparation iteration {iteration} for {tool_name}")

            # Step 1: Analyze gaps
            gap_result = self.gap_analyzer.analyze(
                tool_name,
                tool_args,
                current_state
            )

            logger.debug(f"Gap analysis: can_execute={gap_result.can_execute}, "
                        f"gaps={len(gap_result.gaps)}, "
                        f"missing_params={gap_result.missing_parameters}")

            # Step 2: Check if ready
            if gap_result.can_execute and not gap_result.missing_parameters:
                logger.info(f"State preparation complete after {iteration} iteration(s)")
                return PreparationResult(
                    ready_to_execute=True,
                    preparation_steps=preparation_steps,
                    operation_tool=tool_name,
                    operation_arguments=tool_args,
                    error=None,
                    needs_clarification=False,
                    clarification_message=None
                )

            # Step 3: Infer missing values
            inference_result = self.value_inference.infer_values(
                gaps=gap_result.gaps,
                missing_parameters=gap_result.missing_parameters,
                user_message=user_message,
                current_state=current_state,
                tool_name=tool_name
            )

            # Step 4: Check if we need user clarification
            if inference_result.needs_user_clarification:
                return PreparationResult(
                    ready_to_execute=False,
                    preparation_steps=preparation_steps,
                    operation_tool=tool_name,
                    operation_arguments=tool_args,
                    error=None,
                    needs_clarification=True,
                    clarification_message=inference_result.clarification_message
                )

            # Step 5: Update tool arguments with inferred parameter values
            params_updated = False
            for param in gap_result.missing_parameters:
                if param in inference_result.inferred_values:
                    tool_args[param] = inference_result.inferred_values[param].value
                    params_updated = True

            # Step 6: Generate state-setting steps
            new_steps = self._generate_preparation_steps(
                gap_result,
                inference_result,
                tool_args
            )

            # Step 7: Add steps and update simulated state
            for step in new_steps:
                preparation_steps.append(step)
                self._simulate_state_change(step, current_state, inference_result)

            # If we made progress (added steps or updated params), continue loop
            if not new_steps and not params_updated:
                # No progress made but still can't execute
                logger.error(f"Cannot prepare state for {tool_name}: no steps available")
                return PreparationResult(
                    ready_to_execute=False,
                    preparation_steps=preparation_steps,
                    operation_tool=tool_name,
                    operation_arguments=tool_args,
                    error=f"Cannot determine how to prepare state for {tool_name}",
                    needs_clarification=False,
                    clarification_message=None
                )

        # Max iterations reached
        logger.error(f"State preparation exceeded {self.MAX_ITERATIONS} iterations")
        return PreparationResult(
            ready_to_execute=False,
            preparation_steps=preparation_steps,
            operation_tool=tool_name,
            operation_arguments=tool_args,
            error=f"State preparation exceeded maximum iterations ({self.MAX_ITERATIONS})",
            needs_clarification=False,
            clarification_message=None
        )

    def _generate_preparation_steps(
        self,
        gap_result: GapAnalysisResult,
        inference_result: InferenceResult,
        tool_arguments: Dict[str, Any]
    ) -> List[PreparationStep]:
        """Generate state-setting tool calls to fill gaps."""
        steps = []

        # Group related gaps (e.g., start_time + end_time → single set_time_selection)
        needs_time_selection = False
        start_time = None
        end_time = None
        needs_track_selection = False
        needs_seek = False
        seek_time = None

        for gap in gap_result.gaps:
            if not gap.needs_value:
                continue

            inferred = inference_result.inferred_values.get(gap.state_key.value)

            if gap.state_key in (StateKey.HAS_TIME_SELECTION,
                                  StateKey.SELECTION_START_TIME,
                                  StateKey.SELECTION_END_TIME):
                needs_time_selection = True
                if gap.state_key == StateKey.SELECTION_START_TIME and inferred:
                    start_time = inferred.value
                elif gap.state_key == StateKey.SELECTION_END_TIME and inferred:
                    end_time = inferred.value
                # Also check inference result directly for all related keys
                if "selection_start_time" in inference_result.inferred_values:
                    start_time = inference_result.inferred_values["selection_start_time"].value
                if "selection_end_time" in inference_result.inferred_values:
                    end_time = inference_result.inferred_values["selection_end_time"].value

            elif gap.state_key == StateKey.SELECTED_TRACKS:
                needs_track_selection = True

            elif gap.state_key == StateKey.CURSOR_POSITION:
                needs_seek = True
                if inferred:
                    seek_time = inferred.value

        # Generate consolidated steps
        if needs_time_selection and start_time is not None and end_time is not None:
            steps.append(PreparationStep(
                tool_name="set_time_selection",
                arguments={"start_time": start_time, "end_time": end_time},
                purpose=f"Set selection from {start_time}s to {end_time}s"
            ))

        if needs_track_selection:
            steps.append(PreparationStep(
                tool_name="select_all_tracks",
                arguments={},
                purpose="Select all tracks"
            ))

        if needs_seek and seek_time is not None:
            steps.append(PreparationStep(
                tool_name="seek",
                arguments={"time": seek_time},
                purpose=f"Move cursor to {seek_time}s"
            ))

        return steps

    def _simulate_state_change(
        self,
        step: PreparationStep,
        state: Dict[str, Any],
        inference_result: InferenceResult
    ):
        """
        Simulate state change after a preparation step.
        This optimistically updates state for the next iteration.
        """
        if step.tool_name == "set_time_selection":
            state["has_time_selection"] = True
            state["selection_start_time"] = step.arguments.get("start_time")
            state["selection_end_time"] = step.arguments.get("end_time")

        elif step.tool_name == "select_all_tracks":
            # Mark as having track selection
            state["selected_tracks"] = state.get("track_list", ["*"])

        elif step.tool_name == "select_all":
            state["has_time_selection"] = True
            state["selected_tracks"] = state.get("track_list", ["*"])

        elif step.tool_name == "seek":
            state["cursor_position"] = step.arguments.get("time")

        elif step.tool_name == "clear_selection":
            state["has_time_selection"] = False
            state["selected_tracks"] = []
            state["selected_clips"] = []

    def prepare_multiple_tools(
        self,
        tool_calls: List[Dict[str, Any]],
        user_message: str,
        initial_state: Dict[str, Any]
    ) -> List[PreparationResult]:
        """
        Prepare state for multiple tools in sequence.

        Args:
            tool_calls: List of tool calls with 'tool_name' and 'arguments'
            user_message: Original user request
            initial_state: Initial state snapshot

        Returns:
            List of preparation results for each tool
        """
        results = []
        current_state = initial_state.copy()

        for tool_call in tool_calls:
            tool_name = tool_call.get("tool_name", "")
            tool_args = tool_call.get("arguments", {})

            result = self.prepare(
                tool_name=tool_name,
                tool_arguments=tool_args,
                user_message=user_message,
                initial_state=current_state
            )
            results.append(result)

            if not result.ready_to_execute:
                # Stop on first error or clarification needed
                break

            # Simulate state changes from preparation steps
            for step in result.preparation_steps:
                self._simulate_state_change(step, current_state, InferenceResult({}, [], False, None))

            # Simulate state changes from the operation tool itself
            self.gap_analyzer._simulate_state_change(
                result.operation_tool,
                result.operation_arguments,
                current_state
            )

        return results


def prepare_tool_execution(
    tool_name: str,
    tool_arguments: Dict[str, Any],
    user_message: str,
    current_state: Dict[str, Any],
    tool_registry=None
) -> PreparationResult:
    """
    Convenience function for state preparation.

    Args:
        tool_name: Target operation tool
        tool_arguments: Arguments provided by LLM
        user_message: Original user request
        current_state: Current state snapshot
        tool_registry: Optional tool registry for state queries

    Returns:
        PreparationResult with preparation steps or error
    """
    orchestrator = StatePreparationOrchestrator(tool_registry)
    return orchestrator.prepare(
        tool_name=tool_name,
        tool_arguments=tool_arguments,
        user_message=user_message,
        initial_state=current_state
    )
