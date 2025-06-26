from typing import Dict, Any, List, Optional, Literal, Annotated, TypedDict
from utils.datetime_utils import CustomDatetime as datetime

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.redis import RedisSaver

from services.orchestrator.orchestrator_service import OrchestratorService
from services.vector.milvus_service import milvus_service
from services.llm.provider_manager import llm_provider_manager
from services.tools.tool_manager import tool_manager
from config.settings import get_settings
from utils.logging import get_logger

logger = get_logger(__name__)

class RAGWorkflowState(TypedDict):
    """
    Complete state schema cho LangGraph RAG workflow
    """
    
    # LangGraph messages (required)
    messages: Annotated[List[BaseMessage], add_messages]
    
    # Core query data
    original_query: str
    refined_query: str
    language: str
    query_type: str  # rag_query, chitchat, action_request
    
    # User context
    user_id: str
    user_context: Dict[str, Any]
    session_id: str
    conversation_history: List[Dict[str, Any]]
    
    # Orchestration results
    orchestrator_analysis: Dict[str, Any]
    task_distribution: Dict[str, Any]
    tool_selection: Dict[str, Any]
    
    # Document retrieval
    retrieval_results: Dict[str, List[Dict[str, Any]]]
    ranked_documents: Dict[str, List[Dict[str, Any]]]
    total_documents_found: int
    
    # Agent execution
    agent_responses: Dict[str, Dict[str, Any]]
    conflict_resolution: Dict[str, Any]
    
    # Final output
    final_response: str
    evidence: List[Dict[str, Any]]
    confidence: float
    
    # Workflow control
    current_step: str
    processing_time: float
    error_message: Optional[str]
    workflow_id: str

