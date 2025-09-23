"""
Semantic Reflection Node - Optimized for JSON mode providers
workflows/langgraph/nodes/analysis/semantic_reflection_node.py
"""
import json
from typing import Dict, Any
from langchain_core.runnables import RunnableConfig
from .base import AnalysisNode
from workflows.langgraph.state.state import RAGState
from utils.logging import get_logger
from utils.language_utils import get_workflow_message
from services.orchestrator.orchestrator import Orchestrator
from utils.datetime_utils import DateTimeManager

logger = get_logger(__name__)


class SemanticReflectionNode(AnalysisNode):
    """Creates semantic routing and execution planning with optimized JSON responses"""

    def __init__(self):
        super().__init__("semantic_reflection")

    def _calculate_progress_percentage(self, step: str) -> int:
        """Calculate progress percentage for semantic reflection steps"""
        progress_map = {
            "analyzing_query": 10,
            "creating_execution_plan": 15,
            "plan_ready": 20,
            "completed": 25
        }
        return progress_map.get(step, 20)
    
    async def execute(self, state: RAGState, config: RunnableConfig) -> Dict[str, Any]:
        """Execute semantic analysis and route to appropriate node"""
        try:
            result = await self._perform_semantic_analysis(state)

            semantic_routing = result.get("semantic_analysis", {})
            detected_lang = result.get("detected_language", "english").lower()
            state["detected_language"] = detected_lang
            state["is_chitchat"] = semantic_routing.get("is_chitchat", False)
            state["summary_history"] = result.get("summary_history", "")
            state["semantic_routing"] = semantic_routing

            if semantic_routing.get("is_chitchat"):
                return await self._handle_chitchat(state)
            else:
                orchestrator = Orchestrator()
                state["agents_structure"] = await orchestrator.agents_structure(state["user_context"])
                return await self._handle_reflection(state)

        except Exception as e:
            logger.error(f"Semantic reflection failed: {e}")

    def _format_message_history(self, messages, limit: int = 5) -> str:
        """
        Convert LangChain messages to a readable text format.
        
        Args:
            messages (list): List of message objects.
            limit (int): Number of last messages to include (default 5).
        
        Returns:
            str: Formatted message history.
        """
        if not messages:
            return "No previous conversation."
        
        formatted_messages = []
        for msg in messages:
            if hasattr(msg, 'content'):
                if hasattr(msg, 'type'):
                    role = "User" if msg.type == "human" else "Assistant"
                else:
                    role = "User" if "human" in str(type(msg)).lower() else "Assistant"
                formatted_messages.append(f"{role}: {msg.content}")
            else:
                formatted_messages.append(f"Message: {str(msg)}")
        
        if limit and limit > 0:
            formatted_messages = formatted_messages[-limit:]
        
        return "\n".join(formatted_messages)

    def _build_semantic_determination_prompt(self, message_history: str, query: str) -> str:
        """Build semantic determination prompt to analyze chat history and context"""
        return f"""You are a semantic analyzer. Analyze the chat history and current query to determine if this is chitchat or a task that needs execution.

CHAT HISTORY:
{message_history}

CURRENT QUERY: {query}

CRITICAL ANALYSIS:
1. Is this chitchat (casual conversation) or tool execution (needs real-time data/tools)?
   - CHITCHAT ONLY: pure greetings, thanks, small talk with no specific request
   - TOOL EXECUTION: any question requiring current info, calculations, or external data

2. What is the clear, specific version of the query in English?

3. What is the main topic/focus of this conversation?

4. Brief summary of previous conversation context

5. Query language (vietnamese, english, etc.)

Return ONLY valid JSON:
{{
    "detected_language": "english",
    "is_chitchat": true/false,
    "refined_query": "The query version must be clear and specific in the language the user asks.",
    "summary_history": "Brief summary of what this conversation is focusing on..."
}}

CRITICAL RULES:
- Return ONLY valid JSON object
- refined_query is MUST be clear and specific in the language the user asks.
"""

    async def _perform_semantic_analysis(self, state: RAGState) -> dict:
        """Perform semantic analysis to detect chitchat and language"""
        try:
            query = state["query"]
            message_history = state.get("messages", [])
            user_context = state["user_context"]
            provider_name = state.get("provider_name")

            semantic_result = {
                "is_chitchat": False,
                "refined_query": query,
                "summary_history": "",
                "detected_language": "english"
            }

            if provider_name:
                try:
                    orchestrator = Orchestrator()
                    provider = await orchestrator.llm(provider_name)
                    history_text = self._format_message_history(message_history, limit=5)
                    semantic_determination_prompt = self._build_semantic_determination_prompt(history_text, query)

                    temperature = user_context.get("temperature", 0.1)
                    tenant_id = state.get("tenant_id")
                    semantic_response = await provider.ainvoke(
                        semantic_determination_prompt,
                        tenant_id,
                        response_format="json_object",
                        json_mode=True,
                        temperature=temperature,
                        max_tokens=4096
                    )

                    semantic_content = semantic_response.content.strip()
                    if not semantic_content:
                        raise RuntimeError("Provider returned empty response for semantic determination")

                    try:
                        semantic_result = json.loads(semantic_content)
                        logger.info(f"Semantic analysis result: {semantic_result}")
                    except (json.JSONDecodeError, KeyError) as json_err:
                        logger.error(f"Failed to parse semantic analysis JSON: {json_err}, raw content: {semantic_content[:500]}")
                        semantic_result = {
                            "is_chitchat": False,
                            "refined_query": query,
                            "summary_history": "",
                            "detected_language": "english"
                        }
                except RuntimeError as provider_err:
                    if "not found" in str(provider_err).lower():
                        logger.warning(f"Provider {provider_name} not available for semantic analysis, falling back to default: {provider_err}")
                        semantic_result = {
                            "is_chitchat": False,
                            "refined_query": query,
                            "summary_history": "",
                            "detected_language": "english"
                        }
                    else:
                        raise

            result = {
                "semantic_analysis": semantic_result,
                "original_query": query,
                "detected_language": semantic_result["detected_language"],
                "is_chitchat": semantic_result.get("is_chitchat", False),
                "summary_history": semantic_result.get("summary_history", "")
            }

            return result

        except Exception as e:
            logger.error(f"Semantic analysis failed: {e}")
            raise

    def _build_reflection_prompt(self,
        query: str,
        detected_language: str,
        user_access_levels: list,
        history_context: str,
        agents_json: str,
        semantic_result: dict,
        user_context: Dict[str, Any],
        tenant_timezone: str,
        tenant_current_datetime: str,
    ) -> str:
        """Build reflection prompt for execution planning (only called when NOT chitchat)"""
        return f"""You are an expert at planning and delegating tasks. Create detailed execution plan for the user's request.

Information:

LANGUAGE: {detected_language}
ACCESS LEVELS: {user_access_levels}
HISTORY CONTEXT: {history_context}
CONVERSATION SUMMARY FOCUSING ON: {semantic_result.get("summary_history", "")}
TENANT TIMEZONE: {tenant_timezone}
CURRENT TENANT DATETIME: {tenant_current_datetime}

QUERY YOU MUST FOLLOW: {semantic_result.get("refined_query", query)}

AVAILABLE AGENTS AND TOOLS (nested structure):
{agents_json}

CRITICAL EXAMPLE: 
Query: "What time is it?", use an agent that has "datetime" tool.
Query: weather queries, use an agent that has "weather" tool.
Query: calculations, use an agent that has "calculator" tool.
Query: "Find the lateness policy and a brief summary" -> rag tool -> summary tool  
Query: "How many times have I been late this month/year?" -> rag tool(search policy) -> late search tool
Query: "Execute the Internal Training & Evaluation process for employee list X"-> HR Database API / SQL tool -> LMS API / Email Service tool -> Report Generator tool

CRITICAL STRUCTURE - Return ONLY valid JSON for task execution:

{{
    "original_query": "{query}",
    "refined_query": "{semantic_result.get("refined_query", query)}",
    "is_chitchat": false,
    "permission": {{
        "user_access": {user_access_levels}
    }},
    "execution_flow": {{
        "planning": {{
            "tasks": [
                {{
                    "step_1": [
                        {{
                            "agent": "agent_name_from_available_list",
                            "agent_id": "exact_agent_id_from_structure",
                            "purpose": "Overall purpose of this task in {detected_language}",
                            "tools": [
                                {{
                                    "tool": "tool_1_name",
                                    "message": "Specific message for tool_1 in {detected_language}"
                                }},
                                {{
                                    "tool": "tool_2_name", 
                                    "message": "Specific message for tool_2 in {detected_language}"
                                }}
                            ],
                            "queries": ["refined_subquery_1_in_{detected_language}", "refined_subquery_2_in_{detected_language}"],
                            "status": "pending"
                        }}
                    ]
                }},
                {{
                    "step_2": [
                        {{
                            "agent": "another_agent_name",
                            "agent_id": "another_agent_id",
                            "purpose": "Purpose of step 2 in {detected_language}",
                            "tools": [
                                {{
                                    "tool": "tool_name",
                                    "message": "Message for this tool in {detected_language}"
                                }}
                            ],
                            "queries": ["refined_subquery_in_{detected_language}"],
                            "status": "pending"
                        }}
                    ]
                }}
            ],
            "aggregate_status": "pending"
        }},
        "conflict_resolution": "Handle conflicts using evidence quality"
    }}
}}

CRITICAL EXTRACTION RULES:
- Use ONLY agent names and agent_ids that exist in AVAILABLE AGENTS structure
- Each step object contains step_X as key with array of task objects as value
- Tools array must contain tool names that exist for the specified agent
- Respect user access levels when selecting tools
- Tasks with same step number run in parallel, different steps run sequentially
- "queries" should contain specific sub-queries that break down the task into actionable steps
- For time queries: queries like ["Get current time", "Format for user"]
- For weather: queries like ["Get location weather", "Check forecast"]
- Return ONLY valid JSON object - no extra text or formatting

- CRITICAL: All user-facing text (purpose, message, queries) must be in {detected_language} and related to the user's query, refined query.
- CRITICAL: All user-facing text (purpose, message, queries) must be in {detected_language} and related to the user's query, refined query.
- CRITICAL: All user-facing text (purpose, message, queries) must be in {detected_language} and related to the user's query, refined query.

"""

    def _create_execution_plan(self, semantic_routing: dict, agents_structure: dict = None, conversation_context: dict = None) -> dict:
        """Create execution plan from semantic routing with improved structure parsing"""
        try:
            logger.info(f"Creating execution plan from semantic_routing: {semantic_routing}")
            execution_flow = semantic_routing.get("execution_flow", {})
            planning = execution_flow.get("planning", {})
            tasks_data = planning.get("tasks", [])
            logger.info(f"Tasks data: {tasks_data}")

            steps = []
            step_counter = 0

            if tasks_data and isinstance(tasks_data, list):
                for task_batch in tasks_data:
                    if isinstance(task_batch, dict):
                        for step_key, task_list in task_batch.items():
                            if step_key.startswith("step_"):
                                step_counter += 1
                                planning_tasks = []
                                
                                if isinstance(task_list, list):
                                    for task_data in task_list:
                                        if isinstance(task_data, dict):
                                            agent_name = task_data.get("agent", "")
                                            agent_id = task_data.get("agent_id", "")
                                            tools = task_data.get("tools", [])
                                            
                                            if not agent_id and agent_name and agents_structure:
                                                agent_name_lower = agent_name.lower()
                                                if agent_name_lower in agents_structure:
                                                    agent_id = agents_structure[agent_name_lower].get("agent_id", "")
                                                    logger.info(f"Auto-filled agent_id '{agent_id}' for agent '{agent_name}'")
                                            
                                            purpose = task_data.get("purpose", "")
                                            
                                            if conversation_context:
                                                summary = conversation_context.get("summary_history", "")
                                                original_query = conversation_context.get("original_query", "")
                                                
                                                if summary:
                                                    enhanced_purpose = f"Context: {summary}\nCurrent query: {original_query}\nTask: {purpose}"
                                                else:
                                                    enhanced_purpose = purpose
                                            else:
                                                enhanced_purpose = purpose
                                            
                                            planning_task = {
                                                "agent": agent_name,
                                                "agent_id": agent_id,
                                                "purpose": enhanced_purpose,
                                                "tools": tools if isinstance(tools, list) else [{"tool": "rag_tool", "message": purpose}],
                                                "queries": task_data.get("queries", []),
                                                "status": "pending"
                                            }
                                            planning_tasks.append(planning_task)

                                if planning_tasks: 
                                    planning_step = {
                                        "step_id": step_key,
                                        "step_number": step_counter,
                                        "tasks": planning_tasks,
                                        "status": "pending",
                                        "parallel_execution": len(planning_tasks) > 1
                                    }
                                    steps.append(planning_step)

            if not steps:
                logger.warning("No steps found in execution flow, creating fallback plan")
                step_counter = 1
                planning_task = {
                    "agent": "default",
                    "agent_id": "",
                    "tools": ["rag_tool"],
                    "queries": [semantic_routing.get("refined_query", "")],
                    "purpose": "Process user query",
                    "message": semantic_routing.get("refined_query", ""),
                    "status": "pending"
                }

                planning_step = {
                    "step_id": "step_1",
                    "step_number": 1,
                    "tasks": [planning_task],
                    "status": "pending",
                    "parallel_execution": False
                }
                steps.append(planning_step)

            execution_plan = {
                "total_steps": len(steps),
                "current_step": 0,
                "steps": steps,
                "aggregate_status": "pending"
            }

            logger.info(f"Created execution plan with {len(steps)} steps")
            return execution_plan

        except Exception as e:
            logger.error(f"Failed to create execution plan: {e}")
            raise RuntimeError(f"Failed to create execution plan: {e}")

    async def _handle_chitchat(self, state: RAGState) -> Dict[str, Any]:
        """Handle chitchat detection - just set flag for final response to build template"""
        semantic_routing = state.get("semantic_routing", {})
        detected_language = state.get("detected_language", "english")

        summary_text = f"Routing: {semantic_routing.get('routing_decision', 'unknown')}"

        return {
            "semantic_routing": semantic_routing,
            "is_chitchat": True,
            "summary_history": summary_text,
            "next_action": "final_response",
            "processing_status": "chitchat_detected",
            "progress_percentage": self._calculate_progress_percentage("completed"),
            "progress_message": get_workflow_message("chitchat_detected", detected_language),
            "should_yield": True
        }

    async def _handle_reflection(self, state: RAGState) -> Dict[str, Any]:
        """Handle reflection prompt building for non-chitchat queries"""
        try:
            semantic_routing = state.get("semantic_routing", {})
            query = state.get("query", "")
            detected_language = state.get("detected_language", "english")
            user_context = state.get("user_context", {})

            provider_name = state.get("provider_name")
            agents_structure_full = state.get("agents_structure")

            if not provider_name or agents_structure_full is None:
                return await self._handle_error("Provider or agents structure not available")

            agents_json = json.dumps(agents_structure_full, ensure_ascii=False, indent=2)
            logger.info(f"Available agents structure: {agents_json}")

            history_context = self._format_message_history(state.get("messages", []), limit=3)
            tenant_timezone = state.get("tenant_timezone", "UTC")
            tenant_current_datetime = state.get("tenant_current_datetime") or DateTimeManager.system_now().isoformat()
            user_access_levels = state.get("access_scope", "public")

            prompt = self._build_reflection_prompt(
                query,
                detected_language,
                user_access_levels,
                history_context,
                agents_json,
                semantic_routing,
                user_context,
                tenant_timezone,
                tenant_current_datetime,
            )

            temperature = user_context.get("temperature", 0.1)
            tenant_id = state.get("tenant_id")
            orchestrator = Orchestrator()
            provider = await orchestrator.llm(provider_name)
            reflection_response = await provider.ainvoke(
                prompt,
                tenant_id,
                response_format="json_object",
                json_mode=True,
                temperature=temperature,
                max_tokens=4096
            )

            reflection_content = reflection_response.content.strip()
            if not reflection_content:
                raise RuntimeError("Provider returned empty response for reflection")

            parsed_result = json.loads(reflection_content)
            logger.info(f"Reflection result: {parsed_result}")

            conversation_context = {
                "summary_history": state.get("summary_history", ""),
                "original_query": query,
                "detected_language": detected_language
            }
            execution_plan = self._create_execution_plan(parsed_result, agents_structure_full, conversation_context)

            agent_providers = await self._load_agent_providers_for_plan(execution_plan, user_context, agents_structure_full)

            return {
                "semantic_routing": semantic_routing,
                "reflection_result": parsed_result,
                "execution_plan": execution_plan,
                "agent_providers": agent_providers,
                "next_action": "execute_planning",
                "processing_status": "planning_ready",
                "progress_percentage": self._calculate_progress_percentage("plan_ready"),
                "progress_message": get_workflow_message(
                    "planning_created",
                    detected_language,
                    total_steps=execution_plan['total_steps']
                ),
                "should_yield": True
            }

        except Exception as e:
            logger.error(f"Reflection handling failed: {e}")
            return {
                "error_message": str(e),
                "original_error": str(e),
                "exception_type": type(e).__name__,
                "next_action": "error",
                "processing_status": "failed",
                "should_yield": True
            }

    async def _handle_execution(self, result: Dict[str, Any], detected_language: str) -> Dict[str, Any]:
        """Handle execution planning response"""
        semantic_routing = result["semantic_routing"]
        execution_plan = result["execution_plan"]

        return {
            "semantic_routing": semantic_routing,
            "execution_plan": execution_plan,
            "next_action": "execute_planning",
            "processing_status": "planning_ready",
            "progress_percentage": self._calculate_progress_percentage("plan_ready"),
            "progress_message": get_workflow_message(
                "planning_created",
                detected_language,
                total_steps=execution_plan['total_steps']
            ),
            "should_yield": True
        }

    async def _handle_error(self, error=None) -> Dict[str, Any]:
        """Handle error with proper error information"""
        if error is None:
            error_message = "Semantic analysis failed"
            exception_type = "Exception"
        elif isinstance(error, str):
            error_message = error
            exception_type = "ValidationError"
        else:
            error_message = str(error)
            exception_type = type(error).__name__

        return {
            "error_message": error_message,
            "original_error": error_message,
            "exception_type": exception_type,
            "next_action": "error",
            "processing_status": "failed",
            "should_yield": True
        }

    async def _load_agent_providers_for_plan(self, execution_plan: Dict[str, Any], user_context: Dict[str, Any], agents_structure: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Load agent providers only for agents mentioned in the execution plan
        """
        try:
            from services.agents.agent_service import AgentService
            from config.database import execute_db_operation

            tenant_id = user_context.get("tenant_id")
            if not tenant_id:
                logger.warning("No tenant_id in user_context, cannot load agent providers")
                return {}

            logger.info(f"Loading agent providers for plan: {type(execution_plan)} - {execution_plan}")
            agent_ids = set()
            
            if agents_structure is None:
                agents_structure = {}
            
            if "steps" in execution_plan:
                for step in execution_plan["steps"]:
                    if isinstance(step, dict) and "tasks" in step:
                        for task in step["tasks"]:
                            if isinstance(task, dict) and "agent_id" in task and task["agent_id"]:
                                agent_ids.add(task["agent_id"])
                                logger.info(f"Found agent_id: {task['agent_id']}")

            if not agent_ids:
                logger.debug("No agent_ids found in execution plan")
                return {}

            async def load_providers_operation(db):
                agent_service = AgentService(db)
                agent_providers = {}

                for agent_id in agent_ids:
                    try:
                        provider = await agent_service._get_agent_llm_provider(agent_id, tenant_id)
                        if provider:
                            agent_providers[agent_id] = getattr(provider, 'name', f'provider_{agent_id}')
                            logger.debug(f"Loaded provider name for agent_id {agent_id}")
                        else:
                            logger.warning(f"No provider found for agent_id {agent_id}")
                    except Exception as e:
                        logger.warning(f"Failed to load provider for agent_id {agent_id}: {e}")

                return agent_providers

            agent_providers = await execute_db_operation(load_providers_operation)
            logger.info(f"Loaded {len(agent_providers)} agent providers for execution plan")
            return agent_providers

        except Exception as e:
            logger.error(f"Failed to load agent providers for plan: {e}")
            return {}