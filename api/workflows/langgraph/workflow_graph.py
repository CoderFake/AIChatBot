"""
Complete Multi-Agent RAG Workflow using LangGraph
"""
from typing import Dict, Any, Optional
from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from .state.state import RAGState
from .nodes.nodes import (
    OrchestratorNode,
    ReflectionSemanticRouterNode, 
    AgentExecutionNode,
    ConflictResolutionNode
)
from .edges.edges import (
    create_orchestrator_router,
    create_reflection_router,
    create_agent_execution_router,
    create_conflict_resolution_router,
    create_error_router
)
from utils.logging import get_logger

logger = get_logger(__name__)


class FinalResponseNode:
    """
    Final response node that assembles the complete answer
    """
    
    def __init__(self):
        self.node_name = "final_response"
    
    def __call__(self, state: RAGState, config: RunnableConfig) -> Dict[str, Any]:
        """
        Assemble final response from all workflow results
        """
        try:
            logger.info("Assembling final response")
            
            agent_responses = state.get("agent_responses", [])
            conflict_resolution = state.get("conflict_resolution")
            error_message = state.get("error_message")
            
            if error_message:
                final_content = f"I apologize, but I encountered an error: {error_message}"
                sources = []
            elif conflict_resolution and conflict_resolution.get("final_answer"):
                final_content = conflict_resolution["final_answer"]
                sources = self._extract_sources_from_resolution(conflict_resolution)
            elif len(agent_responses) == 1:
                response = agent_responses[0]
                final_content = response.get("content", "No response generated")
                sources = response.get("sources", [])
            elif len(agent_responses) > 1:
                final_content = self._combine_responses(agent_responses)
                sources = self._extract_all_sources(agent_responses)
            else:
                final_content = "I'm sorry, I couldn't generate a response to your query."
                sources = []
            
            execution_metadata = state.get("execution_metadata", {})
            debug_trace = state.get("debug_trace", [])
            
            metadata_summary = {
                "agents_used": [resp.get("agent_name") for resp in agent_responses if resp.get("agent_name")],
                "tools_used": list(set(
                    tool for resp in agent_responses 
                    for tool in resp.get("tools_used", [])
                )),
                "total_execution_time": sum(
                    resp.get("execution_time", 0) for resp in agent_responses
                ),
                "workflow_steps": len(debug_trace),
                "sources_count": len(sources)
            }
            
            return {
                "final_response": final_content,
                "final_sources": sources,
                "processing_status": "completed",
                "execution_metadata": {**execution_metadata, **metadata_summary},
                "debug_trace": [f"final_response: assembled complete response with {len(sources)} sources"]
            }
            
        except Exception as e:
            logger.error(f"Final response assembly failed: {e}")
            return {
                "final_response": f"I apologize, but I encountered an error while preparing the response: {str(e)}",
                "final_sources": [],
                "processing_status": "failed",
                "error_message": str(e)
            }
    
    def _extract_sources_from_resolution(self, conflict_resolution: Dict) -> list:
        """Extract sources from conflict resolution"""
        sources = []
        evidence_ranking = conflict_resolution.get("evidence_ranking", [])
        for evidence in evidence_ranking:
            if "sources" in evidence:
                sources.extend(evidence["sources"])
        return list(set(sources))
    
    def _extract_all_sources(self, agent_responses: list) -> list:
        """Extract all sources from agent responses"""
        all_sources = []
        for response in agent_responses:
            sources = response.get("sources", [])
            all_sources.extend(sources)
        return list(set(all_sources))
    
    def _combine_responses(self, agent_responses: list) -> str:
        """Combine multiple agent responses when no conflict resolution occurred"""
        combined = "Based on analysis from multiple agents:\n\n"
        
        for i, response in enumerate(agent_responses, 1):
            agent_name = response.get("agent_name", f"Agent {i}")
            content = response.get("content", "No response")
            combined += f"**{agent_name}**: {content}\n\n"
        
        return combined.strip()


