"""
Updated Multi-Agent RAG Workflow with streaming and planning execution
"""
import asyncio
import concurrent.futures
from typing import Dict, Any, Optional, List, AsyncGenerator
from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from utils.logging import get_logger
from utils.language_utils import get_workflow_message

from .state.state import RAGState
from .nodes.nodes import (
    OrchestratorNode,
    ErrorHandlerNode
)
from .nodes.semantic_reflection_node import SemanticReflectionNode
from .nodes.execute_planning_node import ExecutePlanningNode
from .nodes.conflict_resolution_node import ConflictResolutionNode
from .nodes.final_response_node import FinalResponseNode
from .edges.edges import (
    create_orchestrator_router,
    create_semantic_reflection_router,
    create_execute_planning_router,
    create_conflict_resolution_router,
    create_error_router
)

logger = get_logger(__name__)


def create_sync_wrapper(async_node):
    """Create a sync wrapper for async node functions with proper event loop handling"""
    def sync_wrapper(state, config):
        try:
            try:
                running_loop = asyncio.get_running_loop()
                future = asyncio.run_coroutine_threadsafe(async_node(state, config), running_loop)
                result = future.result()
                return result
            except RuntimeError as loop_error:
                logger.debug(f"No running event loop ({loop_error}), using isolated execution")

                def run_in_isolation():
                    """Run async function in completely isolated context"""
                    isolated_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(isolated_loop)
                    try:
                        result = isolated_loop.run_until_complete(async_node(state, config))
                        return result
                    finally:
                        try:
                            pending = asyncio.all_tasks(isolated_loop)
                            for task in pending:
                                if not task.done():
                                    task.cancel()
                            if pending:
                                isolated_loop.run_until_complete(
                                    asyncio.gather(*pending, return_exceptions=True)
                                )
                            isolated_loop.run_until_complete(isolated_loop.shutdown_asyncgens())
                        except Exception:
                            pass
                        isolated_loop.close()

                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(run_in_isolation)
                    timeout_seconds = getattr(async_node, '_timeout', None) or 120
                    try:
                        result = future.result(timeout=timeout_seconds)
                        return result
                    except concurrent.futures.TimeoutError:
                        logger.error(f"Node execution timed out after {timeout_seconds} seconds")
                        future.cancel()
                        raise TimeoutError(f"Node execution timed out after {timeout_seconds} seconds")

        except asyncio.TimeoutError as timeout_error:
            logger.error(f"Node execution timed out after {timeout_seconds} seconds: {timeout_error}")
            error_msg = f"Node execution timed out after {timeout_seconds} seconds"
            error_state = {
                "error_message": error_msg,
                "original_error": str(timeout_error),
                "exception_type": "TimeoutError",
                "processing_status": "failed",
                "should_yield": True,
                "next_action": "error",
                "timeout_seconds": timeout_seconds
            }
            logger.error(f"Timeout error state: {error_msg}")
            return error_state

        except RuntimeError as runtime_error:
            if "no running event loop" in str(runtime_error):
                logger.warning(f"Event loop issue detected: {runtime_error}")
                error_msg = "Event loop error: Unable to execute node due to async context issue"
                error_state = {
                    "error_message": error_msg,
                    "original_error": str(runtime_error),
                    "exception_type": "RuntimeError",
                    "processing_status": "failed",
                    "should_yield": True,
                    "next_action": "error"
                }
                logger.error(f"Event loop error state: {error_msg}")
                return error_state
            else:
                raise

        except Exception as e:
            logger.error(f"Node execution failed: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")

            error_msg = str(e) if str(e) else f"Unknown error: {type(e).__name__}"
            original_err = str(e) if str(e) else f"{type(e).__name__}: {repr(e)}"

            error_state = {
                "error_message": error_msg,
                "original_error": original_err,
                "exception_type": type(e).__name__,
                "processing_status": "failed",
                "should_yield": True,
                "next_action": "error"
            }

            logger.error(f"Node execution failed, returning error state: error_message='{error_msg[:100]}...', exception_type={type(e).__name__}")
            return error_state


    return sync_wrapper


