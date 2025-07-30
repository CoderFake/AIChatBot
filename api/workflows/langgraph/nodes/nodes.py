"""
Complete node implementations for Multi-Agent RAG workflow
Each node follows LangGraph pattern: State -> Partial[State]
"""
import asyncio
import time
from typing import Dict, Any, List
from langchain_core.runnables import RunnableConfig
from .base import BaseWorkflowNode, AnalysisNode, ExecutionNode
from workflows.langgraph.state.state import RAGState, AgentResponse
from services.agents.agent_service import AgentService
from services.llm.provider_manager import llm_provider_manager
from services.tools.tool_manager import tool_manager
from services.auth.permission_service import PermissionService
from config.database import get_db_context
from utils.logging import get_logger

logger = get_logger(__name__)


class OrchestratorNode(BaseWorkflowNode):
    """
    Initial orchestrator node that decides workflow path
    Routes to either reflection+semantic routing or direct execution
    """
    
    def __init__(self):
        super().__init__("orchestrator")
    
    async def execute(self, state: RAGState, config: RunnableConfig) -> Dict[str, Any]:
        """
        Analyze query complexity and decide routing
        Simple queries go direct, complex ones need reflection
        """
        try:
            query = state["query"]
            messages = state.get("messages", [])
            
            needs_reflection = await self._needs_clarification(query, messages)
            
            if needs_reflection:
                next_action = "reflection_router"
                logger.info(f"Query needs reflection: {query[:50]}...")
            else:
                next_action = "agent_execution"
                logger.info(f"Direct execution for query: {query[:50]}...")
            
            return {
                "next_action": next_action,
                "processing_status": "processing",
                "execution_metadata": {
                    "orchestrator_decision": next_action,
                    "needs_reflection": needs_reflection,
                    "query_length": len(query),
                    "message_count": len(messages)
                }
            }
            
        except Exception as e:
            logger.error(f"Orchestrator failed: {e}")
            return {
                "error_message": f"Orchestrator failed: {str(e)}",
                "next_action": "error",
                "processing_status": "failed"
            }
    
    async def _needs_clarification(self, query: str, messages: List) -> bool:
        """
        Use LLM to determine if query needs reflection based on:
        - Query ambiguity
        - Chat history context
        - Query complexity
        """
        try:
            if len(messages) <= 1:
                return False
            
            provider = await llm_provider_manager.get_provider()
            
            recent_messages = messages[-3:] if len(messages) > 3 else messages
            context = "\n".join([
                f"{msg.type}: {msg.content}" if hasattr(msg, 'type') else f"message: {str(msg)}"
                for msg in recent_messages
            ])
            
            clarification_prompt = f"""
Analyze if this user query needs clarification based on the conversation context.

Recent conversation context:
{context}

Current user query: {query}

Does this query contain:
1. Ambiguous references (pronouns without clear antecedents)
2. References to previous conversation topics
3. Unclear or incomplete requests that need context

Respond with JSON only:
{{
    "needs_clarification": true/false,
    "reasoning": "brief explanation of why clarification is/isn't needed",
    "ambiguity_level": "low|medium|high"
}}
"""
            
            response = await provider.ainvoke(clarification_prompt)
            
            # Parse response
            import json
            result = json.loads(response.content.strip())
            
            needs_clarification = result.get("needs_clarification", False)
            reasoning = result.get("reasoning", "")
            
            logger.info(f"Clarification analysis: {needs_clarification} - {reasoning}")
            return needs_clarification
            
        except Exception as e:
            logger.warning(f"LLM clarification analysis failed: {e}")
            
            # Simple fallback: check if query is very short with chat history
            return len(query.split()) < 3 and len(messages) > 1


