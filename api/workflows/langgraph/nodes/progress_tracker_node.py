"""
Real-time Progress Tracker Node for LangGraph Workflow
Calculates exact progress percentages and yields immediate updates
"""
import asyncio
import time
from typing import Dict, Any, List, Optional
from langchain_core.runnables import RunnableConfig

from .base import BaseWorkflowNode
from ..state.state import RAGState
from utils.logging import get_logger
from utils.language_utils import get_workflow_message

logger = get_logger(__name__)


class ProgressTrackerNode(BaseWorkflowNode):
    """
    Dedicated node for real-time progress tracking and yielding
    Calculates exact progress percentages based on task states
    """
    
    def __init__(self):
        super().__init__(node_name="progress_tracker")
        self._start_time = None
        
    async def execute(self, state: RAGState, config: RunnableConfig) -> Dict[str, Any]:
        """
        Process progress updates and yield immediately with exact percentages
        """
        try:
            self._start_time = time.time()
            
            # Get current execution context
            execution_plan = state.get("execution_plan", {})
            formatted_tasks = state.get("formatted_tasks", [])
            current_step = state.get("current_step", "unknown")
            detected_language = state.get("detected_language", "english")
            task_status_update = state.get("task_status_update")
            
            # Calculate exact progress percentage
            progress_percentage = self._calculate_exact_progress(formatted_tasks, current_step)
            
            # Generate progress message
            progress_message = self._generate_progress_message(
                formatted_tasks, current_step, detected_language, task_status_update
            )
            
            # Determine next action based on task completion
            next_action = self._determine_next_action(formatted_tasks, current_step)
            
            # Create real-time update payload
            update_payload = {
                "processing_status": self._determine_processing_status(formatted_tasks, current_step),
                "progress_percentage": progress_percentage,
                "progress_message": progress_message,
                "current_step": current_step,
                "total_steps": len(formatted_tasks),
                "formatted_tasks": formatted_tasks,
                "execution_plan": execution_plan,
                "task_status_update": task_status_update,
                "should_yield": True, 
                "timestamp": time.time(),
                "node_execution_time": time.time() - self._start_time if self._start_time else 0
            }
            
            logger.info(f"PROGRESS_TRACKER: {progress_percentage:.1f}% - {progress_message} - Next: {next_action}")
            
            return {
                "next_action": next_action,
                **update_payload
            }
            
        except Exception as e:
            logger.error(f"Progress tracker node failed: {e}")
            return {
                "processing_status": "error",
                "progress_percentage": 0,
                "progress_message": f"Progress tracking error: {str(e)}",
                "should_yield": True,
                "error_message": str(e),
                "next_action": "error"
            }
    
    def _calculate_exact_progress(self, formatted_tasks: List[Dict[str, Any]], current_step: str) -> float:
        """
        Calculate exact progress percentage based on task states
        """
        if not formatted_tasks:
            return 0.0
            
        total_tasks = len(formatted_tasks)
        
        completed_tasks = 0
        in_progress_tasks = 0
        failed_tasks = 0
        pending_tasks = 0
        
        for task in formatted_tasks:
            status = task.get("status", "pending")
            if status == "completed":
                completed_tasks += 1
            elif status in ["in_progress", "retrying"]:
                in_progress_tasks += 1
            elif status == "failed":
                failed_tasks += 1
            else:
                pending_tasks += 1
        
        
        total_progress = (completed_tasks * 100) + (in_progress_tasks * 50)
        max_possible_progress = total_tasks * 100
        
        if max_possible_progress == 0:
            return 0.0
            
        exact_percentage = (total_progress / max_possible_progress) * 100
        
        # Ensure reasonable bounds
        exact_percentage = max(0.0, min(100.0, exact_percentage))
        
        logger.debug(f"Progress calculation: {completed_tasks}C + {in_progress_tasks}IP + {failed_tasks}F + {pending_tasks}P = {exact_percentage:.1f}%")
        
        return exact_percentage
    
    def _determine_next_action(self, formatted_tasks: List[Dict[str, Any]], current_step: str) -> str:
        """
        Determine the next workflow action based on task completion status
        """
        if not formatted_tasks:
            return "final_response"
            
        all_completed = all(task.get("status") == "completed" for task in formatted_tasks)
        if all_completed:
            return "final_response"
            
        any_active = any(task.get("status") in ["pending", "in_progress", "retrying"] for task in formatted_tasks)
        if any_active:
            return "continue_execution"
            
        any_completed = any(task.get("status") == "completed" for task in formatted_tasks)
        any_failed = any(task.get("status") == "failed" for task in formatted_tasks)
        
        if any_completed:
            return "final_response"
        elif any_failed:
            return "final_response"
            
        return "continue_execution"
        
    def _determine_processing_status(self, formatted_tasks: List[Dict[str, Any]], current_step: str) -> str:
        """
        Determine overall processing status based on task states
        """
        if not formatted_tasks:
            return "pending"
            
        # Check if all tasks are completed
        all_completed = all(task.get("status") == "completed" for task in formatted_tasks)
        if all_completed:
            return "completed"
            
        # Check if any tasks are in progress
        any_in_progress = any(task.get("status") in ["in_progress", "retrying"] for task in formatted_tasks)
        if any_in_progress:
            return "running"
            
        # Check if any tasks failed
        any_failed = any(task.get("status") == "failed" for task in formatted_tasks)
        if any_failed:
            # If some completed and some failed, still running
            any_completed = any(task.get("status") == "completed" for task in formatted_tasks)
            if any_completed:
                return "running"
            return "failed"
            
        # Default to pending if all tasks are pending
        return "pending"
    
    def _generate_progress_message(
        self, 
        formatted_tasks: List[Dict[str, Any]], 
        current_step: str, 
        detected_language: str,
        task_status_update: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Generate human-readable progress message
        """
        if not formatted_tasks:
            return get_workflow_message("initializing", detected_language)
            
        total_tasks = len(formatted_tasks)
        completed_count = sum(1 for task in formatted_tasks if task.get("status") == "completed")
        in_progress_count = sum(1 for task in formatted_tasks if task.get("status") in ["in_progress", "retrying"])
        failed_count = sum(1 for task in formatted_tasks if task.get("status") == "failed")
        
        # Handle specific task status updates
        if task_status_update:
            task_type = task_status_update.get("type", "")
            task_index = task_status_update.get("task_index", 0)
            
            if task_type == "task_started" and task_index < len(formatted_tasks):
                agent_name = formatted_tasks[task_index].get("agent", "Agent")
                return get_workflow_message(
                    "task_started",
                    detected_language,
                    current=task_index + 1,
                    total=total_tasks,
                    agent=agent_name
                )
            elif task_type == "task_completed" and task_index < len(formatted_tasks):
                agent_name = formatted_tasks[task_index].get("agent", "Agent")
                return get_workflow_message(
                    "task_completed",
                    detected_language,
                    current=completed_count,
                    total=total_tasks,
                    agent=agent_name
                )
            elif task_type == "task_retry" and task_index < len(formatted_tasks):
                agent_name = formatted_tasks[task_index].get("agent", "Agent")
                attempt = task_status_update.get("attempt", 1)
                return get_workflow_message(
                    "task_retrying",
                    detected_language,
                    agent=agent_name,
                    attempt=attempt
                )
        
        # Generate general progress message
        if completed_count == total_tasks:
            return get_workflow_message("all_tasks_completed", detected_language, total=total_tasks)
        elif in_progress_count > 0:
            return get_workflow_message(
                "tasks_in_progress", 
                detected_language, 
                completed=completed_count, 
                total=total_tasks,
                in_progress=in_progress_count
            )
        elif failed_count > 0 and completed_count > 0:
            return get_workflow_message(
                "tasks_partial_completion",
                detected_language,
                completed=completed_count,
                failed=failed_count,
                total=total_tasks
            )
        elif failed_count > 0:
            return get_workflow_message("tasks_failed", detected_language, failed=failed_count, total=total_tasks)
        else:
            return get_workflow_message("tasks_pending", detected_language, total=total_tasks)


# Export the node
progress_tracker_node = ProgressTrackerNode()