class ErrorHandlerNode:
    """
    Error handling node for workflow failures
    """
    
    def __init__(self):
        self.node_name = "error_handler"
    
    def __call__(self, state: RAGState, config: RunnableConfig) -> Dict[str, Any]:
        """
        Handle workflow errors gracefully
        """
        try:
            error_message = state.get("error_message", "Unknown error occurred")
            retry_count = state.get("retry_count", 0)
            
            logger.error(f"Workflow error (attempt {retry_count + 1}): {error_message}")
            
            return {
                "retry_count": retry_count + 1,
                "processing_status": "failed",
                "final_response": f"I apologize, but I encountered an error while processing your request: {error_message}",
                "debug_trace": [f"error_handler: handled error after {retry_count + 1} attempts"]
            }
            
        except Exception as e:
            logger.error(f"Error handler failed: {e}")
            return {
                "processing_status": "failed",
                "final_response": "I apologize, but I encountered a critical error while processing your request.",
                "error_message": str(e)
            }


class MultiAgentRAGWorkflow:
    """
    Complete Multi-Agent RAG Workflow implementation using LangGraph
    """
    
    def __init__(self, enable_checkpointing: bool = True):
        self.enable_checkpointing = enable_checkpointing
        self._graph = None
        self._compiled_graph = None
        self._initialized = False
        
        self.nodes = {
            "orchestrator": OrchestratorNode(),
            "reflection_semantic_router": ReflectionSemanticRouterNode(),
            "agent_execution": AgentExecutionNode(),
            "conflict_resolution": ConflictResolutionNode(),
            "final_response": FinalResponseNode(),
            "error_handler": ErrorHandlerNode()
        }
        
        self.routers = {
            "orchestrator_router": create_orchestrator_router(),
            "reflection_router": create_reflection_router(),
            "agent_execution_router": create_agent_execution_router(),
            "conflict_resolution_router": create_conflict_resolution_router(),
            "error_router": create_error_router()
        }
    
    def build_graph(self) -> StateGraph:
        """
        Build the LangGraph workflow
        """
        try:
            builder = StateGraph(RAGState)
            
            for node_name, node_instance in self.nodes.items():
                builder.add_node(node_name, node_instance)
                logger.debug(f"Added node: {node_name}")
            
            builder.add_edge(START, "orchestrator")
            
            builder.add_conditional_edges(
                "orchestrator",
                self.routers["orchestrator_router"],
                {
                    "reflection_router": "reflection_semantic_router",
                    "agent_execution": "agent_execution", 
                    "error": "error_handler"
                }
            )
            
            builder.add_conditional_edges(
                "reflection_semantic_router",
                self.routers["reflection_router"],
                {
                    "agent_execution": "agent_execution",
                    "error": "error_handler"
                }
            )
            
            builder.add_conditional_edges(
                "agent_execution",
                self.routers["agent_execution_router"],
                {
                    "conflict_resolution": "conflict_resolution",
                    "final_response": "final_response",
                    "error": "error_handler"
                }
            )
            
            builder.add_conditional_edges(
                "conflict_resolution", 
                self.routers["conflict_resolution_router"],
                {
                    "final_response": "final_response",
                    "error": "error_handler"
                }
            )
            
            # Add edges to END
            builder.add_edge("final_response", END)
            builder.add_edge("error_handler", END)
            
            self._graph = builder
            logger.info("Multi-Agent RAG workflow graph built successfully")
            return builder
            
        except Exception as e:
            logger.error(f"Failed to build workflow graph: {e}")
            raise
    
    def compile(self) -> Any:
        """
        Compile the workflow graph
        """
        try:
            if not self._graph:
                self.build_graph()
            
            # Add checkpointer if enabled
            compile_kwargs = {}
            if self.enable_checkpointing:
                memory = MemorySaver()
                compile_kwargs["checkpointer"] = memory
                logger.info("Enabled workflow checkpointing with MemorySaver")
            
            self._compiled_graph = self._graph.compile(**compile_kwargs)
            self._initialized = True
            
            logger.info("Multi-Agent RAG workflow compiled successfully")
            return self._compiled_graph
            
        except Exception as e:
            logger.error(f"Failed to compile workflow: {e}")
            raise
    
    async def invoke(self, input_data: Dict[str, Any], config: Optional[RunnableConfig] = None) -> Dict[str, Any]:
        """
        Execute the workflow with input data
        """
        try:
            if not self._initialized:
                self.compile()
            
            logger.info(f"Executing Multi-Agent RAG workflow for query: {input_data.get('query', '')[:50]}...")
            
            result = await self._compiled_graph.ainvoke(input_data, config)
            
            logger.info("Multi-Agent RAG workflow completed successfully")
            return result
            
        except Exception as e:
            logger.error(f"Workflow execution failed: {e}")
            raise
    
    async def stream(self, input_data: Dict[str, Any], config: Optional[RunnableConfig] = None):
        """
        Stream workflow execution for real-time updates
        """
        try:
            if not self._initialized:
                self.compile()
            
            logger.info(f"Streaming Multi-Agent RAG workflow for query: {input_data.get('query', '')[:50]}...")
            
            async for chunk in self._compiled_graph.astream(input_data, config):
                yield chunk
                
        except Exception as e:
            logger.error(f"Workflow streaming failed: {e}")
            raise
    
    async def health_check(self) -> bool:
        """
        Check if workflow is properly initialized and ready
        """
        try:
            if not self._initialized:
                return False
            
            # Test with minimal input
            test_input = {
                "query": "test",
                "messages": [],
                "user_context": {
                    "user_id": "test",
                    "session_id": "test",
                    "department": "general",
                    "role": "user"
                },
                "current_step": "orchestrator",
                "next_action": "agent_execution",
                "processing_status": "pending"
            }
            
            # Just check if graph can be invoked without errors
            result = await self._compiled_graph.ainvoke(test_input)
            return result is not None
            
        except Exception as e:
            logger.error(f"Workflow health check failed: {e}")
            return False
    
    def get_graph_visualization(self) -> Optional[str]:
        """
        Get Mermaid diagram representation of the workflow
        """
        try:
            if not self._compiled_graph:
                return None
            
            mermaid = """
graph TD
    START([START]) --> orchestrator[Orchestrator]
    orchestrator --> |needs_reflection| reflection_semantic_router[Reflection + Semantic Router]
    orchestrator --> |direct_execution| agent_execution[Agent Execution]
    reflection_semantic_router --> agent_execution
    agent_execution --> |single_response| final_response[Final Response]
    agent_execution --> |multiple_responses| conflict_resolution[Conflict Resolution]
    conflict_resolution --> final_response
    final_response --> END([END])
    orchestrator --> |error| error_handler[Error Handler]
    reflection_semantic_router --> |error| error_handler
    agent_execution --> |error| error_handler
    conflict_resolution --> |error| error_handler
    error_handler --> END
"""
            return mermaid
            
        except Exception as e:
            logger.error(f"Failed to generate graph visualization: {e}")
            return None
    
    async def get_workflow_status(self) -> Dict[str, Any]:
        """
        Get comprehensive workflow status and configuration
        """
        return {
            "initialized": self._initialized,
            "checkpointing_enabled": self.enable_checkpointing,
            "nodes_count": len(self.nodes),
            "nodes": list(self.nodes.keys()),
            "routers_count": len(self.routers),
            "routers": list(self.routers.keys()),
            "graph_compiled": self._compiled_graph is not None,
            "health_status": await self.health_check() if self._initialized else False
        }


multi_agent_rag_workflow = MultiAgentRAGWorkflow(enable_checkpointing=True)

async def create_rag_workflow(enable_checkpointing: bool = True) -> MultiAgentRAGWorkflow:
    """
    Create and initialize a new RAG workflow instance
    """
    workflow = MultiAgentRAGWorkflow(enable_checkpointing=enable_checkpointing)
    workflow.compile()
    return workflow


async def execute_rag_query(
    query: str,
    user_context: Dict[str, Any],
    messages: list = None,
    config: Optional[RunnableConfig] = None
) -> Dict[str, Any]:
    """
    Execute a RAG query using the global workflow instance
    """
    if not multi_agent_rag_workflow._initialized:
        multi_agent_rag_workflow.compile()
    
    input_data = {
        "query": query,
        "messages": messages or [],
        "user_context": user_context,
        "current_step": "orchestrator",
        "next_action": "orchestrator",
        "processing_status": "pending"
    }
    
    return await multi_agent_rag_workflow.invoke(input_data, config)


__all__ = [
    "MultiAgentRAGWorkflow",
    "multi_agent_rag_workflow", 
    "create_rag_workflow",
    "execute_rag_query",
    "RAGState"
]