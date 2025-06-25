from typing import Dict, Any, List, Optional, Literal, Annotated
from typing_extensions import TypedDict
from datetime import datetime
import asyncio

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages  
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.redis import RedisSaver

from config.settings import get_settings
from services.config.config_manager import config_manager, ConfigSubscriber, ConfigChange, ConfigChangeType
from services.llm.provider_manager import llm_provider_manager
from services.tools.tool_service import ToolService
from services.orchestrator.agent_orchestrator import AgentOrchestrator
from utils.logging import get_logger

logger = get_logger(__name__)

class RAGState(TypedDict):
    """RAG workflow state schema"""
    
    # Messages - Core LangGraph pattern
    messages: Annotated[List[BaseMessage], add_messages]
    
    # Query processing
    original_query: str
    processed_query: str
    language: str
    
    # User context
    user_id: Optional[str]
    session_id: str
    conversation_history: List[Dict[str, Any]]
    
    # Agent orchestration
    selected_agents: List[str]
    agent_outputs: Dict[str, Dict[str, Any]]
    orchestrator_reasoning: str
    complexity_score: float
    
    # Tool execution
    tool_calls: List[Dict[str, Any]]
    tool_outputs: List[Dict[str, Any]]
    
    # Document retrieval
    retrieved_documents: List[Dict[str, Any]]
    document_sources: List[str]
    
    # Response generation
    draft_response: str
    final_response: str
    confidence_score: float
    
    # Quality control
    quality_checks: Dict[str, bool]
    content_safety: Dict[str, Any]
    
    # Metadata
    workflow_id: str
    processing_time: float
    iteration_count: int

