"""Updated Multi-Agent RAG Workflow with streaming and planning execution."""

from __future__ import annotations

import asyncio
from typing import Dict, Any, Optional, List, AsyncGenerator
from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph, START, END
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
from .nodes.progress_tracker_node import ProgressTrackerNode
from .edges.edges import (
    create_orchestrator_router,
    create_semantic_reflection_router,
    create_execute_planning_router,
    create_conflict_resolution_router,
    create_error_router
)
from utils.datetime_utils import DateTimeManager

logger = get_logger(__name__)


class MultiAgentRAGWorkflow:
    """
    Complete Multi-Agent RAG Workflow with streaming support
    """
    def __init__(self, enable_checkpointing: bool = True):
        self.enable_checkpointing = enable_checkpointing
        self._graph = None
        self._compiled_graph = None
        self._initialized = False
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._compile_lock: Optional[asyncio.Lock] = None
        self.nodes = {
            "orchestrator": OrchestratorNode(),
            "semantic_reflection": SemanticReflectionNode(),
            "execute_planning": ExecutePlanningNode(),
            "conflict_resolution": ConflictResolutionNode(),
            "final_response": FinalResponseNode(),
            "error_handler": ErrorHandlerNode(),
        }
        
        self.routers = {
            "orchestrator_router": create_orchestrator_router(),
            "semantic_reflection_router": create_semantic_reflection_router(),
            "execute_planning_router": create_execute_planning_router(),
            "conflict_resolution_router": create_conflict_resolution_router(),
            "error_router": create_error_router()
        }
    
    def _reset(self) -> None:
        """Reset compiled graph state so it can be rebuilt on the current loop."""
        self._graph = None
        self._compiled_graph = None
        self._initialized = False
        self._loop = None
        self._compile_lock = None

    def _get_current_loop(self) -> asyncio.AbstractEventLoop:
        try:
            return asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.get_event_loop()

    async def _ensure_runtime(self) -> None:
        """Ensure the workflow is compiled for the active event loop."""
        current_loop = self._get_current_loop()

        if self._compile_lock is None or (self._loop is not None and current_loop is not self._loop):
            self._compile_lock = asyncio.Lock()

        async with self._compile_lock:
            if self._loop is not None and current_loop is not self._loop:
                logger.warning("Workflow event loop changed; rebuilding graph for new loop")
                self._reset()

            if not self._initialized:
                self._loop = current_loop
                self.compile()

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
        Compile the workflow graph with enhanced checkpointing
        """
        try:
            if not self._graph:
                self.build_graph()
            
            if self.enable_checkpointing:
                try:
                    from langgraph.checkpoint.memory import MemorySaver
                    checkpointer = MemorySaver()
                    logger.info("Using MemorySaver for LangGraph checkpointing - workflow state will be persisted")
                except ImportError:
                    logger.warning("MemorySaver not available, disabling checkpointing")
                    checkpointer = None
            else:
                checkpointer = None
                logger.info("LangGraph checkpointing disabled")
            
            compile_config = {}
            if checkpointer:
                compile_config["checkpointer"] = checkpointer
                compile_config["interrupt_before"] = []  
                compile_config["interrupt_after"] = []  
            
            self._compiled_graph = self._graph.compile(**compile_config)
            self._initialized = True
            
            logger.info(f"Workflow compiled successfully with checkpointing={self.enable_checkpointing}")
            
        except Exception as e:
            logger.error(f"Failed to compile workflow: {e}")
            raise
    
    async def invoke(self, input_data: Dict[str, Any], config: Optional[RunnableConfig] = None) -> Dict[str, Any]:
        """
        Execute workflow without streaming
        """
        await self._ensure_runtime()
        try:
            result = await self._compiled_graph.ainvoke(input_data, config=config)
            return result
        except Exception as e:
            logger.error(f"Workflow execution failed: {e}")
            raise

    async def stream(self, input_data: Dict[str, Any], config: Optional[RunnableConfig] = None) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Execute workflow with streaming - yields progress updates immediately
        """
        await self._ensure_runtime()
        try:
            logger.info("Starting workflow streaming with immediate yields and checkpointing...")
            emitted_runs = set()
            
            stream_config = config or {}
            if self.enable_checkpointing:
                session_id = input_data.get("session_id") or input_data.get("user_context", {}).get("session_id")
                thread_id = f"workflow_{session_id}" if session_id else "default_workflow_thread"
                stream_config = {
                    **stream_config,
                    "configurable": {
                        **stream_config.get("configurable", {}),
                        "thread_id": thread_id
                    }
                }
                logger.info(f"Using thread_id for checkpointing: {thread_id}")

            async for event in self._compiled_graph.astream_events(input_data, config=stream_config, version="v1"):
                event_type = event.get("event")
                if event_type not in {"on_chain_stream", "on_chain_end"}:
                    continue

                metadata = event.get("metadata") or {}
                node_name = metadata.get("langgraph_node") or event.get("name")

                if not node_name or node_name in {"LangGraph", START, END}:
                    continue

                data = event.get("data") or {}
                if event_type == "on_chain_stream":
                    output = data.get("chunk")
                else:
                    if event.get("run_id") in emitted_runs:
                        continue
                    output = data.get("output")

                if not isinstance(output, dict) or not output.get("should_yield"):
                    continue

                emitted_runs.add(event.get("run_id"))
                
                if output.get("task_status_update"):
                    logger.info(f"WORKFLOW_GRAPH: Streaming task status update from node {node_name}: {output.get('task_status_update')}")

                result = {
                    "type": "node",
                    "node": node_name,
                    "output": {
                        **output,
                        "execution_metadata": {
                            "node_executed": node_name,
                            "timestamp": asyncio.get_event_loop().time(),
                            "checkpointing_enabled": self.enable_checkpointing
                        }
                    },
                    "progress": output.get("progress_percentage", 0),
                    "status": output.get("processing_status", "running"),
                    "message": output.get("progress_message"),
                }
                
                yield result
                await asyncio.sleep(0)

        except Exception as e:
            logger.error(f"Workflow streaming failed: {e}")
            yield {
                "type": "node",
                "node": "error",
                "output": {
                    "error_message": str(e),
                    "processing_status": "failed",
                    "progress_percentage": 0,
                    "progress_message": get_workflow_message(
                        "workflow_failed", "english", error=str(e)
                    ),
                    "should_yield": True,
                },
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
    config: Optional[RunnableConfig] = None,
    bot_name: str = "AI Assistant",
    organization_name: str = "Organization"
) -> Dict[str, Any]:
    """
    Execute a RAG query using the global workflow instance
    """
    if not multi_agent_rag_workflow._initialized:
        multi_agent_rag_workflow.compile()

    provider_name = None
    agents_structure = None
    tenant_bot_name = bot_name
    tenant_org_name = organization_name
    tenant_timezone = getattr(DateTimeManager.system_tz, "key", str(DateTimeManager.system_tz))
    tenant_current_datetime = DateTimeManager.system_now().isoformat()

    if user_context.get("tenant_id"):
        try:
            from services.tenant.tenant_service import TenantService
            from services.agents.workflow_agent_service import WorkflowAgentService
            from config.database import get_db_context

            async with get_db_context() as db:
                try:
                    provider_config = await WorkflowAgentService(db).get_workflow_agent_config(user_context["tenant_id"])
                    logger.info(f"Provider config for tenant {user_context['tenant_id']}: {provider_config}")
                    if provider_config:
                        provider_name = provider_config["provider_name"]
                except Exception as e:
                    logger.error(f"Failed to get provider config for tenant {user_context['tenant_id']}: {e}")
                    provider_name = None
                    agents_structure = None  

                tenant_service = TenantService(db)
                tenant_info = await tenant_service.get_bot_and_org_info(user_context["tenant_id"])
                tenant_bot_name = tenant_info["bot_name"]
                tenant_org_name = tenant_info["organization_name"]

                tenant_timezone = await DateTimeManager.get_tenant_timezone(user_context["tenant_id"], db)
                tenant_now = await DateTimeManager.tenant_now_cached(user_context["tenant_id"], db)
                tenant_current_datetime = tenant_now.isoformat()
                user_context.setdefault("timezone", tenant_timezone)
                user_context.setdefault("tenant_current_datetime", tenant_current_datetime)

        except Exception as e:
            logger.warning(f"Failed to initialize provider/agents/tenant info: {e}")
            agents_structure = None

    input_data = {
        "query": query,
        "messages": messages or [],
        "user_context": user_context,
        "tenant_timezone": tenant_timezone,
        "tenant_current_datetime": tenant_current_datetime,
        "bot_name": tenant_bot_name,
        "organization_name": tenant_org_name,
        "provider_name": provider_name,
        "user_id": user_context.get("user_id"),
        "tenant_id": user_context.get("tenant_id"),
        "department_id": user_context.get("department_id"),
        "access_scope": user_context.get("access_scope"),
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
    access_level: str = "public"
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Execute a RAG query with streaming using the global workflow instance
    """
    if not multi_agent_rag_workflow._initialized:
        multi_agent_rag_workflow.compile()

    provider_name = None
    agents_structure = None
    tenant_bot_name = bot_name
    tenant_org_name = organization_name
    tenant_desc = tenant_description
    tenant_timezone = None
    tenant_current_datetime = None

    if user_context.get("tenant_id"):
        try:
            from services.tenant.tenant_service import TenantService
            from services.agents.workflow_agent_service import WorkflowAgentService
            from config.database import get_db_context

            async with get_db_context() as db:
                try:
                    provider_config = await WorkflowAgentService(db).get_workflow_agent_config(user_context["tenant_id"])
                    logger.info(f"Stream provider config for tenant {user_context['tenant_id']}: {provider_config}")
                    if provider_config:
                        provider_name = provider_config["provider_name"]
                    else:
                        logger.warning(f"Stream no provider config returned for tenant {user_context['tenant_id']}")
                        provider_name = None
                except Exception as e:
                    logger.error(f"Stream failed to get provider config for tenant {user_context['tenant_id']}: {e}")
                    provider_name = None
                    agents_structure = None

                tenant_service = TenantService(db)
                tenant_info = await tenant_service.get_bot_and_org_info(user_context["tenant_id"])
                tenant_bot_name = tenant_info["bot_name"]
                tenant_org_name = tenant_info["organization_name"]
                tenant_desc = tenant_info["description"]

                tenant_timezone = await DateTimeManager.get_tenant_timezone(user_context["tenant_id"], db)
                tenant_now = await DateTimeManager.tenant_now_cached(user_context["tenant_id"], db)
                tenant_current_datetime = tenant_now.isoformat()
                user_context.setdefault("timezone", tenant_timezone)

        except Exception as e:
            logger.warning(f"Failed to initialize provider/agents/tenant info: {e}")
            agents_structure = None 

    if not tenant_timezone:
        tenant_timezone = getattr(DateTimeManager.system_tz, "key", str(DateTimeManager.system_tz))

    if not tenant_current_datetime:
        tenant_current_datetime = DateTimeManager.system_now().isoformat()

    user_context.setdefault("timezone", tenant_timezone)
    user_context.setdefault("tenant_current_datetime", tenant_current_datetime)

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
        "tenant_timezone": tenant_timezone,
        "tenant_current_datetime": tenant_current_datetime,
        "bot_name": tenant_bot_name,
        "organization_name": tenant_org_name,
        "tenant_description": tenant_desc,
        "user_id": user_context.get("user_id"),
        "tenant_id": user_context.get("tenant_id"),
        "department_id": user_context.get("department_id"),
        "access_scope": access_level,
        "provider_name": provider_name,
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
    "RAGState",
]
