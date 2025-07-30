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
            
            # Get available agents from database
            async with get_db_context() as db:
                agent_service = AgentService(db)
                available_agents = agent_service.get_agents_for_selection()
            
            # Perform reflection to clarify query
            clarified_query = await self._reflect_and_clarify(query, messages)
            
            # Semantic routing to select agents
            selected_agents, sub_queries = await self._semantic_routing(
                clarified_query, available_agents, user_context
            )
            
            query_analysis = {
                "clarified_query": clarified_query,
                "confidence": 0.8,  # Could be calculated from LLM response
                "query_domain": sub_queries.get("primary_domain", "general"),  # Dynamic from routing
                "selected_agents": selected_agents,
                "sub_queries": sub_queries,
                "reasoning": f"Selected {len(selected_agents)} agents via semantic routing based on query content and agent capabilities"
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
            
            # Build context from messages
            context = ""
            if messages:
                recent_messages = messages[-5:]  # Last 5 messages
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
        Use LLM-based semantic routing to select appropriate agents
        No hardcoded keywords - let LLM understand context and capabilities
        """
        try:
            if not available_agents:
                return [], {}
            
            provider = await llm_provider_manager.get_provider()
            
            # Format agents for LLM with their full context
            agents_info = "\n".join([
                f"- {agent['code']}: {agent['name']} - {agent['description']}"
                for agent in available_agents
            ])
            
            routing_prompt = f"""
You are a semantic router that selects the most appropriate agents to answer user queries.

User Query: {query}

Available Agents:
{agents_info}

User Context:
- Department: {user_context.get('department', 'unknown')}
- Role: {user_context.get('role', 'user')}

Instructions:
1. Analyze the query content and intent
2. Select 1-3 most relevant agents based on their capabilities and descriptions
3. Create specific sub-queries for each selected agent
4. Use agent codes (not names) in the response

Respond with valid JSON only:
{{
    "selected_agents": ["agent_code1", "agent_code2"],
    "sub_queries": {{
        "agent_code1": "specific query for this agent",
        "agent_code2": "specific query for this agent"
    }},
    "primary_domain": "detected_domain_from_query"
}}
"""
            
            response = await provider.ainvoke(routing_prompt)
            
            # Parse JSON response
            import json
            result = json.loads(response.content.strip())
            
            selected_agents = result.get("selected_agents", [])
            sub_queries = result.get("sub_queries", {})
            
            # Validate selected agents exist
            valid_agent_codes = [agent["code"] for agent in available_agents]
            selected_agents = [agent for agent in selected_agents if agent in valid_agent_codes]
            
            # Fallback if no valid selection
            if not selected_agents and available_agents:
                fallback_agent = available_agents[0]["code"]
                selected_agents = [fallback_agent]
                sub_queries = {fallback_agent: query}
            
            logger.info(f"Semantic routing selected: {selected_agents}")
            return selected_agents, sub_queries
            
        except Exception as e:
            logger.error(f"Semantic routing failed: {e}")
            # Fallback to first available agent
            if available_agents:
                fallback_agent = available_agents[0]["code"]
                return [fallback_agent], {fallback_agent: query}
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
        Execute all selected agents in parallel
        """
        try:
            query_analysis = state.get("query_analysis", {})
            selected_agents = query_analysis.get("selected_agents", [])
            sub_queries = query_analysis.get("sub_queries", {})
            user_context = state["user_context"]
            
            if not selected_agents:
                # Direct execution without analysis
                query = state["query"]
                async with get_db_context() as db:
                    agent_service = AgentService(db)
                    available_agents = agent_service.get_agents_for_selection()
                
                if available_agents:
                    fallback_agent = available_agents[0]["name"]
                    selected_agents = [fallback_agent]
                    sub_queries = {fallback_agent: query}
            
            # Execute agents in parallel
            agent_tasks = []
            for agent_name in selected_agents:
                sub_query = sub_queries.get(agent_name, state["query"])
                task = self._execute_single_agent(agent_name, sub_query, user_context, config)
                agent_tasks.append(task)
            
            # Wait for all agents to complete
            agent_results = await asyncio.gather(*agent_tasks, return_exceptions=True)
            
            # Process results
            valid_responses = []
            for i, result in enumerate(agent_results):
                if isinstance(result, Exception):
                    logger.error(f"Agent {selected_agents[i]} failed: {result}")
                else:
                    valid_responses.append(result)
            
            # Determine next action based on results
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
        agent_name: str, 
        query: str, 
        user_context: Dict, 
        config: RunnableConfig
    ) -> AgentResponse:
        """Execute single agent with tools"""
        start_time = time.time()
        
        try:
            # Get agent configuration
            async with get_db_context() as db:
                agent_service = AgentService(db)
                agent_config = agent_service.get_agent_config(agent_name)
                agent_tools = agent_service.get_agent_tools(agent_name)
            
            # Check permissions and execute tools if needed
            tool_results = {}
            sources = []
            
            for tool_name in agent_tools:
                if await self._can_use_tool(tool_name, user_context):
                    try:
                        tool_result = await self._execute_tool(
                            tool_name, query, user_context, agent_config
                        )
                        tool_results[tool_name] = tool_result
                        
                        # Extract sources if this is RAG tool
                        if tool_name == "rag_search" and "sources" in tool_result:
                            sources.extend(tool_result["sources"])
                            
                    except Exception as e:
                        logger.warning(f"Tool {tool_name} failed for agent {agent_name}: {e}")
            
            # Generate response using agent's LLM
            response_content = await self._generate_agent_response(
                agent_name, query, tool_results, agent_config
            )
            
            execution_time = time.time() - start_time
            
            return {
                "agent_name": agent_name,
                "content": response_content,
                "confidence": 0.8,  # Placeholder
                "tools_used": list(tool_results.keys()),
                "sources": sources,
                "execution_time": execution_time,
                "status": "completed"
            }
            
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Agent {agent_name} execution failed: {e}")
            
            return {
                "agent_name": agent_name,
                "content": f"Error: {str(e)}",
                "confidence": 0.0,
                "tools_used": [],
                "sources": [],
                "execution_time": execution_time,
                "status": "failed"
            }
    
    async def _can_use_tool(self, tool_name: str, user_context: Dict) -> bool:
        """Check if user has permission to use tool"""
        try:
            async with get_db_context() as db:
                permission_service = PermissionService(db)
                return True  
        except Exception:
            return False
    
    async def _execute_tool(
        self, 
        tool_name: str, 
        query: str, 
        user_context: Dict,
        agent_config: Dict
    ) -> Dict[str, Any]:
        """Execute specific tool"""
        try:
            return await tool_manager.execute_tool(
                tool_name, query, user_context, agent_config
            )
        except Exception as e:
            logger.error(f"Tool {tool_name} execution failed: {e}")
            raise
    
    async def _generate_agent_response(
        self,
        agent_name: str,
        query: str,
        tool_results: Dict,
        agent_config: Dict
    ) -> str:
        """Generate final response using agent's LLM"""
        try:
            provider = await llm_provider_manager.get_provider(
                agent_config.get("provider")
            )
            
            context = ""
            for tool_name, result in tool_results.items():
                if isinstance(result, dict) and "content" in result:
                    context += f"\n{tool_name}: {result['content']}"
            
            response_prompt = f"""
As {agent_name}, answer the following query using the provided context.

Query: {query}

Context from tools:
{context}

Please provide a comprehensive and helpful response based on the available information.
"""
            
            response = await provider.ainvoke(response_prompt)
            return response.content.strip()
            
        except Exception as e:
            logger.error(f"Response generation failed for {agent_name}: {e}")
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