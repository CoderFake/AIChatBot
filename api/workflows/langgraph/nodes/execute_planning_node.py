import asyncio
import time
import asyncio
from asyncio import Queue
from typing import Dict, Any, List, Optional
from langchain_core.runnables import RunnableConfig
from .base import ExecutionNode
from workflows.langgraph.state.state import RAGState, AgentResponse
from services.agents.agent_service import AgentService
from utils.logging import get_logger
from utils.language_utils import get_workflow_message
from utils.datetime_utils import DateTimeManager
from config.settings import get_settings

# Import progress tracker utility
try:
    from .progress_tracker_node import ProgressTrackerNode
    progress_tracker_utility = ProgressTrackerNode()
except ImportError:
    progress_tracker_utility = None
    
logger = get_logger(__name__)
settings = get_settings()


class ExecutePlanningNode(ExecutionNode):
    """
    Execute the structured planning created by semantic reflection
    Steps (step_1, step_2...) run in PARALLEL
    Tools within each task run SEQUENTIALLY (tool1 -> tool2 -> tool3)
    """

    MAX_RETRY_ATTEMPTS = 3

    def __init__(self):
        super().__init__("execute_planning")

    def _calculate_progress_percentage(self, step: str, current_step: int = 0, total_steps: int = 0) -> int:
        """Calculate real progress percentage based on workflow step and completion"""
        base_progress = {
            "plan_ready": 50,  # Immediately show 50% when plan is ready
            "executing_agents": 75,
            "executing_task": 75,
            "task_completed": 75,
            "completed": 100,  # Show 100% only when truly completed
            "conflict_resolution_needed": 85,
            "failed": 0  # Show 0% for failed state
        }

        progress = base_progress.get(step, 75)

        if total_steps > 0 and current_step > 0:
            task_progress = int((current_step / total_steps) * 10)
            progress = min(85, progress + task_progress)

        return progress
        
    def _calculate_exact_progress_percentage(self, formatted_tasks: List[Dict[str, Any]], step: str = None) -> float:
        """Calculate exact progress percentage using progress tracker utility"""
        if progress_tracker_utility:
            try:
                return progress_tracker_utility._calculate_exact_progress(formatted_tasks, step or "executing")
            except Exception as e:
                logger.warning(f"Progress tracker utility failed: {e}")
                
        # Fallback to basic calculation
        if not formatted_tasks:
            return 0.0
            
        total_tasks = len(formatted_tasks)
        completed_tasks = sum(1 for task in formatted_tasks if task.get("status") == "completed")
        in_progress_tasks = sum(1 for task in formatted_tasks if task.get("status") in ["in_progress", "retrying"])
        
        # Simple calculation: completed=100%, in_progress=50%, others=0%
        total_progress = (completed_tasks * 100) + (in_progress_tasks * 50)
        max_possible = total_tasks * 100
        
        return (total_progress / max_possible * 100) if max_possible > 0 else 0.0

    async def execute(self, state: RAGState, config: RunnableConfig) -> Dict[str, Any]:
        """Execute the structured planning with agent coordination"""
        results = []
        async for result in self.execute_with_progress(state, config):
            results.append(result)
        return results[-1] if results else {}

    async def execute_with_progress(self, state: RAGState, config: RunnableConfig):
        """Execute with step-by-step progress yielding"""
        try:
            semantic_routing = state.get("semantic_routing", {})
            execution_plan = state.get("execution_plan", {})
            original_query = state.get("query", "")
            user_context = state.get("user_context", {})

            if not execution_plan:
                logger.warning("No execution plan found, skipping to final response")
                yield {
                    "next_action": "final_response",
                    "processing_status": "completed",
                    "progress_percentage": self._calculate_progress_percentage("completed"),
                    "progress_message": "No execution plan found",
                    "should_yield": True
                }
                return

            logger.info("Starting execution of structured planning")
            detected_language = state.get("detected_language", "english")

            formatted_tasks = self._format_tasks_for_display(execution_plan)

            yield {
                "processing_status": "plan_ready",
                "progress_percentage": self._calculate_progress_percentage("plan_ready"),
                "progress_message": get_workflow_message("execution_plan_ready", detected_language),
                "execution_plan": execution_plan,
                "formatted_tasks": formatted_tasks,
                "task_status_update": {
                    "type": "plan_ready",
                    "all_tasks_status": "pending",
                    "color": "primary"
                },
                "should_yield": True
            }

            execution_results = []
            try:
                async for progress_update in self._execute_parallel_steps(
                    state,
                    execution_plan,
                    original_query,
                    user_context,
                    detected_language,
                    formatted_tasks,
                    semantic_routing
                ):
                    if progress_update.get("type") == "progress":
                        if progress_update.get("formatted_tasks") is not None:
                            formatted_tasks = progress_update["formatted_tasks"]
                        yield progress_update
                    elif progress_update.get("type") == "result":
                        execution_results = progress_update.get("results", [])
                        if progress_update.get("formatted_tasks") is not None:
                            formatted_tasks = progress_update["formatted_tasks"]
            except Exception as e:
                logger.error(f"Parallel execution failed in execute method: {e}")
                execution_results = [{
                    "agent_name": "System",
                    "content": f"Parallel execution failed: {str(e)}",
                    "status": "failed",
                    "confidence": 0.0,
                    "sources": [],
                    "execution_time": 0.0,
                    "error": str(e),
                    "task_index": 0
                }]

            successful_responses = [r for r in execution_results if r.get("status") == "completed"]
            failed_responses = [r for r in execution_results if r.get("status") == "failed"]

            logger.info(f"Execution completed: {len(successful_responses)} successful, {len(failed_responses)} failed")

            progress_msg = get_workflow_message("execution_completed", detected_language, success=len(successful_responses), total=len(execution_results))

            if len(successful_responses) == 0:
                yield {
                    "agent_responses": execution_results,
                    "error_message": "All agents failed to execute",
                    "next_action": "error",
                    "processing_status": "failed",
                    "progress_percentage": self._calculate_progress_percentage("failed"),
                    "progress_message": progress_msg,
                    "formatted_tasks": formatted_tasks,
                    "should_yield": True
                }
                return

            routing_decision = self._analyze_execution_plan_for_routing(
                execution_plan, successful_responses, semantic_routing
            )

            if routing_decision == "single_agent_sequential":
                logger.info("Routing to final_response: Single agent with sequential tools")
                all_completed = all(task.get("status") == "completed" for task in formatted_tasks)
                final_progress = self._calculate_exact_progress_percentage(formatted_tasks, "final_routing")
                yield {
                    "agent_responses": successful_responses,
                    "next_action": "final_response",
                    "routing_decision": routing_decision,
                    "processing_status": "completed",
                    "progress_percentage": final_progress,
                    "progress_message": progress_msg,
                    "formatted_tasks": formatted_tasks,
                    "task_status_update": {
                        "type": "all_completed" if all_completed else "mostly_completed",
                        "all_tasks_status": "completed" if all_completed else "partial",
                        "color": "success" if all_completed else "primary"
                    },
                    "should_yield": True
                }

            elif routing_decision == "multiple_agents":
                logger.info("Routing to conflict_resolution: Multiple agents detected")
                all_completed = all(task.get("status") == "completed" for task in formatted_tasks)
                conflict_progress = self._calculate_exact_progress_percentage(formatted_tasks, "conflict_resolution")
                yield {
                    "agent_responses": successful_responses,
                    "next_action": "conflict_resolution",
                    "routing_decision": routing_decision,
                    "processing_status": "ready_for_resolution",
                    "progress_percentage": conflict_progress,
                    "progress_message": get_workflow_message("conflict_resolution_needed", detected_language),
                    "formatted_tasks": formatted_tasks,
                    "task_status_update": {
                        "type": "conflict_resolution" if not all_completed else "all_completed",
                        "all_tasks_status": "completed" if all_completed else "partial",
                        "color": "success" if all_completed else "primary"
                    },
                    "should_yield": True
                }

            else:
                logger.info("Routing to conflict_resolution: Complex execution plan")
                all_completed = all(task.get("status") == "completed" for task in formatted_tasks)
                complex_progress = self._calculate_exact_progress_percentage(formatted_tasks, "complex_resolution")
                yield {
                    "agent_responses": successful_responses,
                    "next_action": "conflict_resolution",
                    "routing_decision": routing_decision,
                    "processing_status": "ready_for_resolution",
                    "progress_percentage": complex_progress,
                    "progress_message": get_workflow_message("conflict_resolution_needed", detected_language),
                    "formatted_tasks": formatted_tasks,
                    "task_status_update": {
                        "type": "complex_resolution" if not all_completed else "all_completed",
                        "all_tasks_status": "completed" if all_completed else "partial",
                        "color": "success" if all_completed else "primary"
                    },
                    "should_yield": True
                }

        except Exception as e:
            logger.error(f"Execute planning failed: {e}")
            yield {
                "error_message": f"Execute planning failed: {str(e)}",
                "next_action": "error",
                "processing_status": "failed",
                "progress_percentage": self._calculate_progress_percentage("failed"),
                "formatted_tasks": formatted_tasks if 'formatted_tasks' in locals() else None,
                "should_yield": True
            }

    def _format_tasks_for_display(self, execution_plan: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Format tasks from execution plan for user display:
        {
            "task_name": "purpose",
            "messages": {
                "1": "Tool 1 message",
                "2": "Tool 2 message"
            },
            "status": "pending"
        }
        """
        formatted_tasks = []
        
        steps = execution_plan.get("steps", [])
        for step in steps:
            if isinstance(step, dict):
                tasks = step.get("tasks", [])
                for i, task in enumerate(tasks):
                    if isinstance(task, dict):
                        purpose = task.get("purpose", f"Task {i+1}")
                        tools = task.get("tools", [])
                        
                        messages = {}
                        for j, tool in enumerate(tools, 1):
                            if isinstance(tool, dict):
                                tool_message = tool.get("message", "")
                                if tool_message:
                                    messages[str(j)] = tool_message
                            else:
                                messages[str(j)] = f"Execute {tool}"
                    
                        task_name = purpose
                        if "Task: " in purpose:
                            task_name = purpose.split("Task: ")[-1].strip()
                        elif isinstance(purpose, str) and len(purpose.split('\n')) > 1:
                            task_name = purpose.split('\n')[-1].strip()

                        formatted_task = {
                            "task_name": task_name,
                            "purpose": purpose,
                            "messages": messages,
                            "status": task.get("status", "pending"),
                            "agent": task.get("agent", ""),
                            "task_index": len(formatted_tasks),
                            "retry_attempts": 0,
                            "retry_history": [],
                            "max_retries": self.MAX_RETRY_ATTEMPTS,
                            "severity": "pending",
                            "color": "primary"  # Default primary color for pending
                        }
                        formatted_tasks.append(formatted_task)
        
        return formatted_tasks

    def _augment_with_retry_context(self, base_message: str, retry_error: Optional[str], attempt: int) -> str:
        """Append retry error context to the next tool/query execution message."""
        if not retry_error:
            return base_message

        retry_instruction = (
            "\n\nPREVIOUS ATTEMPT ERROR DETAILS:"
            f"\nAttempt {max(attempt - 1, 1)} failed with error: {retry_error}"
            "\nPlease adjust your approach, consider alternative parameters or data sources, and avoid repeating the same error."
        )

        return f"{base_message}{retry_instruction}"

    def _ensure_datetime_context(
        self,
        base_query: str,
        tenant_timezone: Optional[str],
        tenant_current_datetime: Optional[str],
    ) -> str:
        """Append tenant datetime context for the datetime tool when missing."""

        marker = "TENANT DATETIME CONTEXT"
        if base_query and marker in base_query.upper():
            return base_query

        timezone_value = tenant_timezone or getattr(settings, "TIMEZONE", "UTC")
        try:
            timezone_value = timezone_value or getattr(DateTimeManager.system_tz, "key", str(DateTimeManager.system_tz))
        except Exception:
            timezone_value = getattr(settings, "TIMEZONE", "UTC")

        if tenant_current_datetime:
            current_value = tenant_current_datetime
        else:
            try:
                current_value = DateTimeManager.tenant_now(timezone_value).isoformat()
            except Exception:
                current_value = DateTimeManager.system_now().isoformat()

        context_block = (
            f"\n\n{marker}:"
            f"\n- Tenant timezone: {timezone_value}"
            f"\n- Current tenant datetime: {current_value}"
            "\n- Always interpret and report dates/times using this tenant timezone, not UTC."
        )

        if base_query:
            return f"{base_query.rstrip()}{context_block}"
        return context_block.lstrip()

    def _get_tool_display(self, tools_used: List[str], result: Dict[str, Any]) -> str:
        """Build a human-friendly representation of the tools used."""
        if isinstance(tools_used, list) and tools_used:
            return ", ".join(str(tool) for tool in tools_used)

        return str(result.get("tool") or result.get("tool_name") or "tool")

    def _build_retry_progress_message(
        self,
        retry_event: Dict[str, Any],
        detected_language: str
    ) -> str:
        """Create a localized progress message for retry attempts."""
        agent_display = retry_event.get("agent_name") or "Agent"
        tools = retry_event.get("tools") or []
        if isinstance(tools, list):
            tool_names = [t.get("tool", "unknown") if isinstance(t, dict) else str(t) for t in tools]
        else:
            tool_names = [str(tools)]

        tool_display = self._get_tool_display(tool_names, {})
        attempt = retry_event.get("attempt", 0) + 1
        max_attempts = retry_event.get("max_attempts", self.MAX_RETRY_ATTEMPTS)
        error = retry_event.get("error", "")

        try:
            return get_workflow_message(
                "task_retrying",
                detected_language,
                agent=agent_display,
                tool=tool_display,
                attempt=attempt,
                max_attempts=max_attempts,
                error=error
            )
        except Exception:
            return (
                f"Retrying task {agent_display} ({tool_display}) "
                f"attempt {attempt}/{max_attempts} due to error: {error}"
            )

    async def _execute_parallel_steps(
        self,
        state: RAGState,
        execution_plan: Dict[str, Any],
        original_query: str,
        user_context: Dict[str, Any],
        detected_language: str,
        formatted_tasks: List[Dict[str, Any]],
        semantic_routing: Dict[str, Any] = None
    ):
        """
        Execute all steps in PARALLEL (step_1, step_2, step_3... run simultaneously)
        But tools within each task run SEQUENTIALLY (tool1 -> tool2 -> tool3...)
        """
        execution_tasks = []
        progress_queue: Queue = Queue()
        
        try:
            steps = execution_plan.get("steps", [])

            if not steps:
                logger.warning("No planning steps found in execution plan")
                yield {"type": "result", "results": []}
                return

            all_tasks = []
            for step in steps:
                if isinstance(step, dict):
                    tasks = step.get("tasks", [])
                    if isinstance(tasks, list):
                        all_tasks.extend(tasks)

            if not all_tasks:
                logger.warning("No executable tasks found")
                yield {"type": "result", "results": []}
                return

            logger.info(f"Found {len(all_tasks)} tasks to execute in parallel")

            latest_formatted = self._format_tasks_for_display(execution_plan)
            formatted_tasks.clear()
            formatted_tasks.extend(latest_formatted)

            for task_info in formatted_tasks:
                task_info["status"] = "pending"
                task_info["retry_count"] = 0
                task_info["max_retries"] = self.MAX_RETRY_ATTEMPTS
                task_info["retry_attempts"] = 0
                task_info["retry_history"] = []
                task_info["severity"] = "pending"
                task_info.pop("result", None)
                task_info.pop("error", None)
                task_info.pop("last_error", None)

            initial_progress = self._calculate_progress_percentage("executing_agents")
            yield {
                "type": "progress",
                "node": "execute_planning",
                "output": {
                    "processing_status": "executing_agents",
                    "progress_percentage": initial_progress,
                    "progress_message": get_workflow_message(
                        "execution_started",
                        detected_language,
                        total=len(all_tasks)
                    ),
                    "current_step": 0,
                    "total_steps": len(all_tasks),
                    "formatted_tasks": formatted_tasks,
                    "should_yield": True
                }
            }

            processed_results: List[Any] = [None] * len(all_tasks)
            completed_success = 0
            processed_count = 0

            for i, task in enumerate(all_tasks):
                try:
                    if isinstance(task, dict):
                        if i < len(formatted_tasks):
                            # Update to in_progress status immediately
                            formatted_tasks[i]["status"] = "in_progress"
                            formatted_tasks[i]["severity"] = "info"
                            formatted_tasks[i]["color"] = "primary"  # Primary color for in progress
                            formatted_tasks[i]["agent"] = task.get("agent", formatted_tasks[i].get("agent", ""))
                            formatted_tasks[i]["retry_count"] = 0
                            formatted_tasks[i].pop("error", None)
                            formatted_tasks[i].pop("last_error", None)
                            
                            # Pass data with exact progress calculation
                            exact_progress = self._calculate_exact_progress_percentage(formatted_tasks, "task_started")
                            yield {
                                "type": "progress",
                                "node": "execute_planning",
                                "output": {
                                    "processing_status": "task_started",
                                    "progress_percentage": exact_progress,
                                    "progress_message": get_workflow_message(
                                        "task_started",
                                        detected_language,
                                        current=i+1,
                                        total=len(all_tasks),
                                        agent=task.get("agent", "Agent")
                                    ),
                                    "current_step": "task_execution",
                                    "total_steps": len(all_tasks),
                                    "formatted_tasks": formatted_tasks,
                                    "task_status_update": {
                                        "type": "task_started",
                                        "task_index": i,
                                        "status": "in_progress",
                                        "color": "primary"
                                    },
                                    "should_yield": True
                                }
                            }
                            # Force immediate yielding to prevent async buffering
                            await asyncio.sleep(0)
                            
                        logger.info(f"YIELDED_TASK_START: task_index={i}, agent={task.get('agent', 'Agent')}")
                        task_future = asyncio.create_task(
                            self._execute_single_task(
                                state,
                                task,
                                i,
                                progress_queue=progress_queue
                            )
                        )
                        execution_tasks.append((task_future, i))
                    else:
                        logger.warning(f"Task {i} is not a dict, skipping")
                except Exception as e:
                    logger.error(f"Failed to create task {i}: {e}")
                    failed_result = {
                        "agent_name": f"Task_{i}",
                        "content": f"Task creation failed: {str(e)}",
                        "status": "failed",
                        "confidence": 0.0,
                        "sources": [],
                        "execution_time": 0.0,
                        "error": str(e),
                        "task_index": i
                    }
                    processed_results[i] = failed_result
                    processed_count += 1

            if not execution_tasks:
                yield {"type": "result", "results": [], "formatted_tasks": formatted_tasks}
                return

            # Process completed tasks
            pending_tasks = {future for future, idx in execution_tasks}
            queue_listener: Optional[asyncio.Task] = asyncio.create_task(progress_queue.get()) if pending_tasks else None

            while pending_tasks:
                try:
                    wait_items = set(pending_tasks)
                    if queue_listener:
                        wait_items.add(queue_listener)

                    done, _ = await asyncio.wait(wait_items, return_when=asyncio.FIRST_COMPLETED)

                    if queue_listener and queue_listener in done:
                        listener_task = queue_listener
                        try:
                            retry_event = listener_task.result()
                        except asyncio.CancelledError:
                            retry_event = None

                        if retry_event is not None:
                            task_idx = retry_event.get("task_index")
                            if task_idx is not None and 0 <= task_idx < len(formatted_tasks):
                                formatted_tasks[task_idx]["status"] = "retrying"
                                formatted_tasks[task_idx]["severity"] = "danger"
                                formatted_tasks[task_idx]["color"] = "danger"  # Danger color for retry
                                formatted_tasks[task_idx]["retry_count"] = retry_event.get("attempt", 0)
                                formatted_tasks[task_idx]["max_retries"] = retry_event.get("max_attempts", self.MAX_RETRY_ATTEMPTS)
                                formatted_tasks[task_idx]["retry_attempts"] = retry_event.get("attempt", 0)
                                formatted_tasks[task_idx]["error"] = retry_event.get("error")
                                formatted_tasks[task_idx]["last_error"] = retry_event.get("error")

                            progress_message = self._build_retry_progress_message(
                                retry_event,
                                detected_language
                            )

                            exact_progress = self._calculate_exact_progress_percentage(formatted_tasks, "task_retry")
                            progress_message = self._build_retry_progress_message(
                                retry_event,
                                detected_language
                            )
                            
                            yield {
                                "type": "progress",
                                "node": "execute_planning",
                                "output": {
                                    "processing_status": "task_retrying",
                                    "progress_percentage": exact_progress,
                                    "progress_message": progress_message,
                                    "current_step": "task_retry",
                                    "total_steps": len(all_tasks),
                                    "formatted_tasks": formatted_tasks,
                                    "task_status_update": {
                                        "type": "task_retry",
                                        "task_index": task_idx,
                                        "status": "retrying",
                                        "color": "danger",
                                        "attempt": retry_event.get("attempt", 0)
                                    },
                                    "should_yield": True
                                }
                            }
                            # Force immediate yielding for retry events
                            await asyncio.sleep(0)
                            
                        if pending_tasks:
                            queue_listener = asyncio.create_task(progress_queue.get())
                        else:
                            queue_listener = None

                        done.discard(listener_task)

                    completed_futures = [task for task in done if task in pending_tasks]

                    for completed_task in completed_futures:
                        task_idx = None
                        for future, idx in execution_tasks:
                            if future == completed_task:
                                task_idx = idx
                                break
                        
                        if task_idx is None:
                            logger.error("Could not find task index for completed task")
                            continue
                            
                        try:
                            result = await completed_task
                        except Exception as exc:
                            logger.error(f"Task {task_idx} failed with exception: {exc}")
                            result = {
                                "agent_name": f"Task_{task_idx}",
                                "content": f"Task execution failed: {str(exc)}",
                                "status": "failed",
                                "confidence": 0.0,
                                "sources": [],
                                "execution_time": 0.0,
                                "error": str(exc),
                                "task_index": task_idx
                            }

                        processed_results[task_idx] = result
                        processed_count += 1

                        status = result.get("status", "completed")
                        if status == "completed":
                            completed_success += 1

                        if task_idx < len(formatted_tasks):
                            task_status = "completed" if status == "completed" else "failed"
                            formatted_tasks[task_idx]["status"] = task_status
                            
                            if status == "completed":
                                formatted_tasks[task_idx]["severity"] = "success"
                                formatted_tasks[task_idx]["color"] = "success"  
                            else:
                                formatted_tasks[task_idx]["severity"] = "danger"
                                formatted_tasks[task_idx]["color"] = "danger"  
                            
                            formatted_tasks[task_idx]["result"] = result
                            attempts_used = result.get("retry_attempts", result.get("attempts", 0))
                            formatted_tasks[task_idx]["retry_count"] = attempts_used
                            formatted_tasks[task_idx]["retry_attempts"] = attempts_used
                            formatted_tasks[task_idx]["retry_history"] = result.get("retry_history", [])
                            formatted_tasks[task_idx]["max_retries"] = result.get("max_retries", self.MAX_RETRY_ATTEMPTS)
                            
                            if status != "completed":
                                error_message = result.get("error") or result.get("content")
                                formatted_tasks[task_idx]["error"] = error_message
                                formatted_tasks[task_idx]["last_error"] = error_message
                            else:
                                formatted_tasks[task_idx].pop("error", None)
                                formatted_tasks[task_idx].pop("last_error", None)

                        tools_used = result.get("tools_used") or []
                        tool_display = self._get_tool_display(tools_used, result)
                        agent_display = result.get("agent_name") or result.get("agent") or "Agent"

                        attempts_used = result.get("retry_attempts", result.get("attempts", 1)) or 1

                        if status == "completed":
                            if attempts_used > 1:
                                progress_message = get_workflow_message(
                                    "task_recovered",
                                    detected_language,
                                    current=completed_success,
                                    total=len(all_tasks),
                                    agent=agent_display,
                                    tool=tool_display,
                                    attempts=attempts_used
                                )
                            else:
                                progress_message = get_workflow_message(
                                    "task_completed_sequential",
                                    detected_language,
                                    current=completed_success,
                                    total=len(all_tasks),
                                    agent=agent_display,
                                    tool=tool_display
                                )
                        else:
                            error_detail = result.get("error") or result.get("content", "")
                            base_error = error_detail or get_workflow_message("generic_error", detected_language)
                            progress_message = (
                                f"Task {agent_display} failed after {attempts_used} attempts: {base_error}" if base_error else get_workflow_message(
                                    "task_failed",
                                    detected_language,
                                    agent=agent_display,
                                    tool=tool_display,
                                    error=""
                                )
                            )

                        exact_progress = self._calculate_exact_progress_percentage(formatted_tasks, "task_completion")
                        
                        if status == "completed":
                            if attempts_used > 1:
                                progress_message = get_workflow_message(
                                    "task_recovered",
                                    detected_language,
                                    current=completed_success,
                                    total=len(all_tasks),
                                    agent=agent_display,
                                    tool=tool_display,
                                    attempts=attempts_used
                                )
                            else:
                                progress_message = get_workflow_message(
                                    "task_completed_sequential",
                                    detected_language,
                                    current=completed_success,
                                    total=len(all_tasks),
                                    agent=agent_display,
                                    tool=tool_display
                                )
                        else:
                            error_detail = result.get("error") or result.get("content", "")
                            base_error = error_detail or get_workflow_message("generic_error", detected_language)
                            progress_message = (
                                f"Task {agent_display} failed after {attempts_used} attempts: {base_error}" if base_error else get_workflow_message(
                                    "task_failed",
                                    detected_language,
                                    agent=agent_display,
                                    tool=tool_display,
                                    error=""
                                )
                            )

                        yield {
                            "type": "progress",
                            "node": "execute_planning",
                            "output": {
                                "processing_status": "task_completed" if status == "completed" else "task_failed",
                                "progress_percentage": exact_progress,
                                "progress_message": progress_message,
                                "current_step": "task_completion",
                                "total_steps": len(all_tasks),
                                "formatted_tasks": formatted_tasks,
                                "task_status_update": {
                                    "type": "task_completed" if status == "completed" else "task_failed",
                                    "task_index": task_idx,
                                    "status": "completed" if status == "completed" else "failed",
                                    "color": "success" if status == "completed" else "danger",
                                    "retry_attempts": attempts_used,
                                    "is_retry_success": status == "completed" and attempts_used > 1, 
                                    "enhanced_success": status == "completed" and attempts_used > 1 
                                },
                                "should_yield": True
                            }
                        }
                        await asyncio.sleep(0)
                        
                        pending_tasks.discard(completed_task)

                except Exception as wait_exc:
                    logger.error(f"Error in asyncio.wait: {wait_exc}")
            
                    for task in list(pending_tasks):
                        if not task.done():
                            task.cancel()
                    pending_tasks.clear()
                    if queue_listener:
                        queue_listener.cancel()
                    break

            if queue_listener:
                queue_listener.cancel()

            filtered_results = [res for res in processed_results if res is not None]
            actual_successful = sum(1 for r in filtered_results if r.get("status") == "completed")
            logger.info(
                f"Parallel execution completed: {actual_successful}/{len(all_tasks)} tasks successful"
            )
            yield {
                "type": "result",
                "results": filtered_results,
                "formatted_tasks": formatted_tasks
            }

        except Exception as e:
            logger.error(f"Parallel execution failed: {e}")

            for task_future, _ in execution_tasks:
                if not task_future.done():
                    task_future.cancel()

            raise e

    async def _execute_single_task(
        self,
        state: RAGState,
        task: Dict[str, Any],
        task_index: int,
        progress_queue: Optional[Queue] = None
    ) -> AgentResponse:
        """
        Execute a single task from the execution plan with retry support.
        Tools structure: [{"tool": "tool_name", "message": "specific_message"}]
        """
        start_time = time.time()

        agent_name = task.get("agent", "general")
        agent_id = task.get("agent_id")
        tools = task.get("tools", [])
        purpose = task.get("purpose", "")

        logger.debug(f"Executing task {task_index}: {agent_name} -> Purpose: {purpose}")

        max_attempts = self.MAX_RETRY_ATTEMPTS
        retry_history: List[Dict[str, Any]] = []
        retry_error: Optional[str] = None

        async def run_single_attempt(attempt: int) -> Dict[str, Any]:
            if isinstance(tools, list) and len(tools) > 1:
                tools_names = [t.get('tool', t) if isinstance(t, dict) else t for t in tools]
                logger.info(f"Task {task_index} using sequential tools (attempt {attempt}): {tools_names}")
                queries = task.get("queries", [])
                return await self._execute_agent_with_sequential_tools(
                    state,
                    agent_name,
                    tools,
                    purpose,
                    agent_id,
                    queries,
                    attempt=attempt,
                    retry_error=retry_error
                )

            if tools and isinstance(tools, list) and len(tools) > 0:
                tool_obj = tools[0]
                if isinstance(tool_obj, dict):
                    tool_name = tool_obj.get("tool", "rag_tool")
                    tool_message = tool_obj.get("message", purpose)
                else:
                    tool_name = str(tool_obj)
                    tool_message = purpose
            else:
                tool_name = "rag_tool"
                tool_message = purpose

            queries = task.get("queries", [])
            if queries and isinstance(queries, list) and len(queries) > 0:
                query_to_use = queries[0]
            else:
                query_to_use = tool_message

            return await self._execute_agent_task(
                state,
                agent_name,
                tool_name,
                query_to_use,
                agent_id,
                attempt=attempt,
                retry_error=retry_error
            )

        for attempt in range(1, max_attempts + 1):
            try:
                agent_response = await run_single_attempt(attempt)

                if agent_response.get("error"):
                    raise RuntimeError(str(agent_response.get("error")))

                execution_time = time.time() - start_time

                tools_used = []
                for tool in tools:
                    if isinstance(tool, dict):
                        tools_used.append(tool.get("tool", "unknown"))
                    else:
                        tools_used.append(str(tool))

                response_status = agent_response.get("status", "completed")
                enhanced_response = {
                    **agent_response,
                    "task_index": task_index,
                    "agent_name": agent_name,
                    "tools_used": tools_used,
                    "purpose": purpose,
                    "execution_time": execution_time,
                    "status": response_status,
                    "attempts": attempt,
                    "retry_attempts": agent_response.get("retry_attempts", attempt),
                    "retry_history": agent_response.get("retry_history", retry_history),
                    "max_retries": agent_response.get("max_retries", self.MAX_RETRY_ATTEMPTS),
                }

                return enhanced_response

            except asyncio.CancelledError:
                raise
            except Exception as e:
                error_message = str(e)
                retry_history.append({"attempt": attempt, "error": error_message})
                logger.warning(
                    f"Task {task_index} attempt {attempt} failed for agent {agent_name}: {error_message}"
                )

                if progress_queue and attempt < max_attempts:
                    await progress_queue.put({
                        "type": "retry",
                        "task_index": task_index,
                        "attempt": attempt,
                        "max_attempts": max_attempts,
                        "error": error_message,
                        "agent_name": agent_name,
                        "tools": tools,
                    })

                if attempt >= max_attempts:
                    execution_time = time.time() - start_time
                    return {
                        "agent_name": agent_name,
                        "content": f"Task execution failed: {error_message}",
                        "status": "failed",
                        "confidence": 0.0,
                        "sources": [],
                        "execution_time": execution_time,
                        "error": error_message,
                        "task_index": task_index,
                        "attempts": attempt,
                        "retry_attempts": attempt,
                        "retry_history": retry_history,
                        "purpose": purpose,
                        "tools_used": [t.get("tool", "unknown") if isinstance(t, dict) else str(t) for t in tools] if tools else [],
                        "max_retries": self.MAX_RETRY_ATTEMPTS,
                    }

                retry_error = error_message
                await asyncio.sleep(0.1 * attempt)

        execution_time = time.time() - start_time
        logger.error(f"Task {task_index} could not complete after retries")
        return {
            "agent_name": agent_name,
            "content": "Task execution failed after retries",
            "status": "failed",
            "confidence": 0.0,
            "sources": [],
            "execution_time": execution_time,
            "error": retry_error or "Unknown error",
            "task_index": task_index,
            "attempts": max_attempts,
            "retry_attempts": max_attempts,
            "retry_history": retry_history,
            "purpose": purpose,
            "tools_used": [t.get("tool", "unknown") if isinstance(t, dict) else str(t) for t in tools] if tools else [],
            "max_retries": self.MAX_RETRY_ATTEMPTS,
        }

    async def _execute_agent_task(
        self,
        state: RAGState,
        agent_name: str,
        tool_name: str,
        message: str = None,
        agent_id: str = None,
        attempt: int = 1,
        retry_error: Optional[str] = None
    ) -> Dict[str, Any]:
        """Execute a specific agent with a specific tool"""
        try:
            original_query = state.get("query", "")
            user_context = state.get("user_context", {})
            detected_language = state.get("detected_language", "english")

            query_to_use = message if message else original_query

            if tool_name == "datetime":
                tenant_timezone = user_context.get("timezone") or state.get("tenant_timezone")
                tenant_current_datetime = (
                    user_context.get("tenant_current_datetime")
                    or state.get("tenant_current_datetime")
                )
                query_to_use = self._ensure_datetime_context(
                    query_to_use,
                    tenant_timezone,
                    tenant_current_datetime,
                )

            query_to_use = self._augment_with_retry_context(query_to_use, retry_error, attempt)
            agent_providers = state.get("agent_providers", {})

            attempt_history: List[Dict[str, Any]] = []

            async def execute_agent_operation(db):
                agent_service = AgentService(db)
                return await agent_service.execute_agent(
                    agent_name=agent_name,
                    query=query_to_use,
                    tool_name=tool_name,
                    user_context=user_context,
                    detected_language=detected_language,
                    agent_id=agent_id,
                    agent_providers=agent_providers
                )

            from config.database import execute_db_operation
            agent_result = await execute_db_operation(execute_agent_operation)

            attempt_history.append({
                "attempt": attempt,
                "status": "completed",
                "tool": tool_name,
                "query": query_to_use,
            })

            return {
                "agent_name": agent_name,
                "content": agent_result.get("content", ""),
                "confidence": agent_result.get("confidence", 0.5),
                "sources": agent_result.get("sources", []),
                "tools_used": [tool_name],
                "metadata": agent_result.get("metadata", {}),
                "query_used": query_to_use,
                "attempt": attempt,
                "retry_attempts": attempt,
                "retry_history": attempt_history,
                "max_retries": self.MAX_RETRY_ATTEMPTS,
                "status": "completed",
            }

        except Exception as e:
            logger.error(f"Agent {agent_name} execution failed: {e}")
            error_message = str(e)
            attempt_history = [{
                "attempt": attempt,
                "status": "failed",
                "tool": tool_name,
                "error": error_message,
                "query": query_to_use,
            }]
            return {
                "agent_name": agent_name,
                "content": f"Agent {agent_name} failed: {error_message}",
                "confidence": 0.0,
                "sources": [],
                "tools_used": [tool_name],
                "error": error_message,
                "query_used": original_query,
                "status": "failed",
                "retry_attempts": attempt,
                "retry_history": attempt_history,
                "max_retries": self.MAX_RETRY_ATTEMPTS,
            }

    async def _execute_agent_with_sequential_tools(
        self,
        state: RAGState,
        agent_name: str,
        tools_sequence: List[Any],
        purpose: str = None,
        agent_id: str = None,
        queries: List[str] = None,
        attempt: int = 1,
        retry_error: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute an agent with SEQUENTIAL tools
        tools_sequence: [{"tool": "tool1", "message": "msg1"}, {"tool": "tool2", "message": "msg2"}]
        queries: ["query_for_tool1", "query_for_tool2"] - specific queries for each tool
        Each tool's result becomes context for the next tool
        """
        try:
            original_query = state.get("query", "")
            user_context = state.get("user_context", {})
            detected_language = state.get("detected_language", "english")
            agent_providers = state.get("agent_providers", {})

            all_sources = []
            all_tools_used = []
            accumulated_context = ""
            final_content = ""
            final_confidence = 0.5

            tools_names = []
            for tool in tools_sequence:
                if isinstance(tool, dict):
                    tools_names.append(tool.get("tool", "unknown"))
                else:
                    tools_names.append(str(tool))

            logger.info(f"Agent {agent_name} executing {len(tools_sequence)} tools sequentially: {tools_names}")

            for i, tool_obj in enumerate(tools_sequence):
                if isinstance(tool_obj, dict):
                    current_tool = tool_obj.get("tool", "rag_tool")
                    if queries and isinstance(queries, list) and i < len(queries):
                        tool_message = queries[i]
                    else:
                        tool_message = tool_obj.get("message", purpose or original_query)
                else:
                    current_tool = str(tool_obj)
                    if queries and isinstance(queries, list) and i < len(queries):
                        tool_message = queries[i]
                    else:
                        tool_message = purpose or original_query

                if current_tool == "datetime":
                    tenant_timezone = user_context.get("timezone") or state.get("tenant_timezone")
                    tenant_current_datetime = (
                        user_context.get("tenant_current_datetime")
                        or state.get("tenant_current_datetime")
                    )
                    tool_message = self._ensure_datetime_context(
                        tool_message,
                        tenant_timezone,
                        tenant_current_datetime,
                    )

                if retry_error and attempt > 1 and i == 0:
                    tool_message = self._augment_with_retry_context(tool_message, retry_error, attempt)

                logger.debug(f"Agent {agent_name} executing tool {i+1}/{len(tools_sequence)}: {current_tool}")

                if accumulated_context and i > 0:
                    enriched_query = f"""
{tool_message}

CONTEXT FROM PREVIOUS TOOLS:
{accumulated_context}

INSTRUCTIONS:
Use the results from previous tools as context to:
1. Refine your search/analysis
2. Focus on complementary information
3. Provide more detailed or deeper insights
4. Avoid repeating information already found
5. Build upon previous findings to create a comprehensive response
"""
                else:
                    enriched_query = tool_message

                async def execute_agent_operation(db):
                    agent_service = AgentService(db)
                    return await agent_service.execute_agent(
                        agent_name=agent_name,
                        query=enriched_query,
                        tool_name=current_tool,
                        user_context=user_context,
                        detected_language=detected_language,
                        agent_id=agent_id,
                        agent_providers=agent_providers
                    )

                from config.database import execute_db_operation
                agent_result = await execute_db_operation(execute_agent_operation)

                current_content = agent_result.get("content", "")
                current_sources = agent_result.get("sources", [])
                current_confidence = agent_result.get("confidence", 0.5)

                if current_content:
                    if final_content:
                        final_content += f"\n\n--- {current_tool.upper()} RESULTS ---\n{current_content}"
                    else:
                        final_content = current_content

                    final_confidence = max(final_confidence, current_confidence)

                    tool_context = f"""
TOOL {i+1} ({current_tool}) RESULTS:
Query: {enriched_query}
Response: {current_content}
Confidence: {current_confidence}
Sources: {len(current_sources)} sources found
"""
                    accumulated_context += tool_context

                all_sources.extend(current_sources)
                all_tools_used.append(current_tool)

                logger.debug(f"Agent {agent_name} tool {current_tool} completed. Content length: {len(current_content)}")

            return {
                "agent_name": agent_name,
                "content": final_content,
                "confidence": final_confidence,
                "sources": all_sources,
                "tools_used": all_tools_used,
                "metadata": {
                    "tools_sequence": tools_names,
                    "sequential_execution": True,
                    "total_tools": len(tools_sequence),
                    "accumulated_context_length": len(accumulated_context),
                    "purpose": purpose
                },
                "query_used": purpose or original_query,
                "status": "completed",
                "retry_attempts": attempt,
                "retry_history": [],
                "max_retries": self.MAX_RETRY_ATTEMPTS,
            }

        except Exception as e:
            logger.error(f"Agent {agent_name} sequential execution failed: {str(e)}")
            tools_names = []
            for tool in tools_sequence:
                if isinstance(tool, dict):
                    tools_names.append(tool.get("tool", "unknown"))
                else:
                    tools_names.append(str(tool))
            
            return {
                "agent_name": agent_name,
                "content": f"Agent {agent_name} sequential execution failed: {str(e)}",
                "confidence": 0.0,
                "sources": [],
                "tools_used": tools_names,
                "error": str(e),
                "query_used": purpose or original_query,
                "status": "failed",
                "retry_attempts": attempt,
                "retry_history": [],
                "max_retries": self.MAX_RETRY_ATTEMPTS,
            }

    def _analyze_execution_plan_for_routing(
        self,
        execution_plan: Dict[str, Any],
        successful_responses: List[Dict],
        semantic_routing: Dict[str, Any] = None
    ) -> str:
        """
        Analyze execution plan to determine routing strategy

        Returns:
            "single_agent_sequential": Single agent with sequential tools
            "multiple_agents": Multiple different agents
            "complex": Complex execution plan (fallback)
        """
        try:
            unique_agents = set()

            steps = execution_plan.get("steps", [])
            for step in steps:
                if isinstance(step, dict):
                    tasks = step.get("tasks", [])
                    for task in tasks:
                        if isinstance(task, dict):
                            agent_name = task.get("agent", "")
                            if agent_name:
                                unique_agents.add(agent_name)

            if not unique_agents and successful_responses:
                unique_agents.update([
                    r.get("agent_name", "") for r in successful_responses
                    if r.get("agent_name")
                ])

            logger.info(f"Found {len(unique_agents)} unique agents: {list(unique_agents)}")

            if len(unique_agents) == 1:
                single_agent = list(unique_agents)[0]
                
                has_sequential_tools = False
                for step in steps:
                    if isinstance(step, dict):
                        tasks = step.get("tasks", [])
                        for task in tasks:
                            if isinstance(task, dict) and task.get("agent") == single_agent:
                                tools = task.get("tools", [])
                                if isinstance(tools, list) and len(tools) > 1:
                                    has_sequential_tools = True
                                    break
                        if has_sequential_tools:
                            break

                if has_sequential_tools:
                    logger.info(f"Single agent {single_agent} - treating as single execution")
                return "single_agent_sequential"

            elif len(unique_agents) > 1:
                logger.info(f"Multiple agents detected: {list(unique_agents)}")
                return "multiple_agents"

            else:
                logger.warning("No agents found in execution plan - treating as complex")
                return "complex"

        except Exception as e:
            logger.error(f"Failed to analyze execution plan for routing: {e}")
            return "complex"