class CompleteRAGWorkflow:
    """
    Complete RAG workflow sử dụng LangGraph và intelligent orchestration
    Implement theo đúng patterns của LangGraph
    """
    
    def __init__(self):
        self.settings = get_settings()
        self.orchestrator = OrchestratorService()
        self.graph = None
        self.checkpointer = None
        self._initialized = False
    
    async def initialize(self):
        """Initialize workflow với checkpointer và build graph"""
        try:
            # Setup checkpointer
            await self._setup_checkpointer()
            
            # Build workflow graph
            await self._build_workflow_graph()
            
            self._initialized = True
            logger.info("Complete RAG workflow initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize RAG workflow: {e}")
            raise
    
    async def _setup_checkpointer(self):
        """Setup checkpointer based on configuration"""
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
    
    async def _build_workflow_graph(self):
        """Build LangGraph workflow theo đúng specification"""
        
        # Create StateGraph với state schema
        workflow = StateGraph(RAGWorkflowState)
        
        # Add workflow nodes
        workflow.add_node("initialize_workflow", self._initialize_workflow_node)
        workflow.add_node("orchestrate_query", self._orchestrate_query_node)
        workflow.add_node("handle_chitchat", self._handle_chitchat_node)
        workflow.add_node("execute_retrieval", self._execute_retrieval_node)
        workflow.add_node("rank_documents", self._rank_documents_node)
        workflow.add_node("execute_agents", self._execute_agents_node)
        workflow.add_node("resolve_conflicts", self._resolve_conflicts_node)
        workflow.add_node("finalize_response", self._finalize_response_node)
        
        # Define workflow edges
        workflow.add_edge(START, "initialize_workflow")
        workflow.add_edge("initialize_workflow", "orchestrate_query")
        
        # Conditional routing sau orchestration
        workflow.add_conditional_edges(
            "orchestrate_query",
            self._route_after_orchestration,
            {
                "chitchat": "handle_chitchat",
                "rag_query": "execute_retrieval"
            }
        )
        
        workflow.add_edge("handle_chitchat", "finalize_response")
        workflow.add_edge("execute_retrieval", "rank_documents")
        workflow.add_edge("rank_documents", "execute_agents")
        workflow.add_edge("execute_agents", "resolve_conflicts")
        workflow.add_edge("resolve_conflicts", "finalize_response")
        workflow.add_edge("finalize_response", END)
        
        # Compile graph với checkpointer
        self.graph = workflow.compile(
            checkpointer=self.checkpointer,
            debug=self.settings.DEBUG
        )
        
        logger.info("LangGraph workflow compiled successfully")
    
    # ===== WORKFLOW NODES =====
    
    async def _initialize_workflow_node(self, state: RAGWorkflowState) -> RAGWorkflowState:
        """
        Node 1: Initialize workflow state
        """
        logger.info("🚀 Initializing RAG workflow...")
        
        workflow_id = f"rag_{datetime.now().isoformat()}_{state.get('user_id', 'anon')}"
        
        return {
            **state,
            "workflow_id": workflow_id,
            "current_step": "initialization",
            "processing_time": 0.0,
            "total_documents_found": 0,
            "agent_responses": {},
            "evidence": [],
            "confidence": 0.0,
            "error_message": None
        }
    
    async def _orchestrate_query_node(self, state: RAGWorkflowState) -> RAGWorkflowState:
        """
        Node 2: Intelligent query orchestration
        """
        logger.info("🧠 Orchestrating query with intelligent analysis...")
        
        try:
            # B1: Query Analysis
            query_analysis = await self.orchestrator._analyze_and_refine_query(
                original_query=state["original_query"],
                user_context=state["user_context"],
                conversation_history=state.get("conversation_history", [])
            )
            
            # B2: Task Distribution (only for RAG queries)
            task_distribution = None
            tool_selection = None
            
            if query_analysis.query_type.value != "chitchat":
                task_distribution = await self.orchestrator._distribute_tasks(
                    query_analysis, state["user_context"]
                )
                
                # B3: Tool Selection
                tool_selection = await self.orchestrator._select_tools(
                    query_analysis, task_distribution, state["user_context"]
                )
            
            return {
                **state,
                "refined_query": query_analysis.refined_query,
                "language": query_analysis.language,
                "query_type": query_analysis.query_type.value,
                "orchestrator_analysis": {
                    "confidence": query_analysis.confidence,
                    "reasoning": query_analysis.reasoning,
                    "conversation_context": query_analysis.conversation_context
                },
                "task_distribution": task_distribution.__dict__ if task_distribution else {},
                "tool_selection": tool_selection.__dict__ if tool_selection else {},
                "current_step": "orchestration_complete"
            }
            
        except Exception as e:
            logger.error(f"Orchestration failed: {e}")
            return {
                **state,
                "error_message": f"Orchestration failed: {str(e)}",
                "query_type": "rag_query",  # Fallback
                "refined_query": state["original_query"],
                "language": "vi"
            }
    
    async def _handle_chitchat_node(self, state: RAGWorkflowState) -> RAGWorkflowState:
        """
        Node 3A: Handle chitchat queries
        """
        logger.info("💬 Handling chitchat query...")
        
        try:
            chitchat_result = await self.orchestrator._handle_chitchat(
                query_analysis=type('obj', (object,), {
                    'refined_query': state["refined_query"],
                    'language': state["language"],
                    'query_type': type('obj', (object,), {'value': 'chitchat'})()
                })(),
                user_context=state["user_context"]
            )
            
            return {
                **state,
                "final_response": chitchat_result["response"],
                "confidence": chitchat_result["confidence"],
                "evidence": [],
                "current_step": "chitchat_complete"
            }
            
        except Exception as e:
            logger.error(f"Chitchat handling failed: {e}")
            return {
                **state,
                "final_response": "Xin lỗi, tôi không thể trả lời câu hỏi này lúc này.",
                "confidence": 0.1,
                "error_message": str(e)
            }
    
    async def _execute_retrieval_node(self, state: RAGWorkflowState) -> RAGWorkflowState:
        """
        Node 3B: Execute RAG retrieval
        """
        logger.info("🔍 Executing document retrieval...")
        
        try:
            # B4: RAG Retrieval
            task_distribution_obj = type('obj', (object,), state["task_distribution"])()
            
            retrieval_results = await self.orchestrator._execute_rag_retrieval(
                query_analysis=type('obj', (object,), {
                    'refined_query': state["refined_query"]
                })(),
                task_distribution=task_distribution_obj,
                user_context=state["user_context"]
            )
            
            total_docs = sum(len(docs) for docs in retrieval_results.values())
            
            return {
                **state,
                "retrieval_results": retrieval_results,
                "total_documents_found": total_docs,
                "current_step": "retrieval_complete"
            }
            
        except Exception as e:
            logger.error(f"Document retrieval failed: {e}")
            return {
                **state,
                "retrieval_results": {},
                "total_documents_found": 0,
                "error_message": str(e)
            }
    
    async def _rank_documents_node(self, state: RAGWorkflowState) -> RAGWorkflowState:
        """
        Node 4: Rank and evaluate documents
        """
        logger.info("📊 Ranking and evaluating documents...")
        
        try:
            # B5: Document Evaluation & Ranking
            query_analysis_obj = type('obj', (object,), {
                'refined_query': state["refined_query"]
            })()
            
            ranked_documents = await self.orchestrator._evaluate_and_rank_documents(
                retrieval_results=state["retrieval_results"],
                query_analysis=query_analysis_obj
            )
            
            return {
                **state,
                "ranked_documents": ranked_documents,
                "current_step": "ranking_complete"
            }
            
        except Exception as e:
            logger.error(f"Document ranking failed: {e}")
            return {
                **state,
                "ranked_documents": state["retrieval_results"],
                "error_message": str(e)
            }
    
    async def _execute_agents_node(self, state: RAGWorkflowState) -> RAGWorkflowState:
        """
        Node 5: Execute agents
        """
        logger.info("🤖 Executing agents...")
        
        try:
            # B6: Agent Execution
            task_distribution_obj = type('obj', (object,), state["task_distribution"])()
            tool_selection_obj = type('obj', (object,), state["tool_selection"])()
            query_analysis_obj = type('obj', (object,), {
                'language': state["language"]
            })()
            
            agent_responses = await self.orchestrator._execute_agents(
                task_distribution=task_distribution_obj,
                tool_selection=tool_selection_obj,
                ranked_documents=state["ranked_documents"],
                query_analysis=query_analysis_obj
            )
            
            return {
                **state,
                "agent_responses": agent_responses,
                "current_step": "agents_complete"
            }
            
        except Exception as e:
            logger.error(f"Agent execution failed: {e}")
            return {
                **state,
                "agent_responses": {},
                "error_message": str(e)
            }
    
    async def _resolve_conflicts_node(self, state: RAGWorkflowState) -> RAGWorkflowState:
        """
        Node 6: Resolve conflicts between agents
        """
        logger.info("⚖️ Resolving conflicts...")
        
        try:
            # B6: Conflict Resolution
            query_analysis_obj = type('obj', (object,), {
                'refined_query': state["refined_query"]
            })()
            
            conflict_resolution = await self.orchestrator._resolve_conflicts(
                agent_responses=state["agent_responses"],
                query_analysis=query_analysis_obj
            )
            
            return {
                **state,
                "conflict_resolution": conflict_resolution.__dict__,
                "current_step": "conflicts_resolved"
            }
            
        except Exception as e:
            logger.error(f"Conflict resolution failed: {e}")
            return {
                **state,
                "conflict_resolution": {},
                "error_message": str(e)
            }
    
    async def _finalize_response_node(self, state: RAGWorkflowState) -> RAGWorkflowState:
        """
        Node 7: Finalize response với evidence
        """
        logger.info("📝 Finalizing response...")
        
        try:
            # For chitchat, response is already finalized
            if state["query_type"] == "chitchat":
                return {
                    **state,
                    "current_step": "workflow_complete"
                }
            
            # B7: Final Response Assembly
            conflict_resolution_obj = type('obj', (object,), state["conflict_resolution"])()
            query_analysis_obj = type('obj', (object,), {
                'language': state["language"]
            })()
            
            final_result = await self.orchestrator._assemble_final_response(
                conflict_resolution=conflict_resolution_obj,
                ranked_documents=state["ranked_documents"],
                query_analysis=query_analysis_obj
            )
            
            return {
                **state,
                "final_response": final_result["response"],
                "evidence": final_result["evidence"],
                "confidence": final_result["confidence"],
                "current_step": "workflow_complete",
                "processing_time": (datetime.now().timestamp() - state.get("start_time", datetime.now().timestamp()))
            }
            
        except Exception as e:
            logger.error(f"Response finalization failed: {e}")
            return {
                **state,
                "final_response": "Xin lỗi, đã có lỗi xảy ra trong quá trình xử lý.",
                "confidence": 0.1,
                "evidence": [],
                "error_message": str(e)
            }
    
    # ===== ROUTING FUNCTIONS =====
    
    def _route_after_orchestration(self, state: RAGWorkflowState) -> Literal["chitchat", "rag_query"]:
        """Route sau orchestration based on query type"""
        query_type = state.get("query_type", "rag_query")
        
        if query_type == "chitchat":
            return "chitchat"
        else:
            return "rag_query"
    
    # ===== MAIN EXECUTION METHOD =====
    
    async def process_query(
        self,
        query: str,
        user_id: str,
        user_context: Dict[str, Any],
        conversation_history: Optional[List[Dict[str, Any]]] = None,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Main method để process RAG query through complete workflow
        
        Args:
            query: User query
            user_id: User ID
            user_context: User context với permissions
            conversation_history: Previous conversation
            session_id: Session ID cho checkpointing
            
        Returns:
            Complete response với evidence
        """
        
        if not self._initialized:
            await self.initialize()
        
        # Create initial state
        initial_state = RAGWorkflowState(
            messages=[HumanMessage(content=query)],
            original_query=query,
            refined_query=query,
            language="vi",
            query_type="rag_query",
            user_id=user_id,
            user_context=user_context,
            session_id=session_id or f"session_{datetime.now().isoformat()}",
            conversation_history=conversation_history or [],
            orchestrator_analysis={},
            task_distribution={},
            tool_selection={},
            retrieval_results={},
            ranked_documents={},
            total_documents_found=0,
            agent_responses={},
            conflict_resolution={},
            final_response="",
            evidence=[],
            confidence=0.0,
            current_step="start",
            processing_time=0.0,
            error_message=None,
            workflow_id=""
        )
        
        # Add start time for performance tracking
        initial_state["start_time"] = datetime.now().timestamp()
        
        try:
            # Execute workflow với checkpointing
            config = {"configurable": {"thread_id": initial_state["session_id"]}}
            
            final_state = await self.graph.ainvoke(initial_state, config=config)
            
            # Return formatted result
            return {
                "response": final_state["final_response"],
                "evidence": final_state["evidence"],
                "confidence": final_state["confidence"],
                "language": final_state["language"],
                "workflow_id": final_state["workflow_id"],
                "processing_time": final_state["processing_time"],
                "metadata": {
                    "query_type": final_state["query_type"],
                    "total_documents": final_state["total_documents_found"],
                    "agents_used": list(final_state["agent_responses"].keys()),
                    "orchestrator_confidence": final_state.get("orchestrator_analysis", {}).get("confidence", 0.0),
                    "error_message": final_state.get("error_message"),
                    "workflow_steps": final_state["current_step"]
                }
            }
            
        except Exception as e:
            logger.error(f"Workflow execution failed: {e}")
            return {
                "response": "Xin lỗi, đã có lỗi xảy ra trong quá trình xử lý câu hỏi.",
                "evidence": [],
                "confidence": 0.1,
                "language": "vi",
                "workflow_id": initial_state.get("workflow_id", "unknown"),
                "processing_time": 0.0,
                "metadata": {
                    "error": str(e),
                    "query_type": "error"
                }
            }
    
    async def stream_process_query(
        self,
        query: str,
        user_id: str,
        user_context: Dict[str, Any],
        conversation_history: Optional[List[Dict[str, Any]]] = None,
        session_id: Optional[str] = None
    ):
        """
        Stream version của process_query cho real-time updates
        
        Yields workflow state updates as they happen
        """
        
        if not self._initialized:
            await self.initialize()
        
        # Create initial state
        initial_state = RAGWorkflowState(
            messages=[HumanMessage(content=query)],
            original_query=query,
            refined_query=query,
            language="vi",
            query_type="rag_query",
            user_id=user_id,
            user_context=user_context,
            session_id=session_id or f"session_{datetime.now().isoformat()}",
            conversation_history=conversation_history or [],
            orchestrator_analysis={},
            task_distribution={},
            tool_selection={},
            retrieval_results={},
            ranked_documents={},
            total_documents_found=0,
            agent_responses={},
            conflict_resolution={},
            final_response="",
            evidence=[],
            confidence=0.0,
            current_step="start",
            processing_time=0.0,
            error_message=None,
            workflow_id=""
        )
        
        initial_state["start_time"] = datetime.now().timestamp()
        
        try:
            config = {"configurable": {"thread_id": initial_state["session_id"]}}
            
            # Stream workflow execution
            async for state_update in self.graph.astream(initial_state, config=config):
                # Extract current step và state
                current_step = list(state_update.keys())[0] if state_update else "unknown"
                current_state = list(state_update.values())[0] if state_update else {}
                
                # Yield formatted update
                yield {
                    "step": current_step,
                    "progress": self._calculate_progress(current_step),
                    "state": {
                        "current_step": current_state.get("current_step", current_step),
                        "refined_query": current_state.get("refined_query"),
                        "query_type": current_state.get("query_type"),
                        "total_documents_found": current_state.get("total_documents_found", 0),
                        "agents_active": list(current_state.get("agent_responses", {}).keys()),
                        "confidence": current_state.get("confidence", 0.0),
                        "error_message": current_state.get("error_message")
                    },
                    "timestamp": datetime.now().isoformat()
                }
            
        except Exception as e:
            logger.error(f"Stream workflow execution failed: {e}")
            yield {
                "step": "error",
                "progress": 0.0,
                "state": {
                    "error_message": str(e),
                    "current_step": "failed"
                },
                "timestamp": datetime.now().isoformat()
            }
    
    def _calculate_progress(self, step: str) -> float:
        """Calculate workflow progress based on current step"""
        step_progress = {
            "initialize_workflow": 0.1,
            "orchestrate_query": 0.2,
            "handle_chitchat": 0.9, 
            "execute_retrieval": 0.4,
            "rank_documents": 0.5,
            "execute_agents": 0.7,
            "resolve_conflicts": 0.8,
            "finalize_response": 0.9,
            "workflow_complete": 1.0
        }
        
        return step_progress.get(step, 0.0)
    
    async def health_check(self) -> bool:
        """Check workflow health"""
        try:
            return self._initialized and self.graph is not None
        except Exception:
            return False
    
    async def get_workflow_status(self) -> Dict[str, Any]:
        """Get current workflow status"""
        return {
            "initialized": self._initialized,
            "graph_compiled": self.graph is not None,
            "checkpointer_type": type(self.checkpointer).__name__ if self.checkpointer else None,
            "orchestrator_available": True,
            "supported_languages": ["vi", "en", "ja", "ko"],
            "workflow_steps": [
                "initialize_workflow",
                "orchestrate_query", 
                "handle_chitchat",
                "execute_retrieval",
                "rank_documents",
                "execute_agents",
                "resolve_conflicts",
                "finalize_response"
            ]
        }

# ===== WORKFLOW VISUALIZATION =====

def create_workflow_visualization():
    """
    Create workflow visualization cho documentation
    """
    
    workflow_steps = {
        "START": "Bắt đầu workflow",
        "initialize_workflow": "Khởi tạo workflow state",
        "orchestrate_query": "Phân tích và điều phối query",
        "handle_chitchat": "Xử lý chitchat (nếu cần)",
        "execute_retrieval": "Tìm kiếm documents",
        "rank_documents": "Đánh giá và xếp hạng documents",
        "execute_agents": "Thực hiện agents",
        "resolve_conflicts": "Giải quyết conflicts",
        "finalize_response": "Hoàn thiện response",
        "END": "Kết thúc workflow"
    }
    
    workflow_flow = """
    START 
      ↓
    initialize_workflow
      ↓
    orchestrate_query
      ↓
    ┌─────────────────┐
    ↓                 ↓
    handle_chitchat   execute_retrieval
    ↓                 ↓
    ↓                 rank_documents
    ↓                 ↓
    ↓                 execute_agents
    ↓                 ↓
    ↓                 resolve_conflicts
    ↓                 ↓
    └──→ finalize_response ←──┘
      ↓
    END
    """
    
    return {
        "steps": workflow_steps,
        "flow": workflow_flow,
        "description": "Complete LangGraph RAG workflow với intelligent orchestration"
    }

# ===== GLOBAL INSTANCE =====

rag_workflow = CompleteRAGWorkflow()

# ===== EXPORT =====

__all__ = [
    "CompleteRAGWorkflow",
    "RAGWorkflowState", 
    "complete_rag_workflow",
    "create_workflow_visualization"
]