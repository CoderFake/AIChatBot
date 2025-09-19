"""
Semantic Reflection Node - Optimized for JSON mode providers
"""
import json
from typing import Dict, Any
from langchain_core.runnables import RunnableConfig
from .base import AnalysisNode
from workflows.langgraph.state.state import RAGState
from utils.logging import get_logger
from utils.language_utils import get_workflow_message

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
                return await self._handle_reflection(state)

        except Exception as e:
            logger.error(f"Semantic reflection failed: {e}")
            return await self._handle_error(e)

    async def _perform_semantic_analysis(self, state: RAGState) -> dict:
        """Perform semantic analysis to detect chitchat and language"""
        try:
            query = state["query"]
            message_history = state.get("messages", [])
            user_context = state["user_context"]
            provider = state.get("provider")

            if not provider:
                logger.warning("No provider available, using simple chitchat/language detection")
                from utils.language_utils import detect_language

                detected_language = detect_language(query)
                semantic_result = {
                    "is_chitchat": True, 
                    "refined_query": query,
                    "summary_history": "",
                    "detected_language": detected_language,
                    "confidence": 0.5
                }
            else:
                # Convert LangChain messages to readable text
                history_text = self._format_message_history(message_history)
                semantic_determination_prompt = self._build_semantic_determination_prompt(history_text, query)

                temperature = user_context.get("temperature", 0.1)
                semantic_response = await provider.ainvoke(
                    semantic_determination_prompt,
                    response_format="json_object",
                    json_mode=True,
                    temperature=temperature,
                    max_tokens=1024
                )

                semantic_content = semantic_response.content.strip()
                if not semantic_content:
                    raise RuntimeError("Provider returned empty response for semantic determination")

                semantic_result = json.loads(semantic_content)

            if "is_chitchat" not in semantic_result:
                semantic_result["is_chitchat"] = False
            if "refined_query" not in semantic_result:
                semantic_result["refined_query"] = query
            if "summary_history" not in semantic_result:
                semantic_result["summary_history"] = ""
            if "detected_language" not in semantic_result:
                semantic_result["detected_language"] = "english"

            result = {
                "semantic_analysis": semantic_result,
                "original_query": query,
                "detected_language": semantic_result["detected_language"] ,
                "is_chitchat": semantic_result.get("is_chitchat", False),
                "summary_history": semantic_result.get("summary_history", "")
            }

            return result

        except Exception as e:
            logger.error(f"Semantic analysis failed: {e}")
            raise

    def _format_message_history(self, messages) -> str:
        """Convert LangChain messages to readable text format"""
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
        
        return "\n".join(formatted_messages[-5:])  
    
    def _build_semantic_determination_prompt(self, message_history: str, query: str) -> str:
        """Build semantic determination prompt to analyze chat history and context"""
    
        return f"""You are a semantic analyzer. Analyze the chat history and current query to determine if this is chitchat or a task that needs execution.

CHAT HISTORY:
{message_history}

CURRENT QUERY: {query}

Analyze the conversation and determine:
1. Is this a casual conversation (chitchat) or a task that requires tool/agent execution?
   - If user asks for current time, weather, calculations, or specific information → NOT chitchat
   - If user just greets, thanks, or makes general conversation → chitchat
2. What is the refined, clear version of the current query?
3. What is the main focus/topic of this conversation?
4. Full description of information compiled from previous conversation not too long but meaningful
5. Accurately judge what language the question is in, for example vietnamese, english, japanese, korean,..

Return ONLY valid JSON:
{{
    "detected_language": "english",
    "is_chitchat": true/false,
    "refined_query": "Clear, specific version of the query",
    "summary_history": "Brief summary of what this conversation is focusing on..."
}}

CRITICAL RULES:
- Return ONLY valid JSON object

CHITCHAT (is_chitchat = true):
- Simple greetings: "Xin chào", "Hello", "Hi"
- Thank you: "Cảm ơn", "Thanks"
- Casual conversation without specific request
- Small talk about general topics

TOOL/AGENT EXECUTION (is_chitchat = false):
- Time-related queries: "Mấy giờ rồi?", "What time is it?", "Bây giờ là mấy giờ?"
- Weather queries: "Thời tiết hôm nay", "Weather today"
- Information search: specific questions about facts, data
- Task execution: calculations, document search, analysis
- Any query that needs real-time data or specific information

- refined_query should be clear and specific
- summary_history should capture the main topic/theme of the conversation
- Language detection is handled separately (ignore this field)"""

    def _build_reflection_prompt(self, query: str, detected_language: str, user_access_levels: list, history_context: str, agents_json: str, semantic_result: dict, user_context: Dict[str, Any]) -> str:
        """Build reflection prompt for execution planning (only called when NOT chitchat)"""
        return f"""You are an expert at planning and delegating tasks. Create detailed execution plan for the user's request.

Information:

LANGUAGE: {detected_language}
ACCESS LEVELS: {user_access_levels}
Conversation Summary: {semantic_result.get("summary_history", "")}
AVAILABLE AGENTS AND TOOLS (nested structure):
{agents_json}

CRITICAL: For time queries like "Mấy giờ rồi?", "What time is it?", use an agent that has "datetime" tool.
For weather queries, use an agent that has "weather" tool.
For calculations, use an agent that has "calculator" tool.

Return ONLY valid JSON for task execution (use EXACT agent names and tool names from the available agents above):
{{
    "original_query": "{query}",
    "refined_query": "{semantic_result.get("refined_query", query)}",
    "is_chitchat": false,
    "permission": {{
        "user_access": {user_access_levels}
    }},
    "execution_flow": {{
        "planning": {{
            "tasks": [{{
                "1": [{{
                    "agent": "hr",
                    "agent_id": "hr-agent-id-here",
                    "tool": "rag_tool",
                    "purpose": "Search for relevant HR information in {detected_language}",
                    "message": "Find information about HR policy in {detected_language}",
                    "status": "pending"
                }}],
                "2": [{{
                    "agent": "it",
                    "agent_id": "it-agent-id-here",
                    "tool": "log_tool",
                    "purpose": "Check system logs for IT issues in {detected_language}",
                    "message": "Analyze logs for IT problem in {detected_language}",
                    "status": "pending"
                }}]
            }}],
            "aggregate_status": "pending"
        }},
        "conflict_resolution": "Handle conflicts using evidence quality"
    }}
}}

CRITICAL RULES:
- Use ONLY agent names, agent_ids and tool names that exist in the AVAILABLE AGENTS structure above
- Include BOTH agent name AND agent_id from the agents structure for each task
- Respect user access levels - only use tools with matching access_level
- Tasks with same number (e.g., "1") run in parallel, different numbers run sequentially
- Make purposes user-friendly and in {detected_language}
- Use {detected_language} for all user-facing text
- Return ONLY valid JSON object with proper structure
- Do NOT add agents or tools that are not in the available list"""

    def _create_execution_plan(self, semantic_routing: dict, agents_structure: dict = None, conversation_context: dict = None) -> dict:
        """Create execution plan from semantic routing"""
        try:
            execution_flow = semantic_routing.get("execution_flow", {})
            planning = execution_flow.get("planning", {})
            tasks_data = planning.get("tasks", [])

            steps = []
            step_counter = 0

            if tasks_data and isinstance(tasks_data, list):
                for task_batch in tasks_data:
                    if isinstance(task_batch, dict):
                        for step_id, task_list in task_batch.items():
                            step_counter += 1
                            planning_tasks = []
                            
                            if isinstance(task_list, list):
                                for task_data in task_list:
                                    if isinstance(task_data, dict):
                                        agent_name = task_data.get("agent", "")
                                        agent_id = task_data.get("agent_id", "")
                                        
                                        if not agent_id and agent_name and agents_structure:
                                            agent_name_lower = agent_name.lower()
                                            if agent_name_lower in agents_structure:
                                                agent_id = agents_structure[agent_name_lower].get("agent_id", "")
                                                logger.info(f"Auto-filled agent_id '{agent_id}' for agent '{agent_name}'")
                                        
                                        original_message = task_data.get("message", "")
                                        enhanced_message = original_message
                                        
                                        if conversation_context:
                                            summary = conversation_context.get("summary_history", "")
                                            original_query = conversation_context.get("original_query", "")
                                            
                                            if summary:
                                                enhanced_message = f"Context: {summary}\nCurrent query: {original_query}\nTask: {original_message}"
                                        
                                        planning_task = {
                                            "agent": agent_name,
                                            "agent_id": agent_id,
                                            "tool": task_data.get("tool", ""),
                                            "message": enhanced_message,
                                            "status": "pending"
                                        }
                                        planning_tasks.append(planning_task)

                            if planning_tasks: 
                                planning_step = {
                                    "step_id": f"step_{step_counter}",
                                    "tasks": planning_tasks,
                                    "status": "pending",
                                    "parallel_execution": len(planning_tasks) > 1
                                }
                                steps.append(planning_step)

            if not steps:
                agents = semantic_routing.get("agents", {})
                if agents and isinstance(agents, dict):
                    logger.info("Creating execution plan from agents structure")
                    for agent_name, agent_data in agents.items():
                        if isinstance(agent_data, dict):
                            queries = agent_data.get("queries", [])
                            tools = agent_data.get("tools", ["rag_tool"])

                            if queries and isinstance(queries, list):
                                for query_item in queries:
                                    if isinstance(query_item, dict):
                                        for query_id, query_text in query_item.items():
                                            step_counter += 1
                                            planning_task = {
                                                "agent": agent_name,
                                                "tool": tools[0] if tools else "rag_tool",
                                                "message": str(query_text),
                                                "status": "pending"
                                            }

                                            planning_step = {
                                                "step_id": f"step_{step_counter}",
                                                "tasks": [planning_task],
                                                "status": "pending",
                                                "parallel_execution": False
                                            }
                                            steps.append(planning_step)

            if not steps:
                raise RuntimeError("No execution steps could be created from semantic routing")

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

            provider = state.get("provider")
            agents_structure_full = state.get("agents_structure")

            if not provider or agents_structure_full is None:
                return await self._handle_error("Provider or agents structure not available")

            agents_json = json.dumps(agents_structure_full, ensure_ascii=False, indent=2)
            logger.info(f"Available agents structure: {agents_json}")

            history_context = state.get("summary_history", "")

            user_access_levels = user_context.get("permissions", ["public"])
            access_scope_override = user_context.get("access_scope")
            if access_scope_override:
                if access_scope_override == "public":
                    user_access_levels = ["public"]
                elif access_scope_override == "private":
                    user_access_levels = ["private"]
                elif access_scope_override == "both":
                    user_access_levels = ["public", "private"]

            prompt = self._build_reflection_prompt(
                query, detected_language, user_access_levels, history_context,
                agents_json, semantic_routing, user_context
            )

            temperature = user_context.get("temperature", 0.1)
            reflection_response = await provider.ainvoke(
                prompt,
                response_format="json_object",
                json_mode=True,
                temperature=temperature,
                max_tokens=2048
            )

            reflection_content = reflection_response.content.strip()
            if not reflection_content:
                raise RuntimeError("Provider returned empty response for reflection")

            parsed_result = json.loads(reflection_content)

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
                            agent_providers[agent_id] = provider
                            logger.debug(f"Loaded provider for agent_id {agent_id}")
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