class MultiAgentRAGWorkflow:
    """
    Complete Multi-Agent RAG Workflow with streaming support
    """

    def __init__(self, enable_checkpointing: bool = True):
        self.enable_checkpointing = enable_checkpointing
        self._graph = None
        self._compiled_graph = None
        self._initialized = False

        self.nodes = {
            "orchestrator": create_sync_wrapper(OrchestratorNode()),
            "semantic_reflection": create_sync_wrapper(SemanticReflectionNode()),
            "execute_planning": create_sync_wrapper(ExecutePlanningNode()),
            "conflict_resolution": create_sync_wrapper(ConflictResolutionNode()),
            "final_response": create_sync_wrapper(FinalResponseNode()),
            "error_handler": create_sync_wrapper(ErrorHandlerNode())
        }
        
        self.routers = {
            "orchestrator_router": create_orchestrator_router(),
            "semantic_reflection_router": create_semantic_reflection_router(),
            "execute_planning_router": create_execute_planning_router(),
            "conflict_resolution_router": create_conflict_resolution_router(),
            "error_router": create_error_router()
        }
    
    def build_graph(self) -> StateGraph:
        """
        Build the LangGraph workflow with updated routing
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
                    "semantic_reflection": "semantic_reflection",
                    "execute_planning": "execute_planning",
                    "error": "error_handler"
                }
            )
            
            builder.add_conditional_edges(
                "semantic_reflection",
                self.routers["semantic_reflection_router"],
                {
                    "execute_planning": "execute_planning",
                    "final_response": "final_response",
                    "error": "error_handler"
                }
            )
            
            builder.add_conditional_edges(
                "execute_planning",
                self.routers["execute_planning_router"],
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
            
            builder.add_conditional_edges(
                "error_handler",
                self.routers["error_router"],
                {
                    "final_response": "final_response"
                }
            )
            
            builder.add_edge("final_response", END)
            
            self._graph = builder
            return builder
            
        except Exception as e:
            logger.error(f"Failed to build workflow graph: {e}")
            raise
    
    def compile(self) -> None:
        """
        Compile the workflow graph
        """
        try:
            if not self._graph:
                self.build_graph()
            
            checkpointer = MemorySaver() if self.enable_checkpointing else None
            
            self._compiled_graph = self._graph.compile(checkpointer=checkpointer)
            self._initialized = True
            
            logger.info("Workflow compiled successfully")
            
        except Exception as e:
            logger.error(f"Failed to compile workflow: {e}")
            raise
    
    async def invoke(self, input_data: Dict[str, Any], config: Optional[RunnableConfig] = None) -> Dict[str, Any]:
        """
        Execute workflow without streaming
        """
        if not self._initialized:
            self.compile()

        try:
            result = await self._compiled_graph.ainvoke(input_data, config=config)
            return result

        except Exception as e:
            logger.error(f"Workflow execution failed: {e}")
            raise
    
    async def stream(self, input_data: Dict[str, Any], config: Optional[RunnableConfig] = None) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Execute workflow with streaming - yields progress updates
        """
        if not self._initialized:
            self.compile()

        from asyncio import Queue
        progress_queue = Queue()

        try:
            logger.info("Starting workflow streaming...")
            async for chunk in self._compiled_graph.astream(input_data, config=config):
                logger.debug(f"Received chunk from astream: {list(chunk.keys())}")
                for node_name, node_output in chunk.items():
                    logger.debug(f"Processing node {node_name}, output type: {type(node_output)}")
                    if isinstance(node_output, dict):
                        should_yield = node_output.get("should_yield")
                        logger.debug(f"Node {node_name} should_yield: {should_yield} (type: {type(should_yield)})")
                        if should_yield:
                            logger.info(f"Yielding event for node {node_name}: {node_output.get('processing_status', 'unknown')}")
                            yield {
                            "type": "node",
                            "node": node_name,
                            "output": node_output,
                            "progress": node_output.get("progress_percentage", 0),
                            "status": node_output.get("processing_status", "processing"),
                            "message": node_output.get("progress_message", "")
                        }

                    elif hasattr(node_output, '__aiter__'):
                        async for progress_item in node_output:
                            if isinstance(progress_item, dict) and progress_item.get("should_yield"):
                                yield {
                                    "type": "node",
                                    "node": node_name,
                                    "output": progress_item,
                                    "progress": progress_item.get("progress_percentage", 0),
                                    "status": progress_item.get("processing_status", "processing"),
                                    "message": progress_item.get("progress_message", "")
                                }

            while not progress_queue.empty():
                progress_data = await progress_queue.get()
                yield progress_data
            
        except Exception as e:
            logger.error(f"Workflow streaming failed: {e}")

            yield {
                "node": "error",
                "output": {"error_message": str(e)},
                "progress": 0,
                "status": "failed",
                "message": get_workflow_message("workflow_failed", "english", error=str(e))
            }
    
    async def health_check(self) -> bool:
        """
        Check if workflow is healthy and ready
        """
        try:
            return self._initialized and self._compiled_graph is not None
        except Exception:
            return False


