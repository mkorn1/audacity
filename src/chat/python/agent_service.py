#!/usr/bin/env python3
"""
Audacity AI Chat Service
Main entry point for Python-based AI agents
"""

import json
import sys
import os
from typing import Dict, Any, Optional

# Import agents and tools
from tools import ToolExecutor, ToolRegistry
from orchestrator import OrchestratorAgent
from planning_orchestrator import PlanningOrchestrator


class AgentService:
    """Main service that coordinates AI agents"""

    def __init__(self):
        # Initialize tool executor (no stdin - we'll start the reader separately)
        self.tool_executor = ToolExecutor(stdout=sys.stdout)
        self.tools = ToolRegistry(self.tool_executor)

        # Initialize base orchestrator (uses OpenAI function calling)
        self.base_orchestrator = OrchestratorAgent(tools=self.tools)
        
        # Initialize planning orchestrator (wraps base orchestrator)
        self.orchestrator = PlanningOrchestrator(
            tool_registry=self.tools,
            orchestrator_agent=self.base_orchestrator
        )

        # Store pending approvals with their task plans and metadata
        self._pending_approvals = {}  # approval_id -> {task_plan, approval_mode, current_step}

    def start(self):
        """Start the background reader thread"""
        self.tool_executor.start_reader(stdin=sys.stdin)

    def stop(self):
        """Stop the background reader thread"""
        self.tool_executor.stop_reader()
    
    def process_request(self, message: str) -> Dict[str, Any]:
        """
        Process a user message and return response
        
        Args:
            message: User's message/request
            
        Returns:
            Dict with 'message', 'approval_request', or 'error'
        """
        # Delegate to orchestrator
        response = self.orchestrator.process_request(message)
        
        # If approval requested, store the task plan and metadata
        if response.get("type") == "approval_request":
            approval_id = response.get("approval_id")
            task_plan = response.get("task_plan")
            approval_mode = response.get("approval_mode", "batch")
            current_step = response.get("current_step", 0)
            if approval_id and task_plan:
                self._pending_approvals[approval_id] = {
                    "task_plan": task_plan,
                    "approval_mode": approval_mode,
                    "current_step": current_step
                }
        
        return response
    
    def process_approval(self, approval_id: str, approved: bool, batch_mode: bool = False) -> Dict[str, Any]:
        """
        Process approval response
        
        Args:
            approval_id: ID of the approval request
            approved: Whether user approved
            
        Returns:
            Dict with result
        """
        # Get stored approval data
        approval_data = self._pending_approvals.get(approval_id)
        if not approval_data:
            # Try to find by base approval ID (for step-by-step)
            base_id = approval_id.rsplit("_step_", 1)[0]
            approval_data = self._pending_approvals.get(base_id)
            if approval_data:
                # Update current step from approval_id
                if "_step_" in approval_id:
                    step_num = int(approval_id.split("_step_")[-1])
                    approval_data["current_step"] = step_num
        
        if not approval_data:
            return {
                "type": "error",
                "content": f"Approval ID not found: {approval_id}"
            }
        
        task_plan = approval_data.get("task_plan")
        approval_mode = approval_data.get("approval_mode", "batch")
        current_step = approval_data.get("current_step", 0)
        
        # Check if this is a batch approval request (from UI)
        # We'll detect this by checking if approval_mode is "step_by_step" but user wants batch
        # For now, we'll pass a batch_mode flag - this would come from the C++ side
        # For simplicity, if it's step_by_step with multiple steps, allow batch conversion
        
        # Delegate to orchestrator
        result = self.orchestrator.process_approval(
            approval_id, 
            approved, 
            task_plan,
            approval_mode,
            current_step,
            batch_mode=batch_mode
        )
        
        # If result is another approval request, store it
        if result.get("type") == "approval_request":
            new_approval_id = result.get("approval_id")
            if new_approval_id:
                self._pending_approvals[new_approval_id] = {
                    "task_plan": result.get("task_plan"),
                    "approval_mode": result.get("approval_mode", "batch"),
                    "current_step": result.get("current_step", 0)
                }
        elif not approved or approval_mode == "batch":
            # Remove from pending if batch mode or rejected
            self._pending_approvals.pop(approval_id, None)
            base_id = approval_id.rsplit("_step_", 1)[0]
            self._pending_approvals.pop(base_id, None)
        
        return result

def main():
    """Main entry point - communicates via stdin/stdout with C++"""
    service = AgentService()

    # Start the background reader thread
    service.start()

    # Process messages from the queue (populated by reader thread)
    # The reader thread handles tool_result messages directly
    while True:
        try:
            # Block waiting for next message from queue
            request = service.tool_executor.message_queue.get()

            request_type = request.get("type")

            if request_type == "message":
                response = service.process_request(request.get("message", ""))
                # Write response to stdout (JSON)
                print(json.dumps(response))
                sys.stdout.flush()
            elif request_type == "approval":
                response = service.process_approval(
                    request.get("approval_id", ""),
                    request.get("approved", False),
                    request.get("batch_mode", False)
                )
                # Write response to stdout (JSON)
                print(json.dumps(response))
                sys.stdout.flush()
            elif request_type == "shutdown":
                # Clean shutdown request
                service.stop()
                break
            else:
                response = {"type": "error", "content": f"Unknown request type: {request_type}"}
                print(json.dumps(response))
                sys.stdout.flush()

        except Exception as e:
            error_response = {
                "type": "error",
                "content": f"Error: {str(e)}"
            }
            print(json.dumps(error_response))
            sys.stdout.flush()

if __name__ == "__main__":
    main()

