from typing import Dict, Any, List, Optional, TypedDict, Annotated
from dataclasses import dataclass, field
import json
from datetime import datetime

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.checkpoint.redis import RedisSaver
from langgraph.prebuilt import ToolNode

from config.settings import get_settings
from core.exceptions import LangGraphError, WorkflowError
from services.llm.provider_manager import llm_provider_manager
from services.tools.tool_manager import tool_manager
from utils.logging import get_logger, log_performance

logger = get_logger(__name__)
settings = get_settings()

class WorkflowState(TypedDict):
    """LangGraph workflow state schema"""
    # Input
    query: str
    user_id: Optional[str]
    session_id: Optional[str]
    conversation_history: List[Dict[str, Any]]
    
    # Processing
    current_step: str
    routing_decision: Optional[str]
    retrieved_documents: List[Dict[str, Any]]
    tool_results: List[Dict[str, Any]]
    
    # Output
    response: Optional[str]
    sources: List[Dict[str, Any]]
    follow_up_questions: List[str]
    
    # Metadata
    processing_time: float
    tokens_used: int
    error: Optional[str]
    workflow_id: str
    
    # Configuration (dynamic từ admin)
    enabled_tools: Dict[str, bool]
    enabled_providers: List[str]
    workflow_config: Dict[str, Any]

@dataclass
class RAGWorkflowConfig:
    """Configuration cho RAG workflow"""
    max_iterations: int = 10
    timeout_seconds: int = 300
    
    # Model assignments (configurable từ admin)
    router_model: str = field(default_factory=lambda: settings.ROUTER_MODEL)
    retrieval_model: str = field(default_factory=lambda: settings.RETRIEVAL_MODEL)
    synthesis_model: str = field(default_factory=lambda: settings.SYNTHESIS_MODEL)
    reflection_model: str = field(default_factory=lambda: settings.REFLECTION_MODEL)
    
    # Workflow features (configurable từ admin)
    enable_reflection: bool = field(default_factory=lambda: settings.ENABLE_REFLECTION_WORKFLOW)
    enable_semantic_routing: bool = field(default_factory=lambda: settings.ENABLE_SEMANTIC_ROUTING)
    enable_document_grading: bool = field(default_factory=lambda: settings.ENABLE_DOCUMENT_GRADING)
    enable_citation_generation: bool = field(default_factory=lambda: settings.ENABLE_CITATION_GENERATION)
    enable_query_expansion: bool = field(default_factory=lambda: settings.ENABLE_QUERY_EXPANSION)
    enable_hallucination_check: bool = field(default_factory=lambda: settings.ENABLE_ANSWER_HALLUCINATION_CHECK)

