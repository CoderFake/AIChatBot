import asyncio
import time
from typing import Dict, Any, List
from langchain_core.runnables import RunnableConfig
from .base import ExecutionNode
from workflows.langgraph.state.state import RAGState, AgentResponse
from services.agents.agent_service import AgentService
from utils.logging import get_logger
from utils.language_utils import get_workflow_message

logger = get_logger(__name__)


class ExecutePlanningNode(ExecutionNode):
    """
    Execute the structured planning created by semantic reflection
    Steps (step_1, step_2...) run in PARALLEL
    Tools within each task run SEQUENTIALLY (tool1 -> tool2 -> tool3)
    """

    def __init__(self):
        super().__init__("execute_planning")

    def _calculate_progress_percentage(self, step: str, current_step: int = 0, total_steps: int = 0) -> int:
        """Calculate real progress percentage based on workflow step and completion"""
        base_progress = {
            "plan_ready": 20,
            "executing_agents": 75,
            "executing_task": 75,
            "task_completed": 75,
            "completed": 85,
            "conflict_resolution_needed": 85
        }

        progress = base_progress.get(step, 75)

        if total_steps > 0 and current_step > 0:
            task_progress = int((current_step / total_steps) * 10)
            progress = min(85, progress + task_progress)

        return progress

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
                yield {
                    "agent_responses": successful_responses,
                    "next_action": "final_response",
                    "routing_decision": routing_decision,
                    "processing_status": "completed",
                    "progress_percentage": self._calculate_progress_percentage("completed"),
                    "progress_message": progress_msg,
                    "formatted_tasks": formatted_tasks,
                    "should_yield": True
                }

            elif routing_decision == "multiple_agents":
                logger.info("Routing to conflict_resolution: Multiple agents detected")
                yield {
                    "agent_responses": successful_responses,
                    "next_action": "conflict_resolution",
                    "routing_decision": routing_decision,
                    "processing_status": "ready_for_resolution",
                    "progress_percentage": self._calculate_progress_percentage("conflict_resolution_needed"),
                    "progress_message": get_workflow_message("conflict_resolution_needed", detected_language),
                    "formatted_tasks": formatted_tasks,
                    "should_yield": True
                }

            else:
                logger.info("Routing to conflict_resolution: Complex execution plan")
                yield {
                    "agent_responses": successful_responses,
                    "next_action": "conflict_resolution",
                    "routing_decision": routing_decision,
                    "processing_status": "ready_for_resolution",
                    "progress_percentage": self._calculate_progress_percentage("conflict_resolution_needed"),
                    "progress_message": get_workflow_message("conflict_resolution_needed", detected_language),
                    "formatted_tasks": formatted_tasks,
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
                            "task_index": len(formatted_tasks)
                        }
                        formatted_tasks.append(formatted_task)
        
        return formatted_tasks

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
                task_info.pop("result", None)
                task_info.pop("error", None)

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
                            formatted_tasks[i]["status"] = "in_progress"
                            formatted_tasks[i]["agent"] = task.get("agent", formatted_tasks[i].get("agent", ""))
                        task_future = asyncio.create_task(self._execute_single_task(state, task, i))
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
            pending_tasks = [future for future, idx in execution_tasks]
            
            while pending_tasks:
                try:
                    done, pending_tasks = await asyncio.wait(pending_tasks, return_when=asyncio.FIRST_COMPLETED)
                    
                    for completed_task in done:
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
                            formatted_tasks[task_idx]["status"] = "completed" if status == "completed" else "failed"
                            formatted_tasks[task_idx]["result"] = result
                            if status != "completed":
                                formatted_tasks[task_idx]["error"] = result.get("error") or result.get("content")

                        tools_used = result.get("tools_used") or []
                        tool_display = ", ".join(tools_used) if isinstance(tools_used, list) and tools_used else result.get("tool") or "tool"
                        agent_display = result.get("agent_name") or result.get("agent") or "Agent"

                        if status == "completed":
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
                            progress_message = (
                                f"Task {agent_display} failed: {error_detail}" if error_detail else get_workflow_message(
                                    "generic_error",
                                    detected_language
                                )
                            )

                        yield {
                            "type": "progress",
                            "node": "execute_planning",
                            "output": {
                                "processing_status": "task_completed" if status == "completed" else "task_failed",
                                "progress_percentage": self._calculate_progress_percentage(
                                    "task_completed", processed_count, len(all_tasks)
                                ),
                                "progress_message": progress_message,
                                "current_step": processed_count,
                                "total_steps": len(all_tasks),
                                "formatted_tasks": formatted_tasks,
                                "should_yield": True
                            }
                        }
                        
                except Exception as wait_exc:
                    logger.error(f"Error in asyncio.wait: {wait_exc}")
                    # Cancel remaining tasks
                    for task in pending_tasks:
                        if not task.done():
                            task.cancel()
                    break

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

            # Cancel all pending tasks
            for task_future, _ in execution_tasks:
                if not task_future.done():
                    task_future.cancel()

            # Re-raise the exception to let the caller handle it
            raise e

    async def _execute_single_task(
        self,
        state: RAGState,
        task: Dict[str, Any],
        task_index: int
    ) -> AgentResponse:
        """
        Execute a single task from the execution plan
        Tools structure: [{"tool": "tool_name", "message": "specific_message"}]
        """
        start_time = time.time()

        try:
            agent_name = task.get("agent", "general")
            agent_id = task.get("agent_id")
            tools = task.get("tools", [])
            purpose = task.get("purpose", "")

            logger.debug(f"Executing task {task_index}: {agent_name} -> Purpose: {purpose}")

            if isinstance(tools, list) and len(tools) > 1:
                tools_names = [t.get('tool', t) if isinstance(t, dict) else t for t in tools]
                logger.info(f"Task {task_index} using sequential tools: {tools_names}")
                queries = task.get("queries", [])
                agent_response = await self._execute_agent_with_sequential_tools(
                    state, agent_name, tools, purpose, agent_id, queries
                )
            else:
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

                # Use queries from task if available, otherwise use tool_message
                queries = task.get("queries", [])
                if queries and isinstance(queries, list) and len(queries) > 0:
                    query_to_use = queries[0]  # Use first query as main query
                else:
                    query_to_use = tool_message

                agent_response = await self._execute_agent_task(
                    state, agent_name, tool_name, query_to_use, agent_id
                )

            execution_time = time.time() - start_time

            tools_used = []
            for tool in tools:
                if isinstance(tool, dict):
                    tools_used.append(tool.get("tool", "unknown"))
                else:
                    tools_used.append(str(tool))

            enhanced_response = {
                **agent_response,
                "task_index": task_index,
                "agent_name": agent_name,
                "tools_used": tools_used,
                "purpose": purpose,
                "execution_time": execution_time,
                "status": "completed"
            }

            return enhanced_response

        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Task {task_index} execution failed: {e}")

            return {
                "agent_name": f"Task_{task_index}",
                "content": f"Task execution failed: {str(e)}",
                "status": "failed",
                "confidence": 0.0,
                "sources": [],
                "execution_time": execution_time,
                "error": str(e),
                "task_index": task_index
            }

    async def _execute_agent_task(
        self,
        state: RAGState,
        agent_name: str,
        tool_name: str,
        message: str = None,
        agent_id: str = None
    ) -> Dict[str, Any]:
        """Execute a specific agent with a specific tool"""
        try:
            original_query = state.get("query", "")
            user_context = state.get("user_context", {})
            detected_language = state.get("detected_language", "english")

            query_to_use = message if message else original_query
            agent_providers = state.get("agent_providers", {})

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

            return {
                "agent_name": agent_name,
                "content": agent_result.get("content", ""),
                "confidence": agent_result.get("confidence", 0.5),
                "sources": agent_result.get("sources", []),
                "tools_used": [tool_name],
                "metadata": agent_result.get("metadata", {}),
                "query_used": query_to_use
            }

        except Exception as e:
            logger.error(f"Agent {agent_name} execution failed: {e}")
            return {
                "agent_name": agent_name,
                "content": f"Agent {agent_name} failed: {str(e)}",
                "confidence": 0.0,
                "sources": [],
                "tools_used": [tool_name],
                "error": str(e),
                "query_used": original_query
            }

    async def _execute_agent_with_sequential_tools(
        self,
        state: RAGState,
        agent_name: str,
        tools_sequence: List[Any],
        purpose: str = None,
        agent_id: str = None,
        queries: List[str] = None
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
                "query_used": purpose or original_query
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
                "query_used": purpose or original_query
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