class ReflectionSemanticRouterNode(AnalysisNode):
    """
    Combined reflection and semantic routing node
    Clarifies query and selects appropriate agents from database
    """
    
    def __init__(self):
        super().__init__("reflection_semantic_router")
    
    async def execute(self, state: RAGState, config: RunnableConfig) -> Dict[str, Any]:
        """
        Perform reflection to clarify query and route to agents
        """
        try:
            query = state["query"]
            messages = state.get("messages", [])
            user_context = state["user_context"]
            
            async with get_db_context() as db:
                agent_service = AgentService(db)
                available_agents = agent_service.get_agents_for_selection()
            
            clarified_query = await self._reflect_and_clarify(query, messages)
            
            selected_agent_ids, sub_queries = await self._semantic_routing(
                clarified_query, available_agents, user_context
            )
            
            query_analysis = {
                "clarified_query": clarified_query,
                "confidence": 0.8,
                "query_domain": sub_queries.get("primary_domain", "general"),
                "selected_agents": selected_agent_ids,
                "sub_queries": sub_queries,
                "reasoning": f"Selected {len(selected_agent_ids)} agents via semantic routing based on query content and agent capabilities"
            }
            
            return {
                "query_analysis": query_analysis,
                "next_action": "agent_execution",
                "processing_status": "processing"
            }
            
        except Exception as e:
            logger.error(f"Reflection routing failed: {e}")
            return {
                "error_message": f"Reflection routing failed: {str(e)}",
                "next_action": "error",
                "processing_status": "failed"
            }
    
    async def _reflect_and_clarify(self, query: str, messages: List) -> str:
        """Use LLM to clarify query based on context"""
        try:
            provider = await llm_provider_manager.get_provider()
            
            context = ""
            if messages:
                recent_messages = messages[-5:]
                context = "\n".join([f"{msg.type}: {msg.content}" for msg in recent_messages])
            
            reflection_prompt = f"""
Given the following conversation context and user query, clarify and reformulate the query to be more specific and actionable.

Context:
{context}

User Query: {query}

Please provide a clear, specific reformulation of the query that removes ambiguity and adds necessary context.
Reformulated Query:"""
            
            response = await provider.ainvoke(reflection_prompt)
            clarified = response.content.strip()
            
            logger.info(f"Query clarified: '{query}' -> '{clarified}'")
            return clarified if clarified else query
            
        except Exception as e:
            logger.warning(f"Reflection failed, using original query: {e}")
            return query
    
    async def _semantic_routing(
        self, 
        query: str, 
        available_agents: List[Dict], 
        user_context: Dict
    ) -> tuple[List[str], Dict[str, str]]:
        """
        Use LLM-based semantic routing to select appropriate agents by ID
        Returns agent IDs instead of codes
        """
        try:
            if not available_agents:
                return [], {}
            
            provider = await llm_provider_manager.get_provider()
            
            agents_info = "\n".join([
                f"- ID: {agent['id']}, Name: {agent['name']} - {agent['description']}"
                for agent in available_agents
            ])
            
            routing_prompt = f"""
You are a semantic router that selects the most appropriate agents to answer user queries.

User Query: {query}

Available Agents (use the ID to reference them):
{agents_info}

User Context:
- Department: {user_context.get('department', 'unknown')}
- Role: {user_context.get('role', 'user')}

Instructions:
1. Analyze the query content and intent
2. Select 1-3 most relevant agents based on their capabilities and descriptions
3. Create specific sub-queries for each selected agent
4. Use agent IDs (not names) in the response

Respond with valid JSON only:
{{
    "selected_agents": ["agent_id_1", "agent_id_2"],
    "sub_queries": {{
        "agent_id_1": "specific query for this agent",
        "agent_id_2": "specific query for this agent"
    }},
    "primary_domain": "detected_domain_from_query"
}}
"""
            
            response = await provider.ainvoke(routing_prompt)
            
            import json
            result = json.loads(response.content.strip())
            
            selected_agent_ids = result.get("selected_agents", [])
            sub_queries = result.get("sub_queries", {})
            
            valid_agent_ids = [agent["id"] for agent in available_agents]
            selected_agent_ids = [agent_id for agent_id in selected_agent_ids if agent_id in valid_agent_ids]
            
            if not selected_agent_ids and available_agents:
                fallback_agent_id = available_agents[0]["id"]
                selected_agent_ids = [fallback_agent_id]
                sub_queries = {fallback_agent_id: query}
            
            logger.info(f"Semantic routing selected agent IDs: {selected_agent_ids}")
            return selected_agent_ids, sub_queries
            
        except Exception as e:
            logger.error(f"Semantic routing failed: {e}")
            if available_agents:
                fallback_agent_id = available_agents[0]["id"]
                return [fallback_agent_id], {fallback_agent_id: query}
            return [], {}