class RAGWorkflow:
    """
    Agentic RAG Workflow sử dụng LangGraph
    Tất cả configurations được load từ admin settings
    """
    
    def __init__(self):
        self.graph: Optional[StateGraph] = None
        self.compiled_graph = None
        self.checkpointer = None
        self.config = RAGWorkflowConfig()
        self.initialized = False
    
    async def initialize(self):
        """Initialize RAG workflow với configuration từ admin"""
        try:
            logger.info("Initializing LangGraph RAG workflow...")
            
            # Setup checkpointer based on admin config
            await self._setup_checkpointer()
            
            # Load current configuration từ admin
            await self._load_admin_configuration()
            
            # Build workflow graph
            await self._build_workflow_graph()
            
            # Compile graph
            self.compiled_graph = self.graph.compile(
                checkpointer=self.checkpointer,
                debug=settings.ENABLE_LANGGRAPH_DEBUG
            )
            
            self.initialized = True
            logger.info("LangGraph RAG workflow initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize RAG workflow: {e}")
            raise LangGraphError(f"Workflow initialization failed: {e}")
    
    async def _setup_checkpointer(self):
        """Setup checkpointer based on admin configuration"""
        checkpointer_type = settings.LANGGRAPH_CHECKPOINTER_TYPE
        
        if checkpointer_type == "redis":
            try:
                import redis.asyncio as redis
                redis_client = redis.from_url(settings.redis_url)
                self.checkpointer = RedisSaver(redis_client)
                logger.info("Redis checkpointer configured")
            except Exception as e:
                logger.warning(f"Redis checkpointer failed, falling back to memory: {e}")
                self.checkpointer = MemorySaver()
        
        elif checkpointer_type == "postgres":
            try:
                from config.database import settings as db_settings
                # Sử dụng sync connection cho checkpointer
                conn_string = db_settings.DATABASE_URL
                self.checkpointer = PostgresSaver.from_conn_string(conn_string)
                logger.info("PostgreSQL checkpointer configured")
            except Exception as e:
                logger.warning(f"PostgreSQL checkpointer failed, falling back to memory: {e}")
                self.checkpointer = MemorySaver()
        
        else:
            self.checkpointer = MemorySaver()
            logger.info("Memory checkpointer configured")
    
    async def _load_admin_configuration(self):
        """Load configuration từ admin interface (database/API)"""
        try:
            # Trong thực tế, đây sẽ load từ database admin settings
            # Hiện tại sử dụng settings file
            
            self.config.router_model = settings.ROUTER_MODEL
            self.config.retrieval_model = settings.RETRIEVAL_MODEL
            self.config.synthesis_model = settings.SYNTHESIS_MODEL
            self.config.reflection_model = settings.REFLECTION_MODEL
            
            self.config.enable_reflection = settings.ENABLE_REFLECTION_WORKFLOW
            self.config.enable_semantic_routing = settings.ENABLE_SEMANTIC_ROUTING
            self.config.enable_document_grading = settings.ENABLE_DOCUMENT_GRADING
            self.config.enable_citation_generation = settings.ENABLE_CITATION_GENERATION
            self.config.enable_query_expansion = settings.ENABLE_QUERY_EXPANSION
            self.config.enable_hallucination_check = settings.ENABLE_ANSWER_HALLUCINATION_CHECK
            
            logger.info("Admin configuration loaded successfully")
            
        except Exception as e:
            logger.error(f"Failed to load admin configuration: {e}")
            # Use defaults if loading fails
    
    async def _build_workflow_graph(self):
        """Build LangGraph workflow với dynamic configuration"""
        
        # Create StateGraph
        self.graph = StateGraph(WorkflowState)
        
        # Add nodes based on admin configuration
        
        # Always add entry point
        self.graph.add_node("initialize", self._initialize_state)
        
        # Conditional nodes based on admin settings
        if self.config.enable_semantic_routing:
            self.graph.add_node("route_query", self._route_query)
        
        self.graph.add_node("retrieve_documents", self._retrieve_documents)
        
        if self.config.enable_document_grading:
            self.graph.add_node("grade_documents", self._grade_documents)
        
        if self.config.enable_query_expansion:
            self.graph.add_node("expand_query", self._expand_query)
        
        # Tool execution node (dynamic based on enabled tools)
        self.graph.add_node("execute_tools", self._execute_tools)
        
        # Response generation
        self.graph.add_node("generate_response", self._generate_response)
        
        if self.config.enable_hallucination_check:
            self.graph.add_node("check_hallucination", self._check_hallucination)
        
        if self.config.enable_reflection:
            self.graph.add_node("reflect_response", self._reflect_response)
        
        if self.config.enable_citation_generation:
            self.graph.add_node("generate_citations", self._generate_citations)
        
        self.graph.add_node("finalize", self._finalize_response)
        
        # Build edges based on configuration
        await self._build_workflow_edges()
        
        # Set entry and exit points
        self.graph.set_entry_point("initialize")
        self.graph.set_finish_point("finalize")
        
        logger.info("Workflow graph built successfully with admin configuration")
    
    async def _build_workflow_edges(self):
        """Build workflow edges based on admin configuration"""
        
        # Basic flow
        self.graph.add_edge(START, "initialize")
        
        if self.config.enable_semantic_routing:
            self.graph.add_edge("initialize", "route_query")
            self.graph.add_conditional_edges(
                "route_query",
                self._routing_condition,
                {
                    "retrieval": "retrieve_documents",
                    "tools": "execute_tools",
                    "direct": "generate_response"
                }
            )
        else:
            self.graph.add_edge("initialize", "retrieve_documents")
        
        # Document processing flow
        if self.config.enable_document_grading:
            self.graph.add_edge("retrieve_documents", "grade_documents")
            
            if self.config.enable_query_expansion:
                self.graph.add_conditional_edges(
                    "grade_documents",
                    self._document_grading_condition,
                    {
                        "good": "generate_response",
                        "expand": "expand_query",
                        "tools": "execute_tools"
                    }
                )
                self.graph.add_edge("expand_query", "retrieve_documents")
            else:
                self.graph.add_edge("grade_documents", "generate_response")
        else:
            self.graph.add_edge("retrieve_documents", "generate_response")
        
        # Tool execution flow
        self.graph.add_edge("execute_tools", "generate_response")
        
        # Response processing flow
        if self.config.enable_hallucination_check:
            self.graph.add_edge("generate_response", "check_hallucination")
            
            if self.config.enable_reflection:
                self.graph.add_conditional_edges(
                    "check_hallucination",
                    self._hallucination_condition,
                    {
                        "good": "reflect_response" if self.config.enable_reflection else "generate_citations",
                        "bad": "generate_response"  # Retry
                    }
                )
            else:
                self.graph.add_edge("check_hallucination", "generate_citations" if self.config.enable_citation_generation else "finalize")
        
        if self.config.enable_reflection:
            if self.config.enable_citation_generation:
                self.graph.add_edge("reflect_response", "generate_citations")
            else:
                self.graph.add_edge("reflect_response", "finalize")
        
        if self.config.enable_citation_generation:
            self.graph.add_edge("generate_citations", "finalize")
        else:
            # Direct to finalize if no citations
            if not self.config.enable_reflection and not self.config.enable_hallucination_check:
                self.graph.add_edge("generate_response", "finalize")
        
        self.graph.add_edge("finalize", END)
    
    # =================
    # WORKFLOW NODES
    # =================
    
    async def _initialize_state(self, state: WorkflowState) -> WorkflowState:
        """Initialize workflow state với admin configuration"""
        logger.info(f"Initializing workflow for query: {state['query'][:100]}...")
        
        state["current_step"] = "initialize"
        state["workflow_id"] = f"wf_{datetime.now().isoformat()}_{state.get('user_id', 'anon')}"
        state["processing_time"] = 0.0
        state["tokens_used"] = 0
        
        # Load current admin configuration
        state["enabled_tools"] = settings.enabled_tools
        state["enabled_providers"] = settings.enabled_providers
        state["workflow_config"] = settings.get_langgraph_config()
        
        logger.info(f"Workflow {state['workflow_id']} initialized with {len(state['enabled_providers'])} providers and {len([k for k, v in state['enabled_tools'].items() if v])} tools")
        
        return state
    
    async def _route_query(self, state: WorkflowState) -> WorkflowState:
        """Route query using semantic router (if enabled by admin)"""
        state["current_step"] = "route_query"
        
        try:
            # Get enabled router model from admin config
            router_model = self.config.router_model
            
            # Get LLM provider for routing
            llm = await llm_provider_manager.get_llm(
                provider=None,  # Auto-select based on admin config
                model=router_model
            )
            
            # Semantic routing logic
            routing_prompt = f"""
            Phân tích câu hỏi sau và quyết định hướng xử lý:
            
            Câu hỏi: {state['query']}
            
            Các lựa chọn:
            1. "retrieval" - Tìm kiếm trong tài liệu
            2. "tools" - Sử dụng công cụ (tính toán, web search, etc.)
            3. "direct" - Trả lời trực tiếp từ kiến thức
            
            Enabled tools: {[k for k, v in state['enabled_tools'].items() if v]}
            
            Trả về chỉ một từ: retrieval, tools, hoặc direct
            """
            
            response = await llm.ainvoke(routing_prompt)
            routing_decision = response.content.strip().lower()
            
            state["routing_decision"] = routing_decision
            logger.info(f"Query routed to: {routing_decision}")
            
        except Exception as e:
            logger.error(f"Routing failed: {e}")
            state["routing_decision"] = "retrieval"  # Default fallback
            state["error"] = f"Routing error: {e}"
        
        return state
    
    async def _retrieve_documents(self, state: WorkflowState) -> WorkflowState:
        """Retrieve relevant documents from vector database"""
        state["current_step"] = "retrieve_documents"
        
        try:
            from services.vector.milvus_service import milvus_service
            
            # Retrieve documents
            results = await milvus_service.search(
                query=state["query"],
                top_k=settings.DEFAULT_TOP_K,
                threshold=settings.DEFAULT_THRESHOLD
            )
            
            state["retrieved_documents"] = results
            logger.info(f"Retrieved {len(results)} documents")
            
        except Exception as e:
            logger.error(f"Document retrieval failed: {e}")
            state["retrieved_documents"] = []
            state["error"] = f"Retrieval error: {e}"
        
        return state
    
    async def _grade_documents(self, state: WorkflowState) -> WorkflowState:
        """Grade retrieved documents for relevance (if enabled by admin)"""
        state["current_step"] = "grade_documents"
        
        try:
            # Use admin-configured model for grading
            llm = await llm_provider_manager.get_llm(model=self.config.retrieval_model)
            
            graded_docs = []
            for doc in state["retrieved_documents"]:
                grading_prompt = f"""
                Đánh giá mức độ liên quan của tài liệu với câu hỏi:
                
                Câu hỏi: {state['query']}
                Tài liệu: {doc.get('content', '')[:500]}...
                
                Trả về: relevant hoặc irrelevant
                """
                
                response = await llm.ainvoke(grading_prompt)
                relevance = response.content.strip().lower()
                
                if relevance == "relevant":
                    graded_docs.append(doc)
            
            state["retrieved_documents"] = graded_docs
            logger.info(f"Graded documents: {len(graded_docs)} relevant out of {len(state['retrieved_documents'])}")
            
        except Exception as e:
            logger.error(f"Document grading failed: {e}")
            state["error"] = f"Grading error: {e}"
        
        return state
    
    async def _expand_query(self, state: WorkflowState) -> WorkflowState:
        """Expand query for better retrieval (if enabled by admin)"""
        state["current_step"] = "expand_query"
        
        try:
            llm = await llm_provider_manager.get_llm(model=self.config.retrieval_model)
            
            expansion_prompt = f"""
            Mở rộng câu hỏi sau để tìm kiếm tốt hơn:
            
            Câu hỏi gốc: {state['query']}
            
            Tạo 2-3 cách diễn đạt khác nhau để tìm kiếm thông tin liên quan.
            Trả về các từ khóa mở rộng, phân cách bởi dấu phẩy:
            """
            
            response = await llm.ainvoke(expansion_prompt)
            expanded_terms = response.content.strip()
            
            # Combine original query with expanded terms
            state["query"] = f"{state['query']} {expanded_terms}"
            logger.info(f"Query expanded: {expanded_terms}")
            
        except Exception as e:
            logger.error(f"Query expansion failed: {e}")
            state["error"] = f"Expansion error: {e}"
        
        return state
    
    async def _execute_tools(self, state: WorkflowState) -> WorkflowState:
        """Execute enabled tools based on admin configuration"""
        state["current_step"] = "execute_tools"
        
        try:
            # Get enabled tools from admin config
            enabled_tools = [k for k, v in state["enabled_tools"].items() if v]
            
            if not enabled_tools:
                logger.warning("No tools enabled by admin")
                state["tool_results"] = []
                return state
            
            # Get available tools from tool manager
            available_tools = await tool_manager.get_enabled_tools(enabled_tools)
            
            # Execute relevant tools based on query
            tool_results = []
            for tool_name, tool_instance in available_tools.items():
                try:
                    if await tool_manager.should_use_tool(tool_name, state["query"]):
                        result = await tool_instance.execute(state["query"])
                        tool_results.append({
                            "tool": tool_name,
                            "result": result,
                            "success": True
                        })
                        logger.info(f"Tool {tool_name} executed successfully")
                except Exception as tool_error:
                    logger.error(f"Tool {tool_name} failed: {tool_error}")
                    tool_results.append({
                        "tool": tool_name,
                        "result": str(tool_error),
                        "success": False
                    })
            
            state["tool_results"] = tool_results
            logger.info(f"Executed {len(tool_results)} tools")
            
        except Exception as e:
            logger.error(f"Tool execution failed: {e}")
            state["tool_results"] = []
            state["error"] = f"Tool execution error: {e}"
        
        return state
    
    async def _generate_response(self, state: WorkflowState) -> WorkflowState:
        """Generate response using admin-configured synthesis model"""
        state["current_step"] = "generate_response"
        
        try:
            # Use admin-configured synthesis model
            llm = await llm_provider_manager.get_llm(model=self.config.synthesis_model)
            
            # Build context from retrieved documents and tool results
            context_parts = []
            
            # Add document context
            if state.get("retrieved_documents"):
                doc_context = "\n".join([
                    f"Tài liệu {i+1}: {doc.get('content', '')}"
                    for i, doc in enumerate(state["retrieved_documents"][:5])
                ])
                context_parts.append(f"THÔNG TIN TỪ TÀI LIỆU:\n{doc_context}")
            
            # Add tool results
            if state.get("tool_results"):
                tool_context = "\n".join([
                    f"Kết quả từ {result['tool']}: {result['result']}"
                    for result in state["tool_results"] if result.get("success")
                ])
                if tool_context:
                    context_parts.append(f"KẾT QUẢ TỪ CÔNG CỤ:\n{tool_context}")
            
            # Add conversation history
            if state.get("conversation_history"):
                history_context = "\n".join([
                    f"{msg['role']}: {msg['content']}"
                    for msg in state["conversation_history"][-5:]  # Last 5 messages
                ])
                context_parts.append(f"LỊCH SỬ HỘI THOẠI:\n{history_context}")
            
            context = "\n\n".join(context_parts)
            
            response_prompt = f"""
            Bạn là một AI assistant thông minh. Dựa vào thông tin được cung cấp, hãy trả lời câu hỏi một cách chính xác và hữu ích.
            
            CÂU HỎI: {state['query']}
            
            THÔNG TIN THAM KHẢO:
            {context}
            
            YÊU CẦU:
            - Trả lời bằng tiếng Việt
            - Dựa vào thông tin được cung cấp
            - Nếu không có thông tin phù hợp, hãy nói rõ
            - Đưa ra câu trả lời chi tiết và có cấu trúc
            
            TRẢ LỜI:
            """
            
            response = await llm.ainvoke(response_prompt)
            state["response"] = response.content
            
            # Extract sources
            sources = []
            if state.get("retrieved_documents"):
                sources = [
                    {
                        "title": doc.get("title", "Unknown"),
                        "url": doc.get("url", ""),
                        "snippet": doc.get("content", "")[:200] + "..."
                    }
                    for doc in state["retrieved_documents"][:3]
                ]
            state["sources"] = sources
            
            logger.info("Response generated successfully")
            
        except Exception as e:
            logger.error(f"Response generation failed: {e}")
            state["response"] = "Xin lỗi, tôi không thể tạo câu trả lời lúc này. Vui lòng thử lại sau."
            state["error"] = f"Response generation error: {e}"
        
        return state
    
    async def _check_hallucination(self, state: WorkflowState) -> WorkflowState:
        """Check response for hallucination (if enabled by admin)"""
        state["current_step"] = "check_hallucination"
        
        try:
            llm = await llm_provider_manager.get_llm(model=self.config.reflection_model)
            
            hallucination_prompt = f"""
            Kiểm tra xem câu trả lời có bị ảo giác (hallucination) không:
            
            Câu hỏi: {state['query']}
            Câu trả lời: {state['response']}
            Thông tin tham khảo: {state.get('retrieved_documents', [])}
            
            Trả về: good (nếu câu trả lời phù hợp) hoặc bad (nếu có ảo giác)
            """
            
            response = await llm.ainvoke(hallucination_prompt)
            check_result = response.content.strip().lower()
            
            state["hallucination_check"] = check_result
            logger.info(f"Hallucination check: {check_result}")
            
        except Exception as e:
            logger.error(f"Hallucination check failed: {e}")
            state["hallucination_check"] = "good"  # Default to good
            state["error"] = f"Hallucination check error: {e}"
        
        return state
    
    async def _reflect_response(self, state: WorkflowState) -> WorkflowState:
        """Reflect and improve response (if enabled by admin)"""
        state["current_step"] = "reflect_response"
        
        try:
            llm = await llm_provider_manager.get_llm(model=self.config.reflection_model)
            
            reflection_prompt = f"""
            Cải thiện câu trả lời sau để tốt hơn:
            
            Câu hỏi: {state['query']}
            Câu trả lời hiện tại: {state['response']}
            
            Hãy cải thiện:
            1. Độ chính xác
            2. Tính đầy đủ
            3. Cấu trúc rõ ràng
            4. Tính hữu ích
            
            Câu trả lời được cải thiện:
            """
            
            response = await llm.ainvoke(reflection_prompt)
            state["response"] = response.content
            
            logger.info("Response reflected and improved")
            
        except Exception as e:
            logger.error(f"Response reflection failed: {e}")
            state["error"] = f"Reflection error: {e}"
        
        return state
    
    async def _generate_citations(self, state: WorkflowState) -> WorkflowState:
        """Generate citations for response (if enabled by admin)"""
        state["current_step"] = "generate_citations"
        
        try:
            if not state.get("sources"):
                logger.info("No sources available for citation generation")
                return state
            
            llm = await llm_provider_manager.get_llm(model=self.config.synthesis_model)
            
            citation_prompt = f"""
            Tạo các câu hỏi tiếp theo phù hợp cho cuộc hội thoại:
            
            Câu hỏi gốc: {state['query']}
            Câu trả lời: {state['response']}
            
            Tạo {settings.NUM_FOLLOW_UP_QUESTIONS} câu hỏi tiếp theo thú vị và liên quan.
            Trả về danh sách các câu hỏi, mỗi câu một dòng:
            """
            
            response = await llm.ainvoke(citation_prompt)
            follow_up_questions = [
                q.strip("- ").strip()
                for q in response.content.split("\n")
                if q.strip() and not q.strip().startswith("1.") and not q.strip().startswith("2.") and not q.strip().startswith("3.")
            ][:settings.NUM_FOLLOW_UP_QUESTIONS]
            
            state["follow_up_questions"] = follow_up_questions
            logger.info(f"Generated {len(follow_up_questions)} follow-up questions")
            
        except Exception as e:
            logger.error(f"Citation generation failed: {e}")
            state["follow_up_questions"] = []
            state["error"] = f"Citation error: {e}"
        
        return state
    
    async def _finalize_response(self, state: WorkflowState) -> WorkflowState:
        """Finalize workflow response"""
        state["current_step"] = "finalize"
        
        # Calculate processing time
        # (This would be calculated properly with start time tracking)
        state["processing_time"] = 0.0
        
        # Ensure required fields exist
        if not state.get("response"):
            state["response"] = "Xin lỗi, tôi không thể tạo câu trả lời cho câu hỏi này."
        
        if not state.get("sources"):
            state["sources"] = []
        
        if not state.get("follow_up_questions"):
            state["follow_up_questions"] = []
        
        logger.info(f"Workflow {state['workflow_id']} completed successfully")
        return state
    
    # =================
    # CONDITIONAL FUNCTIONS
    # =================
    
    def _routing_condition(self, state: WorkflowState) -> str:
        """Determine routing based on semantic analysis"""
        routing_decision = state.get("routing_decision", "retrieval")
        return routing_decision
    
    def _document_grading_condition(self, state: WorkflowState) -> str:
        """Determine next step based on document grading"""
        if not state.get("retrieved_documents"):
            return "tools"
        elif len(state["retrieved_documents"]) < 2:
            return "expand"
        else:
            return "good"
    
    def _hallucination_condition(self, state: WorkflowState) -> str:
        """Determine if response has hallucination"""
        check_result = state.get("hallucination_check", "good")
        return check_result
    
    # =================
    # PUBLIC INTERFACE
    # =================
    
    @log_performance()
    async def process_query(
        self,
        query: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        conversation_history: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Process RAG query through LangGraph workflow
        """
        if not self.initialized:
            raise WorkflowError("Workflow not initialized")
        
        try:
            # Prepare initial state
            initial_state = WorkflowState(
                query=query,
                user_id=user_id,
                session_id=session_id or f"session_{datetime.now().isoformat()}",
                conversation_history=conversation_history or [],
                current_step="",
                routing_decision=None,
                retrieved_documents=[],
                tool_results=[],
                response=None,
                sources=[],
                follow_up_questions=[],
                processing_time=0.0,
                tokens_used=0,
                error=None,
                workflow_id="",
                enabled_tools={},
                enabled_providers=[],
                workflow_config={}
            )
            
            # Execute workflow
            config = {"configurable": {"thread_id": initial_state["session_id"]}}
            
            final_state = await self.compiled_graph.ainvoke(
                initial_state,
                config=config
            )
            
            # Return formatted response
            return {
                "response": final_state["response"],
                "sources": final_state["sources"],
                "follow_up_questions": final_state["follow_up_questions"],
                "workflow_id": final_state["workflow_id"],
                "processing_time": final_state["processing_time"],
                "tokens_used": final_state["tokens_used"],
                "error": final_state.get("error")
            }
            
        except Exception as e:
            logger.error(f"Workflow execution failed: {e}")
            raise WorkflowError(f"Query processing failed: {e}")
    
    async def health_check(self) -> bool:
        """Check if workflow is healthy"""
        return self.initialized and self.compiled_graph is not None

# Global workflow instance
rag_workflow = RAGWorkflow()