#!/usr/bin/env python3
"""
Planning State Management
Tracks the state machine and execution plan for multi-step operations.
"""

from enum import Enum
from typing import Dict, Any, List, Optional, Tuple
import time


class PlanningPhase(Enum):
    """Phases in the planning state machine"""
    INITIAL = "initial"
    STATE_DISCOVERY = "state_discovery"
    PLANNING = "planning"
    PREREQUISITE_RESOLUTION = "prerequisite_resolution"  # Legacy - being replaced
    STATE_PREPARATION = "state_preparation"  # New: State prep loop
    EXECUTION = "execution"
    ERROR = "error"
    COMPLETE = "complete"


class PlanningState:
    """
    Manages state for the planning layer.
    Tracks user request, discovered state, execution plan, and results.
    """

    def __init__(self, user_message: str):
        """
        Initialize planning state.

        Args:
            user_message: Original user request
        """
        self.user_message = user_message
        self.discovered_state: Dict[str, Any] = {}
        self.execution_plan: List[Dict[str, Any]] = []
        self.prerequisites_resolved: bool = False
        self.execution_results: List[Dict[str, Any]] = []
        self.current_phase: PlanningPhase = PlanningPhase.INITIAL
        self.error_message: Optional[str] = None
        
        # State synchronization tracking
        self.state_discovery_timestamp: Optional[float] = None
        self.state_staleness_threshold: float = 5.0  # seconds - state considered stale after 5s

    def transition_to(self, phase: PlanningPhase) -> bool:
        """
        Transition to a new phase with validation.

        Args:
            phase: Target phase

        Returns:
            True if transition is valid, False otherwise
        """
        # Define valid transitions
        valid_transitions = {
            PlanningPhase.INITIAL: [PlanningPhase.STATE_DISCOVERY, PlanningPhase.ERROR],
            PlanningPhase.STATE_DISCOVERY: [PlanningPhase.PLANNING, PlanningPhase.ERROR],
            PlanningPhase.PLANNING: [
                PlanningPhase.STATE_DISCOVERY,  # Loop back if more state needed
                PlanningPhase.PREREQUISITE_RESOLUTION,  # Legacy path
                PlanningPhase.STATE_PREPARATION,  # New path
                PlanningPhase.ERROR
            ],
            PlanningPhase.PREREQUISITE_RESOLUTION: [
                PlanningPhase.EXECUTION,
                PlanningPhase.ERROR
            ],
            PlanningPhase.STATE_PREPARATION: [
                PlanningPhase.EXECUTION,
                PlanningPhase.ERROR
            ],
            PlanningPhase.EXECUTION: [PlanningPhase.COMPLETE, PlanningPhase.ERROR],
            PlanningPhase.ERROR: [PlanningPhase.INITIAL],  # Can restart from error
            PlanningPhase.COMPLETE: []  # Terminal state
        }

        if phase in valid_transitions.get(self.current_phase, []):
            self.current_phase = phase
            return True
        else:
            return False

    def set_state_snapshot(self, state: Dict[str, Any]):
        """
        Set the discovered state snapshot.

        Args:
            state: State dictionary with query results
        """
        self.discovered_state = state.copy()
        self.state_discovery_timestamp = time.time()

    def get_state_value(self, key: str, default: Any = None) -> Any:
        """
        Get a value from the discovered state.

        Args:
            key: State key
            default: Default value if key not found

        Returns:
            State value or default
        """
        return self.discovered_state.get(key, default)

    def set_execution_plan(self, plan: List[Dict[str, Any]]):
        """
        Set the execution plan.

        Args:
            plan: List of tool calls with 'tool_name' and 'arguments'
        """
        self.execution_plan = plan.copy()

    def add_execution_result(self, result: Dict[str, Any]):
        """
        Add an execution result.

        Args:
            result: Result dictionary with 'tool_name' and 'result'
        """
        self.execution_results.append(result)

    def mark_prerequisites_resolved(self):
        """Mark that prerequisites have been resolved."""
        self.prerequisites_resolved = True

    def set_error(self, error_message: str):
        """
        Set error state.

        Args:
            error_message: Error description
        """
        self.error_message = error_message
        self.current_phase = PlanningPhase.ERROR

    def is_ready_for_execution(self) -> bool:
        """
        Check if state is ready for execution.

        Returns:
            True if ready, False otherwise
        """
        return (
            self.current_phase == PlanningPhase.PREREQUISITE_RESOLUTION and
            self.prerequisites_resolved and
            len(self.execution_plan) > 0
        )

    def validate(self) -> Tuple[bool, Optional[str]]:
        """
        Validate current state.

        Returns:
            Tuple of (is_valid, error_message)
        """
        if self.current_phase == PlanningPhase.ERROR:
            if not self.error_message:
                return False, "Error state but no error message"
            return True, None

        if self.current_phase == PlanningPhase.EXECUTION:
            if not self.execution_plan:
                return False, "Execution phase but no execution plan"
            return True, None

        if self.current_phase == PlanningPhase.PREREQUISITE_RESOLUTION:
            if not self.execution_plan:
                return False, "Prerequisite resolution but no execution plan"
            return True, None

        if self.current_phase == PlanningPhase.PLANNING:
            # Planning phase is valid even without plan (planning in progress)
            return True, None

        if self.current_phase == PlanningPhase.STATE_DISCOVERY:
            # State discovery is valid even without state (discovery in progress)
            return True, None

        return True, None

    def is_state_stale(self) -> bool:
        """
        Check if discovered state is stale (too old).

        Returns:
            True if state is stale, False otherwise
        """
        if self.state_discovery_timestamp is None:
            return True  # No state discovered yet
        
        age = time.time() - self.state_discovery_timestamp
        return age > self.state_staleness_threshold
    
    def get_critical_state_keys(self) -> List[str]:
        """
        Get list of critical state keys that should be re-queried before execution.
        These are state values that might change and affect execution.

        Returns:
            List of critical state key names
        """
        critical_keys = []
        
        # Check if execution plan uses any state-dependent operations
        for tool_call in self.execution_plan:
            tool_name = tool_call.get("tool_name", "")
            
            # Tools that depend on selection state
            if tool_name in {
                "trim_to_selection", "cut", "copy", "delete_selection",
                "silence_selection", "apply_fade_in", "apply_fade_out",
                "apply_reverse", "apply_invert", "apply_noise_reduction",
                "apply_normalize", "apply_amplify", "apply_normalize_loudness",
                "apply_compressor", "apply_limiter", "apply_truncate_silence"
            }:
                critical_keys.extend(["has_time_selection", "selection_start_time", "selection_end_time"])
            
            # Tools that depend on cursor position
            if tool_name in {"paste", "split"}:
                critical_keys.append("cursor_position")
            
            # Tools that depend on track selection
            if tool_name in {"delete_track", "duplicate_track"}:
                critical_keys.append("selected_tracks")
            
            # Tools that depend on clip selection
            if tool_name in {"join", "duplicate_clip"}:
                critical_keys.append("selected_clips")
        
        # Remove duplicates while preserving order
        seen = set()
        unique_keys = []
        for key in critical_keys:
            if key not in seen:
                seen.add(key)
                unique_keys.append(key)
        
        return unique_keys

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert state to dictionary for serialization.

        Returns:
            State as dictionary
        """
        return {
            "user_message": self.user_message,
            "discovered_state": self.discovered_state,
            "execution_plan": self.execution_plan,
            "prerequisites_resolved": self.prerequisites_resolved,
            "execution_results": self.execution_results,
            "current_phase": self.current_phase.value,
            "error_message": self.error_message,
            "state_discovery_timestamp": self.state_discovery_timestamp
        }