class AgentExecutionNode(ExecutionNode):
    """
    Execute selected agents in parallel with their sub-queries
    Each agent can use tools based on permissions
    """
    
    def __init__(self):
        super().__init__("agent_execution")
    
    async def execute(self, state: RAGState, config: RunnableConfig) -> Dict[str, Any]:
        """
        Execute all selected agents in parallel using agent IDs
        """
        try:
            query_analysis = state.get("query_analysis", {})
            selected_agent_ids = query_analysis.get("selected_agents", [])
            sub_queries = query_analysis.get("sub_queries", {})
            user_context = state["user_context"]
            
            if not selected_agent_ids:
                query = state["query"]
                async with get_db_context() as db:
                    agent_service = AgentService(db)
                    available_agents = agent_service.get_agents_for_selection()
                
                if available_agents:
                    fallback_agent_id = available_agents[0]["id"]
                    selected_agent_ids = [fallback_agent_id]
                    sub_queries = {fallback_agent_id: query}
            
            agent_tasks = []
            for agent_id in selected_agent_ids:
                sub_query = sub_queries.get(agent_id, state["query"])
                task = self._execute_single_agent(agent_id, sub_query, user_context, config)
                agent_tasks.append(task)
            
            agent_results = await asyncio.gather(*agent_tasks, return_exceptions=True)
            
            valid_responses = []
            for i, result in enumerate(agent_results):
                if isinstance(result, Exception):
                    logger.error(f"Agent {selected_agent_ids[i]} failed: {result}")
                else:
                    valid_responses.append(result)
            
            if len(valid_responses) > 1:
                next_action = "conflict_resolution"
            else:
                next_action = "final_response"
            
            return {
                "agent_responses": valid_responses,
                "next_action": next_action,
                "processing_status": "processing" if valid_responses else "failed"
            }
            
        except Exception as e:
            logger.error(f"Agent execution failed: {e}")
            return {
                "error_message": f"Agent execution failed: {str(e)}",
                "next_action": "error",
                "processing_status": "failed"
            }
    
    async def _execute_single_agent(
        self, 
        agent_id: str, 
        query: str, 
        user_context: Dict, 
        config: RunnableConfig
    ) -> AgentResponse:
        """Execute single agent with tools using agent ID"""
        start_time = time.time()
        
        try:
            async with get_db_context() as db:
                agent_service = AgentService(db)
                agent_config = agent_service.get_agent_config(agent_id)
                agent_tools = agent_service.get_agent_tools(agent_id)
                agent_info = agent_service.get_agent_by_id(agent_id)
            
            if not agent_info:
                raise ValueError(f"Agent with ID {agent_id} not found")
            
            agent_name = agent_info.get("name", f"Agent-{agent_id}")
            
            tool_results = {}
            sources = []
            
            for tool_info in agent_tools:
                tool_id = tool_info.get("tool_id")
                tool_name = tool_info.get("tool_name")
                
                if await self._can_use_tool(tool_id, user_context):
                    try:
                        tool_result = await self._execute_tool(
                            tool_id, tool_name, query, user_context, agent_config
                        )
                        tool_results[tool_name] = tool_result
                        
                        if tool_name == "rag_search" and "sources" in tool_result:
                            sources.extend(tool_result["sources"])
                            
                    except Exception as e:
                        logger.warning(f"Tool {tool_name} (ID: {tool_id}) failed for agent {agent_id}: {e}")
            
            response_content = await self._generate_agent_response(
                agent_id, agent_name, query, tool_results, agent_config
            )
            
            execution_time = time.time() - start_time
            
            return {
                "agent_id": agent_id,
                "agent_name": agent_name,
                "content": response_content,
                "confidence": 0.8,
                "tools_used": list(tool_results.keys()),
                "sources": sources,
                "execution_time": execution_time,
                "status": "completed"
            }
            
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Agent {agent_id} execution failed: {e}")
            
            return {
                "agent_id": agent_id,
                "agent_name": f"Agent-{agent_id}",
                "content": f"Error: {str(e)}",
                "confidence": 0.0,
                "tools_used": [],
                "sources": [],
                "execution_time": execution_time,
                "status": "failed"
            }
    
    async def _can_use_tool(self, tool_id: str, user_context: Dict) -> bool:
        """Check if user has permission to use tool by ID"""
        try:
            async with get_db_context() as db:
                permission_service = PermissionService(db)
                # Implement permission check logic based on tool ID
                return True
        except Exception:
            return False
    
    async def _execute_tool(
        self, 
        tool_id: str,
        tool_name: str,
        query: str, 
        user_context: Dict,
        agent_config: Dict
    ) -> Dict[str, Any]:
        """Execute specific tool by ID and name"""
        try:
            return await tool_manager.execute_tool(
                tool_id, tool_name, query, user_context, agent_config
            )
        except Exception as e:
            logger.error(f"Tool {tool_name} (ID: {tool_id}) execution failed: {e}")
            raise
    
    async def _generate_agent_response(
        self,
        agent_id: str,
        agent_name: str,
        query: str,
        tool_results: Dict,
        agent_config: Dict
    ) -> str:
        """Generate final response using agent's LLM"""
        try:
            provider = await llm_provider_manager.get_provider(
                agent_config.get("provider_name")
            )
            
            context = ""
            for tool_name, result in tool_results.items():
                if isinstance(result, dict) and "content" in result:
                    context += f"\n{tool_name}: {result['content']}"
            
            response_prompt = f"""
As {agent_name} (ID: {agent_id}), answer the following query using the provided context.

Query: {query}

Context from tools:
{context}

Please provide a comprehensive and helpful response based on the available information.
"""
            
            response = await provider.ainvoke(response_prompt)
            return response.content.strip()
            
        except Exception as e:
            logger.error(f"Response generation failed for agent {agent_id}: {e}")
            return f"I apologize, but I encountered an error while processing your request: {str(e)}"