class ConfigAwareRAGWorkflow(ConfigSubscriber):
    """
    Configuration-aware RAG Workflow
    Automatically reloads when admin changes settings
    """
    
    def __init__(self):
        self.settings = get_settings()
        self.tool_service = ToolService()
        self.orchestrator = AgentOrchestrator()
        self.graph = None
        self.checkpointer = None
        self._initialized = False
        self._rebuilding = False
        
    async def initialize(self):
        """Initialize workflow với config subscription"""
        try:
            await self._setup_checkpointer()
            await self._build_graph()
            
            # Subscribe to configuration changes
            config_manager.subscribe("workflow", self)
            
            self._initialized = True
            logger.info("Config-aware RAG Workflow initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize RAG Workflow: {e}")
            raise
    
    async def on_config_change(self, change: ConfigChange) -> bool:
        """
        Handle configuration changes from admin
        Automatically reload affected components
        """
        try:
            logger.info(f"Workflow received config change: {change.change_type} for {change.component_name}")
            
            # Prevent concurrent rebuilds
            if self._rebuilding:
                logger.info("Workflow rebuild already in progress, skipping")
                return True
            
            self._rebuilding = True
            
            # Reload settings first
            from config.settings import reload_settings
            self.settings = reload_settings()
            
            # Handle different types of changes
            if change.change_type in [
                ConfigChangeType.PROVIDER_ENABLED,
                ConfigChangeType.PROVIDER_DISABLED,
                ConfigChangeType.PROVIDER_CONFIG_CHANGED
            ]:
                await self._handle_provider_change(change)
                
            elif change.change_type in [
                ConfigChangeType.TOOL_ENABLED,
                ConfigChangeType.TOOL_DISABLED,
                ConfigChangeType.TOOL_CONFIG_CHANGED
            ]:
                await self._handle_tool_change(change)
                
            elif change.change_type in [
                ConfigChangeType.AGENT_ENABLED,
                ConfigChangeType.AGENT_DISABLED,
                ConfigChangeType.AGENT_CONFIG_CHANGED
            ]:
                await self._handle_agent_change(change)
                
            elif change.change_type == ConfigChangeType.WORKFLOW_CONFIG_CHANGED:
                await self._handle_workflow_change(change)
            
            # Rebuild workflow graph with new configuration
            await self._rebuild_workflow()
            
            self._rebuilding = False
            
            logger.info(f"Workflow successfully adapted to config change: {change.component_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to handle config change: {e}")
            self._rebuilding = False
            return False
    
    async def _handle_provider_change(self, change: ConfigChange):
        """Handle LLM provider configuration changes"""
        logger.info(f"Handling provider change: {change.component_name}")
        
        # Reinitialize LLM provider manager
        if llm_provider_manager._initialized:
            llm_provider_manager._initialized = False
            await llm_provider_manager.initialize()
    
    async def _handle_tool_change(self, change: ConfigChange):
        """Handle tool configuration changes"""
        logger.info(f"Handling tool change: {change.component_name}")
        
        # Reinitialize tool service
        if self.tool_service._initialized:
            self.tool_service._initialized = False
            await self.tool_service.initialize()
    
    async def _handle_agent_change(self, change: ConfigChange):
        """Handle agent configuration changes"""
        logger.info(f"Handling agent change: {change.component_name}")
        
        # Agent orchestrator doesn't need reinitialization
        # It reads from settings dynamically
        pass
    
    async def _handle_workflow_change(self, change: ConfigChange):
        """Handle workflow configuration changes"""
        logger.info("Handling workflow configuration change")
        
        # Workflow will be rebuilt with new settings
        # No additional actions needed
        pass
    
    async def _rebuild_workflow(self):
        """Rebuild workflow graph with updated configuration"""
        try:
            logger.info("Rebuilding workflow graph with updated configuration...")
            
            # Setup checkpointer if type changed
            await self._setup_checkpointer()
            
            # Rebuild graph
            await self._build_graph()
            
            logger.info("Workflow graph rebuilt successfully")
            
        except Exception as e:
            logger.error(f"Failed to rebuild workflow: {e}")
            raise
    
    async def _setup_checkpointer(self):
        """Setup checkpointer based on current configuration"""
        checkpointer_type = self.settings.workflow.checkpointer_type
        
        if checkpointer_type == "redis":
            try:
                import redis.asyncio as redis
                redis_client = redis.from_url(self.settings.cache.url)
                self.checkpointer = RedisSaver(redis_client)
                logger.info("Redis checkpointer configured")
            except Exception as e:
                logger.warning(f"Redis checkpointer failed: {e}, using memory")
                self.checkpointer = MemorySaver()
        else:
            self.checkpointer = MemorySaver()
    
    async def _build_graph(self):
        """Build LangGraph with current configuration"""
        builder = StateGraph(RAGState)
        
        # Add nodes based on current configuration
        builder.add_node("initialize", self._initialize_processing)
        builder.add_node("analyze_query", self._analyze_query)
        
        # Conditional nodes based on configuration
        if self.settings.orchestrator.get("enabled", True):
            builder.add_node("orchestrate_agents", self._orchestrate_agents)
        
        # Tools node if any tools are enabled
        if self.settings.get_enabled_tools():
            builder.add_node("execute_tools", self._execute_tools)
        
        builder.add_node("retrieve_documents", self._retrieve_documents)
        builder.add_node("generate_response", self._generate_response)
        
        # Quality control based on configuration
        if self.settings.workflow.enable_hallucination_check:
            builder.add_node("quality_check", self._quality_check)
        
        builder.add_node("finalize_response", self._finalize_response)
        
        # Build edges based on current configuration
        await self._build_workflow_edges(builder)
        
        # Set entry and exit points
        builder.set_entry_point("initialize")
        builder.set_finish_point("finalize_response")
        
        # Compile graph
        self.graph = builder.compile(
            checkpointer=self.checkpointer,
            debug=self.settings.DEBUG
        )
    
    async def _build_workflow_edges(self, builder):
        """Build workflow edges based on current configuration"""
        
        builder.add_edge(START, "initialize")
        builder.add_edge("initialize", "analyze_query")
        
        # Routing after analysis
        if self.settings.orchestrator.get("enabled", True):
            builder.add_conditional_edges(
                "analyze_query",
                self._route_after_analysis,
                {
                    "orchestrate": "orchestrate_agents",
                    "direct_tools": "execute_tools" if self.settings.get_enabled_tools() else "retrieve_documents",
                    "direct_retrieval": "retrieve_documents"
                }
            )
            builder.add_edge("orchestrate_agents", "execute_tools" if self.settings.get_enabled_tools() else "retrieve_documents")
        else:
            # Direct routing without orchestration
            if self.settings.get_enabled_tools():
                builder.add_edge("analyze_query", "execute_tools")
                builder.add_edge("execute_tools", "retrieve_documents")
            else:
                builder.add_edge("analyze_query", "retrieve_documents")
        
        # Tools to retrieval
        if self.settings.get_enabled_tools():
            builder.add_edge("execute_tools", "retrieve_documents")
        
        # Retrieval to response generation
        builder.add_edge("retrieve_documents", "generate_response")
        
        # Quality control flow
        if self.settings.workflow.enable_hallucination_check:
            builder.add_edge("generate_response", "quality_check")
            builder.add_conditional_edges(
                "quality_check",
                self._route_after_quality_check,
                {
                    "pass": "finalize_response",
                    "retry": "generate_response",
                    "fail": "finalize_response"
                }
            )
        else:
            builder.add_edge("generate_response", "finalize_response")
        
        builder.add_edge("finalize_response", END)
    
    # ========================================
    # NODE IMPLEMENTATIONS (Updated paths)
    # ========================================
    
    async def _initialize_processing(self, state: RAGState) -> RAGState:
        """Initialize processing state"""
        workflow_id = f"rag_{datetime.now().isoformat()}_{state.get('user_id', 'anon')}"
        
        return {
            **state,
            "workflow_id": workflow_id,
            "processing_time": 0.0,
            "iteration_count": 0,
            "language": state.get("language", "vi"),
            "processed_query": state["original_query"],
            "quality_checks": {},
            "content_safety": {},
            "agent_outputs": {},
            "tool_outputs": [],
            "retrieved_documents": [],
            "document_sources": []
        }
    
    async def _analyze_query(self, state: RAGState) -> RAGState:
        """Analyze query using current configuration"""
        query = state["processed_query"]
        
        # Use enabled providers only
        enabled_providers = self.settings.get_enabled_providers()
        if not enabled_providers:
            logger.warning("No LLM providers enabled")
            return {
                **state,
                "complexity_score": 0.5,
                "analysis_result": {"error": "No providers enabled"}
            }
        
        try:
            llm = await llm_provider_manager.get_provider(enabled_providers[0])
            
            analysis_prompt = f"""
Phân tích query và xác định approach:

Query: {query}
Language: {state['language']}

Available components:
- Orchestrator: {'enabled' if self.settings.orchestrator.get('enabled') else 'disabled'}
- Enabled tools: {self.settings.get_enabled_tools()}
- Enabled agents: {self.settings.get_enabled_agents()}

Trả về JSON:
{{
    "complexity_score": 0.7,
    "needs_orchestration": true,
    "needs_tools": false,
    "needs_retrieval": true
}}
"""
            
            response = await llm.ainvoke(analysis_prompt)
            
            # Parse analysis
            import json
            json_start = response.content.find('{')
            json_end = response.content.rfind('}') + 1
            
            if json_start >= 0 and json_end > json_start:
                analysis = json.loads(response.content[json_start:json_end])
            else:
                analysis = {"complexity_score": 0.5, "needs_orchestration": True}
            
            return {
                **state,
                "complexity_score": analysis.get("complexity_score", 0.5),
                "analysis_result": analysis
            }
            
        except Exception as e:
            logger.error(f"Query analysis failed: {e}")
            return {
                **state,
                "complexity_score": 0.5,
                "analysis_result": {"error": str(e)}
            }
    
    async def _orchestrate_agents(self, state: RAGState) -> RAGState:
        """Orchestrate agents with their configured providers"""
        try:
            result = await self.orchestrator.select_agents(
                query=state["processed_query"],
                language=state["language"],
                complexity=state["complexity_score"]
            )
            
            # Execute selected agents with their specific providers
            agent_outputs = {}
            for agent_name in result["selected_agents"]:
                agent_result = await self.orchestrator.execute_agent_task(
                    agent_name=agent_name,
                    task=state["processed_query"],
                    context={"language": state["language"]}
                )
                agent_outputs[agent_name] = agent_result
            
            return {
                **state,
                "selected_agents": result["selected_agents"],
                "orchestrator_reasoning": result["reasoning"],
                "agent_outputs": agent_outputs
            }
            
        except Exception as e:
            logger.error(f"Agent orchestration failed: {e}")
            return {
                **state,
                "selected_agents": ["general_assistant"],
                "orchestrator_reasoning": f"Orchestration error: {e}",
                "agent_outputs": {}
            }
    
    async def _execute_tools(self, state: RAGState) -> RAGState:
        """Execute tools based on current configuration"""
        enabled_tools = self.settings.get_enabled_tools()
        
        if not enabled_tools:
            return {**state, "tool_outputs": []}
        
        try:
            relevant_tools = await self.tool_service.get_relevant_tools(
                query=state["processed_query"],
                available_tools=enabled_tools
            )
            
            tool_outputs = []
            for tool_name in relevant_tools:
                result = await self.tool_service.execute_tool(
                    tool_name=tool_name,
                    query=state["processed_query"],
                    context={"language": state["language"]}
                )
                tool_outputs.append({
                    "tool": tool_name,
                    "result": result.result if result.success else f"Error: {result.error}",
                    "success": result.success,
                    "timestamp": datetime.now().isoformat()
                })
            
            return {**state, "tool_outputs": tool_outputs}
            
        except Exception as e:
            logger.error(f"Tool execution failed: {e}")
            return {**state, "tool_outputs": [{"error": str(e)}]}
    
    async def _retrieve_documents(self, state: RAGState) -> RAGState:
        """Retrieve documents with current configuration"""
        try:
            from services.vector.vector_service import VectorService
            
            vector_service = VectorService()
            
            results = await vector_service.search(
                query=state["processed_query"],
                top_k=self.settings.rag["default_top_k"],
                threshold=self.settings.rag["default_threshold"]
            )
            
            return {
                **state,
                "retrieved_documents": results,
                "document_sources": [doc.get("source", "Unknown") for doc in results]
            }
            
        except Exception as e:
            logger.error(f"Document retrieval failed: {e}")
            return {
                **state,
                "retrieved_documents": [],
                "document_sources": []
            }
    
    async def _generate_response(self, state: RAGState) -> RAGState:
        """Generate response using enabled providers"""
        try:
            enabled_providers = self.settings.get_enabled_providers()
            if not enabled_providers:
                raise ValueError("No LLM providers enabled")
            
            llm = await llm_provider_manager.get_provider(enabled_providers[0])
            
            # Build context
            context_parts = []
            
            # Add agent outputs
            if state["agent_outputs"]:
                agent_context = "\n".join([
                    f"Agent {agent}: {output.get('response', '')}"
                    for agent, output in state["agent_outputs"].items()
                    if output.get("success", True)
                ])
                if agent_context:
                    context_parts.append(f"AGENT ANALYSIS:\n{agent_context}")
            
            # Add tool outputs
            if state["tool_outputs"]:
                tool_context = "\n".join([
                    f"Tool {output['tool']}: {output['result']}"
                    for output in state["tool_outputs"]
                    if output.get("success", True)
                ])
                if tool_context:
                    context_parts.append(f"TOOL RESULTS:\n{tool_context}")
            
            # Add retrieved documents
            if state["retrieved_documents"]:
                doc_context = "\n".join([
                    f"Document: {doc.get('content', '')}"
                    for doc in state["retrieved_documents"][:3]
                ])
                context_parts.append(f"RETRIEVED DOCUMENTS:\n{doc_context}")
            
            context = "\n\n".join(context_parts) if context_parts else "Không có thông tin tham khảo cụ thể."
            
            response_prompt = f"""
Bạn là AI Assistant. Trả lời câu hỏi dựa vào thông tin được cung cấp:

Câu hỏi: {state['processed_query']}

Thông tin tham khảo:
{context}

Trả lời bằng {state['language']}, chính xác và hữu ích:
"""
            
            response = await llm.ainvoke(response_prompt)
            
            # Calculate confidence
            confidence = 0.7
            if state["retrieved_documents"]:
                confidence += 0.2
            if state["tool_outputs"]:
                confidence += 0.1
            if state["agent_outputs"]:
                confidence += 0.1
            confidence = min(confidence, 0.95)
            
            return {
                **state,
                "draft_response": response.content,
                "confidence_score": confidence
            }
            
        except Exception as e:
            logger.error(f"Response generation failed: {e}")
            return {
                **state,
                "draft_response": "Xin lỗi, tôi không thể tạo câu trả lời lúc này.",
                "confidence_score": 0.1
            }
    
    async def _quality_check(self, state: RAGState) -> RAGState:
        """Quality check if enabled in configuration"""
        if not self.settings.workflow.enable_hallucination_check:
            return {**state, "quality_checks": {"skipped": True}}
        
        try:
            checks = {
                "has_content": len(state["draft_response"].strip()) > 10,
                "appropriate_length": 50 < len(state["draft_response"]) < 5000,
                "not_error_message": "xin lỗi" not in state["draft_response"].lower()
            }
            
            return {**state, "quality_checks": checks}
            
        except Exception as e:
            logger.error(f"Quality check failed: {e}")
            return {**state, "quality_checks": {"error": str(e)}}
    
    async def _finalize_response(self, state: RAGState) -> RAGState:
        """Finalize response"""
        final_response = state["draft_response"]
        
        # Add sources if available and enabled
        if state["document_sources"] and self.settings.workflow.enable_citation_generation:
            sources_text = "\n\nNguồn tham khảo: " + ", ".join(state["document_sources"][:3])
            final_response += sources_text
        
        return {
            **state,
            "final_response": final_response,
            "processing_time": (datetime.now().timestamp() - state.get("start_time", datetime.now().timestamp())),
            "iteration_count": state.get("iteration_count", 0) + 1
        }
    
    # ========================================
    # ROUTING FUNCTIONS
    # ========================================
    
    def _route_after_analysis(self, state: RAGState) -> Literal["orchestrate", "direct_tools", "direct_retrieval"]:
        """Route based on analysis and current configuration"""
        analysis = state.get("analysis_result", {})
        
        # Check if orchestration is enabled and needed
        if (self.settings.orchestrator.get("enabled", True) and 
            analysis.get("needs_orchestration", False)):
            return "orchestrate"
        
        # Check if tools are enabled and needed
        elif (self.settings.get_enabled_tools() and 
              analysis.get("needs_tools", False)):
            return "direct_tools"
        
        else:
            return "direct_retrieval"
    
    def _route_after_quality_check(self, state: RAGState) -> Literal["pass", "retry", "fail"]:
        """Route based on quality check results"""
        if not self.settings.workflow.enable_hallucination_check:
            return "pass"
        
        checks = state.get("quality_checks", {})
        
        # If all checks pass
        if all(checks.values()) and "error" not in checks:
            return "pass"
        
        # Allow retry if under iteration limit
        elif state.get("iteration_count", 0) < self.settings.workflow.max_iterations:
            return "retry"
        
        else:
            return "fail"
    
    # ========================================
    # PUBLIC INTERFACE
    # ========================================
    
    async def process_query(
        self,
        query: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        language: str = "vi",
        conversation_history: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Process RAG query through config-aware workflow"""
        
        if not self._initialized:
            await self.initialize()
        
        # Create initial state
        initial_state = RAGState(
            messages=[HumanMessage(content=query)],
            original_query=query,
            processed_query=query,
            language=language,
            user_id=user_id,
            session_id=session_id or f"session_{datetime.now().isoformat()}",
            conversation_history=conversation_history or [],
            selected_agents=[],
            agent_outputs={},
            orchestrator_reasoning="",
            complexity_score=0.0,
            tool_calls=[],
            tool_outputs=[],
            retrieved_documents=[],
            document_sources=[],
            draft_response="",
            final_response="",
            confidence_score=0.0,
            quality_checks={},
            content_safety={},
            workflow_id="",
            processing_time=0.0,
            iteration_count=0
        )
        
        initial_state["start_time"] = datetime.now().timestamp()
        
        try:
            config = {"configurable": {"thread_id": initial_state["session_id"]}}
            
            final_state = await self.graph.ainvoke(initial_state, config=config)
            
            return {
                "response": final_state["final_response"],
                "sources": final_state["document_sources"],
                "confidence": final_state["confidence_score"],
                "workflow_id": final_state["workflow_id"],
                "processing_time": final_state["processing_time"],
                "metadata": {
                    "selected_agents": final_state["selected_agents"],
                    "orchestrator_reasoning": final_state["orchestrator_reasoning"],
                    "complexity_score": final_state["complexity_score"],
                    "tools_used": [output.get("tool") for output in final_state["tool_outputs"]],
                    "quality_checks": final_state["quality_checks"],
                    "iteration_count": final_state["iteration_count"],
                    "configuration_version": datetime.now().isoformat(),
                    "agent_outputs": final_state["agent_outputs"]
                }
            }
            
        except Exception as e:
            logger.error(f"Workflow execution failed: {e}")
            return {
                "response": "Xin lỗi, đã có lỗi xảy ra trong quá trình xử lý.",
                "sources": [],
                "confidence": 0.1,
                "workflow_id": initial_state.get("workflow_id", "unknown"),
                "processing_time": 0.0,
                "metadata": {"error": str(e)}
            }
    
    async def health_check(self) -> bool:
        """Check workflow health"""
        try:
            return self._initialized and self.graph is not None and not self._rebuilding
        except Exception:
            return False
    
    async def get_configuration_status(self) -> Dict[str, Any]:
        """Get current configuration status"""
        return {
            "initialized": self._initialized,
            "rebuilding": self._rebuilding,
            "enabled_providers": self.settings.get_enabled_providers(),
            "enabled_tools": self.settings.get_enabled_tools(),
            "enabled_agents": self.settings.get_enabled_agents(),
            "orchestrator_enabled": self.settings.orchestrator.get("enabled", True),
            "workflow_features": {
                "reflection": self.settings.workflow.enable_reflection,
                "semantic_routing": self.settings.workflow.enable_semantic_routing,
                "document_grading": self.settings.workflow.enable_document_grading,
                "citation_generation": self.settings.workflow.enable_citation_generation,
                "hallucination_check": self.settings.workflow.enable_hallucination_check
            }
        }

# Global workflow instance  
rag_workflow = ConfigAwareRAGWorkflow()

from typing import Dict, Any, List, Optional, Literal, Annotated
from typing_extensions import TypedDict
from datetime import datetime
import asyncio

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages  
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.redis import RedisSaver

from config.settings import get_settings
from services.config.config_manager import config_manager, ConfigSubscriber, ConfigChange, ConfigChangeType
from services.llm.provider_manager import llm_provider_manager
from services.tools.tool_service import ToolService
from services.orchestrator.agent_orchestrator import AgentOrchestrator
from utils.logging import get_logger

logger = get_logger(__name__)

class RAGState(TypedDict):
    """RAG workflow state schema"""
    
    # Messages - Core LangGraph pattern
    messages: Annotated[List[BaseMessage], add_messages]
    
    # Query processing
    original_query: str
    processed_query: str
    language: str
    
    # User context
    user_id: Optional[str]
    session_id: str
    conversation_history: List[Dict[str, Any]]
    
    # Agent orchestration
    selected_agents: List[str]
    agent_outputs: Dict[str, Dict[str, Any]]
    orchestrator_reasoning: str
    complexity_score: float
    
    # Tool execution
    tool_calls: List[Dict[str, Any]]
    tool_outputs: List[Dict[str, Any]]
    
    # Document retrieval
    retrieved_documents: List[Dict[str, Any]]
    document_sources: List[str]
    
    # Response generation
    draft_response: str
    final_response: str
    confidence_score: float
    
    # Quality control
    quality_checks: Dict[str, bool]
    content_safety: Dict[str, Any]
    
    # Metadata
    workflow_id: str
    processing_time: float
    iteration_count: int

class ConfigAwareRAGWorkflow(ConfigSubscriber):
    """
    Configuration-aware RAG Workflow
    Automatically reloads when admin changes settings
    """
    
    def __init__(self):
        self.settings = get_settings()
        self.tool_service = ToolService()
        self.orchestrator = AgentOrchestrator()
        self.graph = None
        self.checkpointer = None
        self._initialized = False
        self._rebuilding = False
        
    async def initialize(self):
        """Initialize workflow với config subscription"""
        try:
            await self._setup_checkpointer()
            await self._build_graph()
            
            # Subscribe to configuration changes
            config_manager.subscribe("workflow", self)
            
            self._initialized = True
            logger.info("Config-aware RAG Workflow initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize RAG Workflow: {e}")
            raise
    
    async def on_config_change(self, change: ConfigChange) -> bool:
        """
        Handle configuration changes from admin
        Automatically reload affected components
        """
        try:
            logger.info(f"Workflow received config change: {change.change_type} for {change.component_name}")
            
            # Prevent concurrent rebuilds
            if self._rebuilding:
                logger.info("Workflow rebuild already in progress, skipping")
                return True
            
            self._rebuilding = True
            
            # Reload settings first
            from config.settings import reload_settings
            self.settings = reload_settings()
            
            # Handle different types of changes
            if change.change_type in [
                ConfigChangeType.PROVIDER_ENABLED,
                ConfigChangeType.PROVIDER_DISABLED,
                ConfigChangeType.PROVIDER_CONFIG_CHANGED
            ]:
                await self._handle_provider_change(change)
                
            elif change.change_type in [
                ConfigChangeType.TOOL_ENABLED,
                ConfigChangeType.TOOL_DISABLED,
                ConfigChangeType.TOOL_CONFIG_CHANGED
            ]:
                await self._handle_tool_change(change)
                
            elif change.change_type in [
                ConfigChangeType.AGENT_ENABLED,
                ConfigChangeType.AGENT_DISABLED,
                ConfigChangeType.AGENT_CONFIG_CHANGED
            ]:
                await self._handle_agent_change(change)
                
            elif change.change_type == ConfigChangeType.WORKFLOW_CONFIG_CHANGED:
                await self._handle_workflow_change(change)
            
            # Rebuild workflow graph with new configuration
            await self._rebuild_workflow()
            
            self._rebuilding = False
            
            logger.info(f"Workflow successfully adapted to config change: {change.component_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to handle config change: {e}")
            self._rebuilding = False
            return False
    
    async def _handle_provider_change(self, change: ConfigChange):
        """Handle LLM provider configuration changes"""
        logger.info(f"Handling provider change: {change.component_name}")
        
        # Reinitialize LLM provider manager
        if llm_provider_manager._initialized:
            llm_provider_manager._initialized = False
            await llm_provider_manager.initialize()
    
    async def _handle_tool_change(self, change: ConfigChange):
        """Handle tool configuration changes"""
        logger.info(f"Handling tool change: {change.component_name}")
        
        # Reinitialize tool service
        if self.tool_service._initialized:
            self.tool_service._initialized = False
            await self.tool_service.initialize()
    
    async def _handle_agent_change(self, change: ConfigChange):
        """Handle agent configuration changes"""
        logger.info(f"Handling agent change: {change.component_name}")
        
        # Agent orchestrator doesn't need reinitialization
        # It reads from settings dynamically
        pass
    
    async def _handle_workflow_change(self, change: ConfigChange):
        """Handle workflow configuration changes"""
        logger.info("Handling workflow configuration change")
        
        # Workflow will be rebuilt with new settings
        # No additional actions needed
        pass
    
    async def _rebuild_workflow(self):
        """Rebuild workflow graph with updated configuration"""
        try:
            logger.info("Rebuilding workflow graph with updated configuration...")
            
            # Setup checkpointer if type changed
            await self._setup_checkpointer()
            
            # Rebuild graph
            await self._build_graph()
            
            logger.info("Workflow graph rebuilt successfully")
            
        except Exception as e:
            logger.error(f"Failed to rebuild workflow: {e}")
            raise
    
    async def _setup_checkpointer(self):
        """Setup checkpointer based on current configuration"""
        checkpointer_type = self.settings.workflow.checkpointer_type
        
        if checkpointer_type == "redis":
            try:
                import redis.asyncio as redis
                redis_client = redis.from_url(self.settings.cache.url)
                self.checkpointer = RedisSaver(redis_client)
                logger.info("Redis checkpointer configured")
            except Exception as e:
                logger.warning(f"Redis checkpointer failed: {e}, using memory")
                self.checkpointer = MemorySaver()
        else:
            self.checkpointer = MemorySaver()
    
    async def _build_graph(self):
        """Build LangGraph with current configuration"""
        builder = StateGraph(RAGState)
        
        # Add nodes based on current configuration
        builder.add_node("initialize", self._initialize_processing)
        builder.add_node("analyze_query", self._analyze_query)
        
        # Conditional nodes based on configuration
        if self.settings.orchestrator.get("enabled", True):
            builder.add_node("orchestrate_agents", self._orchestrate_agents)
        
        # Tools node if any tools are enabled
        if self.settings.get_enabled_tools():
            builder.add_node("execute_tools", self._execute_tools)
        
        builder.add_node("retrieve_documents", self._retrieve_documents)
        builder.add_node("generate_response", self._generate_response)
        
        # Quality control based on configuration
        if self.settings.workflow.enable_hallucination_check:
            builder.add_node("quality_check", self._quality_check)
        
        builder.add_node("finalize_response", self._finalize_response)
        
        # Build edges based on current configuration
        await self._build_workflow_edges(builder)
        
        # Set entry and exit points
        builder.set_entry_point("initialize")
        builder.set_finish_point("finalize_response")
        
        # Compile graph
        self.graph = builder.compile(
            checkpointer=self.checkpointer,
            debug=self.settings.DEBUG
        )
    
    async def _build_workflow_edges(self, builder):
        """Build workflow edges based on current configuration"""
        
        builder.add_edge(START, "initialize")
        builder.add_edge("initialize", "analyze_query")
        
        # Routing after analysis
        if self.settings.orchestrator.get("enabled", True):
            builder.add_conditional_edges(
                "analyze_query",
                self._route_after_analysis,
                {
                    "orchestrate": "orchestrate_agents",
                    "direct_tools": "execute_tools" if self.settings.get_enabled_tools() else "retrieve_documents",
                    "direct_retrieval": "retrieve_documents"
                }
            )
            builder.add_edge("orchestrate_agents", "execute_tools" if self.settings.get_enabled_tools() else "retrieve_documents")
        else:
            # Direct routing without orchestration
            if self.settings.get_enabled_tools():
                builder.add_edge("analyze_query", "execute_tools")
                builder.add_edge("execute_tools", "retrieve_documents")
            else:
                builder.add_edge("analyze_query", "retrieve_documents")
        
        # Tools to retrieval
        if self.settings.get_enabled_tools():
            builder.add_edge("execute_tools", "retrieve_documents")
        
        # Retrieval to response generation
        builder.add_edge("retrieve_documents", "generate_response")
        
        # Quality control flow
        if self.settings.workflow.enable_hallucination_check:
            builder.add_edge("generate_response", "quality_check")
            builder.add_conditional_edges(
                "quality_check",
                self._route_after_quality_check,
                {
                    "pass": "finalize_response",
                    "retry": "generate_response",
                    "fail": "finalize_response"
                }
            )
        else:
            builder.add_edge("generate_response", "finalize_response")
        
        builder.add_edge("finalize_response", END)
    
    # ========================================
    # NODE IMPLEMENTATIONS
    # ========================================
    
    async def _initialize_processing(self, state: RAGState) -> RAGState:
        """Initialize processing state"""
        workflow_id = f"rag_{datetime.now().isoformat()}_{state.get('user_id', 'anon')}"
        
        return {
            **state,
            "workflow_id": workflow_id,
            "processing_time": 0.0,
            "iteration_count": 0,
            "language": state.get("language", "vi"),
            "processed_query": state["original_query"],
            "quality_checks": {},
            "content_safety": {},
            "agent_outputs": {},
            "tool_outputs": [],
            "retrieved_documents": [],
            "document_sources": []
        }
    
    async def _analyze_query(self, state: RAGState) -> RAGState:
        """Analyze query using current configuration"""
        query = state["processed_query"]
        
        # Use enabled providers only
        enabled_providers = self.settings.get_enabled_providers()
        if not enabled_providers:
            logger.warning("No LLM providers enabled")
            return {
                **state,
                "complexity_score": 0.5,
                "analysis_result": {"error": "No providers enabled"}
            }
        
        try:
            llm = await llm_provider_manager.get_provider(enabled_providers[0])
            
            analysis_prompt = f"""
Phân tích query và xác định approach:

Query: {query}
Language: {state['language']}

Available components:
- Orchestrator: {'enabled' if self.settings.orchestrator.get('enabled') else 'disabled'}
- Enabled tools: {self.settings.get_enabled_tools()}
- Enabled agents: {self.settings.get_enabled_agents()}

Trả về JSON:
{{
    "complexity_score": 0.7,
    "needs_orchestration": true,
    "needs_tools": false,
    "needs_retrieval": true
}}
"""
            
            response = await llm.ainvoke(analysis_prompt)
            
            # Parse analysis
            import json
            json_start = response.content.find('{')
            json_end = response.content.rfind('}') + 1
            
            if json_start >= 0 and json_end > json_start:
                analysis = json.loads(response.content[json_start:json_end])
            else:
                analysis = {"complexity_score": 0.5, "needs_orchestration": True}
            
            return {
                **state,
                "complexity_score": analysis.get("complexity_score", 0.5),
                "analysis_result": analysis
            }
            
        except Exception as e:
            logger.error(f"Query analysis failed: {e}")
            return {
                **state,
                "complexity_score": 0.5,
                "analysis_result": {"error": str(e)}
            }
    
    async def _orchestrate_agents(self, state: RAGState) -> RAGState:
        """Orchestrate agents if enabled"""
        try:
            result = await self.orchestrator.select_agents(
                query=state["processed_query"],
                language=state["language"],
                complexity=state["complexity_score"]
            )
            
            return {
                **state,
                "selected_agents": result["selected_agents"],
                "orchestrator_reasoning": result["reasoning"]
            }
            
        except Exception as e:
            logger.error(f"Agent orchestration failed: {e}")
            return {
                **state,
                "selected_agents": ["general_assistant"],
                "orchestrator_reasoning": f"Orchestration error: {e}"
            }
    
    async def _execute_tools(self, state: RAGState) -> RAGState:
        """Execute tools based on current configuration"""
        enabled_tools = self.settings.get_enabled_tools()
        
        if not enabled_tools:
            return {**state, "tool_outputs": []}
        
        try:
            relevant_tools = await self.tool_service.get_relevant_tools(
                query=state["processed_query"],
                available_tools=enabled_tools
            )
            
            tool_outputs = []
            for tool_name in relevant_tools:
                result = await self.tool_service.execute_tool(
                    tool_name=tool_name,
                    query=state["processed_query"],
                    context={"language": state["language"]}
                )
                tool_outputs.append({
                    "tool": tool_name,
                    "result": result.result if result.success else f"Error: {result.error}",
                    "success": result.success,
                    "timestamp": datetime.now().isoformat()
                })
            
            return {**state, "tool_outputs": tool_outputs}
            
        except Exception as e:
            logger.error(f"Tool execution failed: {e}")
            return {**state, "tool_outputs": [{"error": str(e)}]}
    
    async def _retrieve_documents(self, state: RAGState) -> RAGState:
        """Retrieve documents with current configuration"""
        try:
            from services.vector.vector_service import VectorService
            
            vector_service = VectorService()
            
            results = await vector_service.search(
                query=state["processed_query"],
                top_k=self.settings.rag["default_top_k"],
                threshold=self.settings.rag["default_threshold"]
            )
            
            return {
                **state,
                "retrieved_documents": results,
                "document_sources": [doc.get("source", "Unknown") for doc in results]
            }
            
        except Exception as e:
            logger.error(f"Document retrieval failed: {e}")
            return {
                **state,
                "retrieved_documents": [],
                "document_sources": []
            }
    
    async def _generate_response(self, state: RAGState) -> RAGState:
        """Generate response using enabled providers"""
        try:
            enabled_providers = self.settings.get_enabled_providers()
            if not enabled_providers:
                raise ValueError("No LLM providers enabled")
            
            llm = await llm_provider_manager.get_provider(enabled_providers[0])
            
            # Build context
            context_parts = []
            
            if state["tool_outputs"]:
                tool_context = "\n".join([
                    f"Tool {output['tool']}: {output['result']}"
                    for output in state["tool_outputs"]
                    if output.get("success", True)
                ])
                if tool_context:
                    context_parts.append(f"TOOL RESULTS:\n{tool_context}")
            
            if state["retrieved_documents"]:
                doc_context = "\n".join([
                    f"Document: {doc.get('content', '')}"
                    for doc in state["retrieved_documents"][:3]
                ])
                context_parts.append(f"RETRIEVED DOCUMENTS:\n{doc_context}")
            
            context = "\n\n".join(context_parts) if context_parts else "Không có thông tin tham khảo cụ thể."
            
            response_prompt = f"""
Bạn là AI Assistant. Trả lời câu hỏi dựa vào thông tin được cung cấp:

Câu hỏi: {state['processed_query']}

Thông tin tham khảo:
{context}

Trả lời bằng {state['language']}, chính xác và hữu ích:
"""
            
            response = await llm.ainvoke(response_prompt)
            
            # Calculate confidence
            confidence = 0.7
            if state["retrieved_documents"]:
                confidence += 0.2
            if state["tool_outputs"]:
                confidence += 0.1
            confidence = min(confidence, 0.95)
            
            return {
                **state,
                "draft_response": response.content,
                "confidence_score": confidence
            }
            
        except Exception as e:
            logger.error(f"Response generation failed: {e}")
            return {
                **state,
                "draft_response": "Xin lỗi, tôi không thể tạo câu trả lời lúc này.",
                "confidence_score": 0.1
            }
    
    async def _quality_check(self, state: RAGState) -> RAGState:
        """Quality check if enabled in configuration"""
        if not self.settings.workflow.enable_hallucination_check:
            return {**state, "quality_checks": {"skipped": True}}
        
        try:
            checks = {
                "has_content": len(state["draft_response"].strip()) > 10,
                "appropriate_length": 50 < len(state["draft_response"]) < 5000,
                "not_error_message": "xin lỗi" not in state["draft_response"].lower()
            }
            
            return {**state, "quality_checks": checks}
            
        except Exception as e:
            logger.error(f"Quality check failed: {e}")
            return {**state, "quality_checks": {"error": str(e)}}
    
    async def _finalize_response(self, state: RAGState) -> RAGState:
        """Finalize response"""
        final_response = state["draft_response"]
        
        # Add sources if available and enabled
        if state["document_sources"] and self.settings.workflow.enable_citation_generation:
            sources_text = "\n\nNguồn tham khảo: " + ", ".join(state["document_sources"][:3])
            final_response += sources_text
        
        return {
            **state,
            "final_response": final_response,
            "processing_time": (datetime.now().timestamp() - state.get("start_time", datetime.now().timestamp())),
            "iteration_count": state.get("iteration_count", 0) + 1
        }
    
    # ========================================
    # ROUTING FUNCTIONS
    # ========================================
    
    def _route_after_analysis(self, state: RAGState) -> Literal["orchestrate", "direct_tools", "direct_retrieval"]:
        """Route based on analysis and current configuration"""
        analysis = state.get("analysis_result", {})
        
        # Check if orchestration is enabled and needed
        if (self.settings.orchestrator.get("enabled", True) and 
            analysis.get("needs_orchestration", False)):
            return "orchestrate"
        
        # Check if tools are enabled and needed
        elif (self.settings.get_enabled_tools() and 
              analysis.get("needs_tools", False)):
            return "direct_tools"
        
        else:
            return "direct_retrieval"
    
    def _route_after_quality_check(self, state: RAGState) -> Literal["pass", "retry", "fail"]:
        """Route based on quality check results"""
        if not self.settings.workflow.enable_hallucination_check:
            return "pass"
        
        checks = state.get("quality_checks", {})
        
        # If all checks pass
        if all(checks.values()) and "error" not in checks:
            return "pass"
        
        # Allow retry if under iteration limit
        elif state.get("iteration_count", 0) < self.settings.workflow.max_iterations:
            return "retry"
        
        else:
            return "fail"
    
    # ========================================
    # PUBLIC INTERFACE
    # ========================================
    
    async def process_query(
        self,
        query: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        language: str = "vi",
        conversation_history: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Process RAG query through config-aware workflow"""
        
        if not self._initialized:
            await self.initialize()
        
        # Create initial state
        initial_state = RAGState(
            messages=[HumanMessage(content=query)],
            original_query=query,
            processed_query=query,
            language=language,
            user_id=user_id,
            session_id=session_id or f"session_{datetime.now().isoformat()}",
            conversation_history=conversation_history or [],
            selected_agents=[],
            agent_outputs={},
            orchestrator_reasoning="",
            complexity_score=0.0,
            tool_calls=[],
            tool_outputs=[],
            retrieved_documents=[],
            document_sources=[],
            draft_response="",
            final_response="",
            confidence_score=0.0,
            quality_checks={},
            content_safety={},
            workflow_id="",
            processing_time=0.0,
            iteration_count=0
        )
        
        initial_state["start_time"] = datetime.now().timestamp()
        
        try:
            config = {"configurable": {"thread_id": initial_state["session_id"]}}
            
            final_state = await self.graph.ainvoke(initial_state, config=config)
            
            return {
                "response": final_state["final_response"],
                "sources": final_state["document_sources"],
                "confidence": final_state["confidence_score"],
                "workflow_id": final_state["workflow_id"],
                "processing_time": final_state["processing_time"],
                "metadata": {
                    "selected_agents": final_state["selected_agents"],
                    "orchestrator_reasoning": final_state["orchestrator_reasoning"],
                    "complexity_score": final_state["complexity_score"],
                    "tools_used": [output.get("tool") for output in final_state["tool_outputs"]],
                    "quality_checks": final_state["quality_checks"],
                    "iteration_count": final_state["iteration_count"],
                    "configuration_version": datetime.now().isoformat()
                }
            }
            
        except Exception as e:
            logger.error(f"Workflow execution failed: {e}")
            return {
                "response": "Xin lỗi, đã có lỗi xảy ra trong quá trình xử lý.",
                "sources": [],
                "confidence": 0.1,
                "workflow_id": initial_state.get("workflow_id", "unknown"),
                "processing_time": 0.0,
                "metadata": {"error": str(e)}
            }
    
    async def health_check(self) -> bool:
        """Check workflow health"""
        try:
            return self._initialized and self.graph is not None and not self._rebuilding
        except Exception:
            return False
    
    async def get_configuration_status(self) -> Dict[str, Any]:
        """Get current configuration status"""
        return {
            "initialized": self._initialized,
            "rebuilding": self._rebuilding,
            "enabled_providers": self.settings.get_enabled_providers(),
            "enabled_tools": self.settings.get_enabled_tools(),
            "enabled_agents": self.settings.get_enabled_agents(),
            "orchestrator_enabled": self.settings.orchestrator.get("enabled", True),
            "workflow_features": {
                "reflection": self.settings.workflow.enable_reflection,
                "semantic_routing": self.settings.workflow.enable_semantic_routing,
                "document_grading": self.settings.workflow.enable_document_grading,
                "citation_generation": self.settings.workflow.enable_citation_generation,
                "hallucination_check": self.settings.workflow.enable_hallucination_check
            }
        }

# Global workflow instance
rag_workflow = ConfigAwareRAGWorkflow()