multi_agent_rag_workflow = MultiAgentRAGWorkflow(enable_checkpointing=False)


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
    config: Optional[RunnableConfig] = None,
    bot_name: str = "AI Assistant",
    organization_name: str = "Organization"
) -> Dict[str, Any]:
    """
    Execute a RAG query using the global workflow instance
    """
    if not multi_agent_rag_workflow._initialized:
        multi_agent_rag_workflow.compile()

    provider = None
    agents_structure = None  
    tenant_bot_name = bot_name
    tenant_org_name = organization_name

    if user_context.get("tenant_id"):
        try:
            from services.orchestrator.provider_helper import get_provider_for_tenant
            from services.agents.agent_service import AgentService
            from services.tenant.tenant_service import TenantService
            from config.database import get_db_session

            async with get_db_session() as db:
                provider = await get_provider_for_tenant(user_context["tenant_id"], db)

                if provider:
                    agent_service = AgentService(db)
                    agents_structure = await agent_service.get_agents_structure_for_user(user_context)
                else:
                    logger.warning(f"No provider available for tenant {user_context['tenant_id']}")
                    agents_structure = None  
                tenant_service = TenantService(db)
                tenant_info = await tenant_service.get_bot_and_org_info(user_context["tenant_id"])
                tenant_bot_name = tenant_info["bot_name"]
                tenant_org_name = tenant_info["organization_name"]

        except Exception as e:
            logger.warning(f"Failed to initialize provider/agents/tenant info: {e}")
            provider = None
            agents_structure = None

    input_data = {
        "query": query,
        "messages": messages or [],
        "user_context": user_context,
        "bot_name": tenant_bot_name,
        "organization_name": tenant_org_name,
        "user_id": user_context.get("user_id"),
        "tenant_id": user_context.get("tenant_id"),
        "department_id": user_context.get("department_id"),
        "access_scope": user_context.get("access_scope"),
        "provider": provider,
        "agents_structure": agents_structure,
        "current_step": "orchestrator",
        "next_action": "semantic_reflection",
        "processing_status": "pending",
    }

    return await multi_agent_rag_workflow.invoke(input_data, config)


async def stream_rag_query(
    query: str,
    user_context: Dict[str, Any],
    messages: List[Dict[str, Any]] = None,
    config: Optional[RunnableConfig] = None,
    bot_name: str = "AI Assistant",
    organization_name: str = "Organization",
    tenant_description: str = "",
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Execute a RAG query with streaming using the global workflow instance
    """
    if not multi_agent_rag_workflow._initialized:
        multi_agent_rag_workflow.compile()

    provider = None
    agents_structure = None
    tenant_bot_name = bot_name
    tenant_org_name = organization_name
    tenant_desc = tenant_description

    if user_context.get("tenant_id"):
        try:
            from services.orchestrator.provider_helper import get_provider_for_tenant
            from services.agents.agent_service import AgentService
            from services.tenant.tenant_service import TenantService
            from config.database import get_db_session

            async with get_db_session() as db:
                provider = await get_provider_for_tenant(user_context["tenant_id"], db)

                if provider:
                    agent_service = AgentService(db)
                    agents_structure = await agent_service.get_agents_structure_for_user(user_context)
                else:
                    logger.warning(f"No provider available for tenant {user_context['tenant_id']}")
                    agents_structure = None
                    
                tenant_service = TenantService(db)
                tenant_info = await tenant_service.get_bot_and_org_info(user_context["tenant_id"])
                tenant_bot_name = tenant_info["bot_name"]
                tenant_org_name = tenant_info["organization_name"]
                tenant_desc = tenant_info["description"]

        except Exception as e:
            logger.warning(f"Failed to initialize provider/agents/tenant info: {e}")
            provider = None
            agents_structure = None 

    langchain_messages = []
    if messages:
        from langchain_core.messages import HumanMessage, AIMessage
        for msg in messages:
            if msg.get("type") == "human":
                langchain_messages.append(HumanMessage(content=msg["content"]))
            elif msg.get("type") == "assistant":
                langchain_messages.append(AIMessage(content=msg["content"]))

    detected_language = user_context.get("detected_language")
    if not detected_language:
        from utils.language_utils import detect_language
        detected_language = detect_language(query)
    
    input_data = {
        "query": query,
        "messages": langchain_messages,
        "user_context": user_context,
        "bot_name": tenant_bot_name,
        "organization_name": tenant_org_name,
        "tenant_description": tenant_desc,
        "user_id": user_context.get("user_id"),
        "tenant_id": user_context.get("tenant_id"),
        "department_id": user_context.get("department_id"),
        "access_scope": user_context.get("access_scope"),
        "provider": provider,
        "agents_structure": agents_structure,
        "detected_language": detected_language,
        "current_step": "orchestrator",
        "next_action": "semantic_reflection",
        "processing_status": "pending",
        "progress_percentage": 0,
        "progress_message": "Initializing workflow...",
    }

    async for result in multi_agent_rag_workflow.stream(input_data, config):
        yield result


__all__ = [
    "MultiAgentRAGWorkflow",
    "multi_agent_rag_workflow",
    "create_rag_workflow",
    "execute_rag_query",
    "stream_rag_query",
    "RAGState"
]