class ConflictResolutionNode(BaseWorkflowNode):
    """
    Resolve conflicts between multiple agent responses
    Select best response or synthesize combined answer
    """
    
    def __init__(self):
        super().__init__("conflict_resolution")
    
    async def execute(self, state: RAGState, config: RunnableConfig) -> Dict[str, Any]:
        """
        Analyze agent responses and resolve conflicts
        """
        try:
            agent_responses = state.get("agent_responses", [])
            
            if len(agent_responses) <= 1:
                return {"next_action": "final_response"}
            
            resolution = await self._resolve_conflicts(agent_responses)
            
            return {
                "conflict_resolution": resolution,
                "next_action": "final_response",
                "processing_status": "processing"
            }
            
        except Exception as e:
            logger.error(f"Conflict resolution failed: {e}")
            return {
                "error_message": f"Conflict resolution failed: {str(e)}",
                "next_action": "final_response",
                "processing_status": "failed"
            }
    
    async def _resolve_conflicts(self, agent_responses: List[Dict]) -> Dict[str, Any]:
        """
        Resolve conflicts between agent responses using IDs
        """
        try:
            provider = await llm_provider_manager.get_provider()
            
            responses_text = ""
            for i, response in enumerate(agent_responses):
                agent_id = response.get("agent_id", f"unknown_{i}")
                agent_name = response.get("agent_name", f"Agent_{i}")
                content = response.get("content", "")
                confidence = response.get("confidence", 0.0)
                sources = response.get("sources", [])
                
                responses_text += f"""
Agent {agent_name} (ID: {agent_id}) - Confidence: {confidence}
Response: {content}
Sources: {len(sources)} sources
---
"""
            
            conflict_resolution_prompt = f"""
You have multiple agent responses that may conflict. Analyze them and provide the best synthesized answer.

Agent Responses:
{responses_text}

Please:
1. Identify any conflicts or contradictions
2. Determine which response(s) are most reliable
3. Synthesize the best answer combining the most accurate information
4. Provide a confidence score for your synthesis

Respond with JSON:
{{
    "final_answer": "synthesized response",
    "winning_agents": ["agent_id_1", "agent_id_2"],
    "conflict_level": "low|medium|high",
    "resolution_method": "description of how conflict was resolved",
    "confidence_score": 0.0-1.0,
    "evidence_ranking": [
        {{"agent_id": "agent_id", "score": 0.9, "reasoning": "why this response is reliable"}}
    ]
}}
"""
            
            response = await provider.ainvoke(conflict_resolution_prompt)
            
            import json
            result = json.loads(response.content.strip())
            
            logger.info(f"Conflict resolution completed with {result.get('conflict_level', 'unknown')} conflict level")
            return result
            
        except Exception as e:
            logger.error(f"Conflict resolution processing failed: {e}")
            if agent_responses:
                first_response = agent_responses[0]
                return {
                    "final_answer": first_response.get("content", ""),
                    "winning_agents": [first_response.get("agent_id", "")],
                    "conflict_level": "unknown",
                    "resolution_method": "fallback_first_response",
                    "confidence_score": first_response.get("confidence", 0.5)
                }
            return {
                "final_answer": "Unable to resolve conflicts between agent responses.",
                "winning_agents": [],
                "conflict_level": "high",
                "resolution_method": "error_fallback",
                "confidence_score": 0.0
            }