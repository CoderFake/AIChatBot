"""
Execute Planning Node
Executes the structured planning created by semantic reflection
Coordinates multiple agents and their tools based on the execution plan
"""
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
    Coordinates multiple agents and their tools based on the execution plan
    """

    def __init__(self):
        super().__init__("execute_planning")
        self._progress_callback = None
        self._start_time = None

    def _calculate_progress_percentage(self, step: str, current_step: int = 0, total_steps: int = 0) -> int:
        """
        Calculate real progress percentage based on workflow step and completion
        """
        base_progress = {
            "plan_ready": 0,
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
        """
        Execute the structured planning with agent coordination
        """
        results = []
        async for result in self.execute_with_progress(state, config):
            results.append(result)
        return results[-1] if results else {}

    async def execute_with_progress(self, state: RAGState, config: RunnableConfig):
        """
        Execute with step-by-step progress yielding
        """
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

            plan_tasks = []
            task_counter = 1

            steps = execution_plan.get("steps", [])
            for step in steps:
                if isinstance(step, dict):
                    tasks = step.get("tasks", [])
                    for task in tasks:
                        if isinstance(task, dict):
                            task_copy = task.copy()
                            task_copy["step_number"] = task_counter
                            task_copy["step_id"] = step.get("step_id", f"step_{task_counter}")
                            plan_tasks.append(task_copy)
                            task_counter += 1

            yield {
                "processing_status": "plan_ready",
                "progress_percentage": self._calculate_progress_percentage("plan_ready"),
                "progress_message": get_workflow_message("execution_plan_ready", detected_language),
                "execution_plan": execution_plan,
                "plan_summary": {
                    "total_tasks": len(plan_tasks),
                    "tasks": plan_tasks
                },
                "should_yield": True
            }

            execution_results = []
            async for progress_update in self._execute_sequential_tasks(
                state, execution_plan, original_query, user_context, detected_language, semantic_routing
            ):
                if progress_update.get("type") == "progress":
                    yield progress_update
                elif progress_update.get("type") == "result":
                    execution_results = progress_update.get("results", [])

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
                    "should_yield": True
                }

        except Exception as e:
            logger.error(f"Execute planning failed: {e}")
            yield {
                "error_message": f"Execute planning failed: {str(e)}",
                "next_action": "error",
                "processing_status": "failed",
                "progress_percentage": self._calculate_progress_percentage("failed"),
                "should_yield": True
            }

    async def _execute_planning_parallel(
        self,
        state: RAGState,
        execution_plan: Dict[str, Any],
        original_query: str,
        user_context: Dict[str, Any],
        detected_language: str,
        semantic_routing: Dict[str, Any] = None,
        progress_callback: callable = None
    ) -> List[AgentResponse]:
        """
        Execute the planning in parallel using asyncio.gather
        """
        try:
            planning_tasks = execution_plan.get("execution_flow", {}).get("planning", {}).get("tasks", [])

            if not planning_tasks:
                logger.warning("No planning tasks found in execution plan")
                return []

            all_tasks = []
            for step_tasks in planning_tasks:
                if isinstance(step_tasks, dict):
                    for step_key, tasks in step_tasks.items():
                        if isinstance(tasks, list):
                            all_tasks.extend(tasks)

            if not all_tasks:
                logger.warning("No executable tasks found")
                return []

            logger.info(f"Found {len(all_tasks)} tasks to execute")

            if progress_callback:
                await progress_callback({
                    "node": "execute_planning",
                    "output": {
                        "processing_status": "executing_agents",
                        "progress_percentage": self._calculate_progress_percentage("executing_agents"),
                        "progress_message": get_workflow_message("execution_started", detected_language, total=len(all_tasks)),
                        "current_step": 0,
                        "total_steps": len(all_tasks),
                        "execution_plan": execution_plan,
                        "should_yield": True
                    }
                })

            execution_tasks = []
            task_info = []

            for i, task in enumerate(all_tasks):
                if isinstance(task, dict):
                    agent_name = task.get("agent", "general")
                    tool_name = task.get("tool", "rag_tool")

                    task_future = self._execute_single_task(
                        state, task, i
                    )
                    execution_tasks.append(task_future)
                    task_info.append({
                        "index": i,
                        "agent": agent_name,
                        "tool": tool_name,
                        "status": "pending"
                    })

            if execution_tasks:
                results = await asyncio.gather(*execution_tasks, return_exceptions=True)

                processed_results = []
                completed_count = 0

                for i, result in enumerate(results):
                    task_info[i]["status"] = "completed" if not isinstance(result, Exception) else "failed"

                    if isinstance(result, Exception):
                        logger.error(f"Task {i} failed with exception: {result}")
                        processed_results.append({
                            "agent_name": task_info[i]["agent"],
                            "content": f"Task execution failed: {str(result)}",
                            "status": "failed",
                            "confidence": 0.0,
                            "sources": [],
                            "execution_time": 0.0,
                            "error": str(result),
                            "task_index": i
                        })
                    else:
                        processed_results.append(result)
                        completed_count += 1

                        if progress_callback:
                            progress_pct = 75 + (completed_count / len(all_tasks)) * 10
                            await progress_callback({
                                "node": "execute_planning",
                                "output": {
                                    "processing_status": "executing_agents",
                                    "progress_percentage": progress_pct,
                                    "progress_message": get_workflow_message("task_completed", detected_language,
                                        agent=task_info[i]["agent"], tool=task_info[i]["tool"],
                                        completed=completed_count, total=len(all_tasks)),
                                    "current_step": completed_count,
                                    "total_steps": len(all_tasks),
                                    "task_info": task_info[i],
                                    "should_yield": True
                                }
                            })

                return processed_results

            return []

        except Exception as e:
            logger.error(f"Parallel execution failed: {e}")
            return []

    async def _execute_single_task(
        self,
        state: RAGState,
        task: Dict[str, Any],
        task_index: int
    ) -> AgentResponse:
        """
        Execute a single task from the execution plan
        """
        start_time = time.time()

        try:
            semantic_routing = state.get("semantic_routing", {})
            agent_name = task.get("agent", "general")
            agent_id = task.get("agent_id")
            tool_name = task.get("tool", "rag_tool")
            message = task.get("message", "")

            logger.debug(f"Executing task {task_index}: {agent_name} -> {tool_name}")

            tools_sequence = self._get_tools_sequence_for_task(task, agent_name, semantic_routing)

            if len(tools_sequence) > 1:
                logger.info(f"Task {task_index} using sequential tools: {tools_sequence}")
                agent_response = await self._execute_agent_with_sequential_tools(
                    state, agent_name, tools_sequence, message, agent_id
                )
            else:
                agent_response = await self._execute_agent_task(
                    state, agent_name, tool_name, message, agent_id
                )

            execution_time = time.time() - start_time

            enhanced_response = {
                **agent_response,
                "task_index": task_index,
                "agent_name": agent_name,
                "tool_used": tool_name,
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
        """
        Execute a specific agent with a specific tool
        """
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

    def _get_tools_sequence_for_task(
        self,
        task: Dict[str, Any],
        agent_name: str,
        semantic_routing: Dict[str, Any] = None
    ) -> List[str]:
        """
        Determine the sequence of tools to execute for a task
        Can be specified in task, agent config, or default to single tool
        """
        try:
            if "tools" in task and isinstance(task["tools"], list):
                return task["tools"]

            if semantic_routing and "agents" in semantic_routing:
                agent_config = semantic_routing["agents"].get(agent_name, {})
                if "sequential_tools" in agent_config and isinstance(agent_config["sequential_tools"], list):
                    sequential_tools = agent_config["sequential_tools"]
                    if len(sequential_tools) > 1: 
                        return sequential_tools

                if "tools" in agent_config and isinstance(agent_config["tools"], list):
                    return agent_config["tools"]

            if "tool" in task:
                return [task["tool"]]

            return ["rag_tool"]

        except Exception as e:
            logger.warning(f"Error determining tools sequence for task: {e}")
            return ["rag_tool"]

    async def _execute_agent_with_sequential_tools(
        self,
        state: RAGState,
        agent_name: str,
        tools_sequence: List[str],
        message: str = None,
        agent_id: str = None
    ) -> Dict[str, Any]:
        """
        Execute an agent with sequential tools where each tool's result
        becomes context for the next tool
        """
        try:
            original_query = state.get("query", "")
            user_context = state.get("user_context", {})
            detected_language = state.get("detected_language", "english")
            agent_providers = state.get("agent_providers", {})

            current_query = message if message else original_query
            all_sources = []
            all_tools_used = []
            accumulated_context = ""
            final_content = ""
            final_confidence = 0.5

            logger.info(f"Agent {agent_name} executing {len(tools_sequence)} tools sequentially: {tools_sequence}")

            for i, current_tool in enumerate(tools_sequence):
                logger.debug(f"Agent {agent_name} executing tool {i+1}/{len(tools_sequence)}: {current_tool}")

                if accumulated_context and i > 0:
                    enriched_query = f"""
{current_query}

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
                    enriched_query = current_query

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
                    "tools_sequence": tools_sequence,
                    "sequential_execution": True,
                    "total_tools": len(tools_sequence),
                    "accumulated_context_length": len(accumulated_context)
                },
                "query_used": current_query
            }

        except Exception as e:
            logger.error(f"Agent {agent_name} sequential execution failed: {str(e)}")
            return {
                "agent_name": agent_name,
                "content": f"Agent {agent_name} sequential execution failed: {str(e)}",
                "confidence": 0.0,
                "sources": [],
                "tools_used": tools_sequence,
                "error": str(e),
                "query_used": original_query
            }

    async def _execute_with_detailed_progress(
        self,
        state: RAGState,
        execution_plan: Dict[str, Any],
        original_query: str,
        user_context: Dict[str, Any],
        detected_language: str,
        semantic_routing: Dict[str, Any] = None
    ):
        """
        Execute planning with detailed progress tracking and yielding
        """
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

            logger.info(f"Found {len(all_tasks)} tasks to execute")

            execution_tasks = []
            task_info = []

            for i, task in enumerate(all_tasks):
                if isinstance(task, dict):
                    agent_name = task.get("agent", "general")
                    tool_name = task.get("tool", "rag_tool")

                    task_future = self._execute_single_task(
                        state, task, i
                    )
                    execution_tasks.append(task_future)
                    task_info.append({
                        "index": i,
                        "agent": agent_name,
                        "tool": tool_name,
                        "status": "pending"
                    })

            if execution_tasks:
                results = await asyncio.gather(*execution_tasks, return_exceptions=True)

                processed_results = []
                completed_count = 0

                for i, result in enumerate(results):
                    task_info[i]["status"] = "completed" if not isinstance(result, Exception) else "failed"

                    if isinstance(result, Exception):
                        logger.error(f"Task {i} failed with exception: {result}")
                        processed_results.append({
                            "agent_name": task_info[i]["agent"],
                            "content": f"Task execution failed: {str(result)}",
                            "status": "failed",
                            "confidence": 0.0,
                            "sources": [],
                            "execution_time": 0.0,
                            "error": str(result),
                            "task_index": i
                        })
                    else:
                        processed_results.append(result)
                        completed_count += 1

                        progress_pct = 75 + (completed_count / len(all_tasks)) * 10
                        yield {
                            "type": "progress",
                            "node": "execute_planning",
                            "output": {
                                "processing_status": "executing_agents",
                                "progress_percentage": progress_pct,
                                "progress_message": get_workflow_message("task_completed", detected_language,
                                    agent=task_info[i]["agent"], tool=task_info[i]["tool"],
                                    completed=completed_count, total=len(all_tasks)),
                                "current_step": completed_count,
                                "total_steps": len(all_tasks),
                                "task_info": task_info[i],
                                "should_yield": True
                            }
                        }

                yield {"type": "result", "results": processed_results}

        except Exception as e:
            logger.error(f"Detailed progress execution failed: {e}")
            yield {"type": "result", "results": []}

    async def _execute_sequential_tasks(
        self,
        state: RAGState,
        execution_plan: Dict[str, Any],
        original_query: str,
        user_context: Dict[str, Any],
        detected_language: str,
        semantic_routing: Dict[str, Any] = None
    ):
        """
        Execute tasks sequentially like Cursor - one by one with progress
        """
        try:
            # Get tasks from execution plan steps
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

            logger.info(f"Found {len(all_tasks)} tasks to execute sequentially")

            processed_results = []

            for i, task in enumerate(all_tasks):
                if isinstance(task, dict):
                    agent_name = task.get("agent", "general")
                    tool_name = task.get("tool", "rag_tool")

                    task_purpose = task.get("purpose", f"Execute {agent_name} with {tool_name}")

                    progress_pct = 75 + (i / len(all_tasks)) * 10
                    yield {
                        "type": "progress",
                        "node": "execute_planning",
                        "output": {
                            "processing_status": "executing_task",
                            "progress_percentage": progress_pct,
                            "progress_message": f"Task {i+1}/{len(all_tasks)}: {task_purpose}",
                            "current_step": i + 1,
                            "total_steps": len(all_tasks),
                            "current_task": {
                                "agent": agent_name,
                                "tool": tool_name,
                                "purpose": task_purpose,
                                "index": i
                            },
                            "should_yield": True
                        }
                    }

                    try:
                        result = await self._execute_single_task(
                            state, task, i
                        )

                        if isinstance(result, Exception):
                            logger.error(f"Task {i} failed with exception: {result}")
                            processed_results.append({
                                "agent_name": agent_name,
                                "content": f"Task execution failed: {str(result)}",
                                "status": "failed",
                                "confidence": 0.0,
                                "sources": [],
                                "execution_time": 0.0,
                                "error": str(result),
                                "task_index": i
                            })
                        else:
                            processed_results.append(result)

                            completion_pct = 75 + ((i + 1) / len(all_tasks)) * 10
                            yield {
                                "type": "progress",
                                "node": "execute_planning",
                                "output": {
                                    "processing_status": "task_completed",
                                    "progress_percentage": completion_pct,
                                    "progress_message": f"Completed {i+1}/{len(all_tasks)}: {task_purpose}",
                                    "current_step": i + 1,
                                    "total_steps": len(all_tasks),
                                    "completed_task": {
                                        "agent": agent_name,
                                        "tool": tool_name,
                                        "purpose": task_purpose,
                                        "index": i,
                                        "status": "completed"
                                    },
                                    "should_yield": True
                                }
                            }

                    except Exception as e:
                        logger.error(f"Task {i} execution failed: {e}")
                        processed_results.append({
                            "agent_name": agent_name,
                            "content": f"Task execution failed: {str(e)}",
                            "status": "failed",
                            "confidence": 0.0,
                            "sources": [],
                            "execution_time": 0.0,
                            "error": str(e),
                            "task_index": i
                        })

            yield {"type": "result", "results": processed_results}

        except Exception as e:
            logger.error(f"Sequential execution failed: {e}")
            yield {"type": "result", "results": []}

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

            execution_flow = execution_plan.get("execution_flow", {})
            planning = execution_flow.get("planning", {})
            tasks_data = planning.get("tasks", [])

            if tasks_data and isinstance(tasks_data, list):
                for task_batch in tasks_data:
                    if isinstance(task_batch, dict):
                        for step_id, task_list in task_batch.items():
                            if isinstance(task_list, list):
                                for task_data in task_list:
                                    if isinstance(task_data, dict):
                                        agent_name = task_data.get("agent", "")
                                        if agent_name:
                                            unique_agents.add(agent_name)

            if semantic_routing:
                agents = semantic_routing.get("agents", {})
                if isinstance(agents, dict):
                    unique_agents.update(agents.keys())

            if not unique_agents and successful_responses:
                unique_agents.update([
                    r.get("agent_name", "") for r in successful_responses
                    if r.get("agent_name")
                ])

            logger.info(f"Found {len(unique_agents)} unique agents: {list(unique_agents)}")

            if len(unique_agents) == 1:
                single_agent = list(unique_agents)[0]

                if semantic_routing:
                    agent_config = semantic_routing.get("agents", {}).get(single_agent, {})
                    tools = agent_config.get("tools", [])
                    sequential_tools = agent_config.get("sequential_tools", [])

                    if len(sequential_tools) > 1:
                        logger.info(f"Single agent {single_agent} has sequential tools: {sequential_tools}")
                        return "single_agent_sequential"
                    elif len(tools) > 1:
                        logger.info(f"Single agent {single_agent} has multiple tools: {tools}")
                        return "single_agent_sequential"

                if tasks_data:
                    agent_tasks = []
                    for task_batch in tasks_data:
                        if isinstance(task_batch, dict):
                            for step_id, task_list in task_batch.items():
                                if isinstance(task_list, list):
                                    for task_data in task_list:
                                        if (isinstance(task_data, dict) and
                                            task_data.get("agent") == single_agent):
                                            agent_tasks.append(task_data)

                    if len(agent_tasks) > 1:
                        logger.info(f"Single agent {single_agent} has {len(agent_tasks)} sequential tasks")
                        return "single_agent_sequential"

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

