from typing import Dict, Any, List
from utils.datetime_utils import CustomDateTime as datetime
import asyncio
from langgraph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from workflows.state.workflow_state import RAGWorkflowState, ProcessingStatus, QueryDomain
from workflows.langgraph.nodes.analysis_nodes import QueryAnalysisNode
from workflows.langgraph.nodes.permission_nodes import PermissionCheckNode
from workflows.langgraph.nodes.retrieval_nodes import RetrievalNode
from workflows.langgraph.nodes.synthesis_nodes import SynthesisNode
from workflows.langgraph.nodes.security_nodes import SecurityGateNode
from workflows.langgraph.edges.routing_edges import RoutingEdge
from workflows.langgraph.edges.condition_edges import ConditionEdge

from services.auth.permission_service import PermissionService
from services.tools.tool_manager import ToolManager
from services.vector.milvus_service import MilvusService
from services.embedding.embedding_service import EmbeddingService
from core.exceptions import WorkflowError, PermissionDeniedError


class RAGWorkflowOrchestrator:
    """
    Core LangGraph workflow orchestrator cho Agentic RAG system
    Quản lý toàn bộ flow từ query analysis đến response synthesis với permission control
    """
    
    def __init__(
        self,
        permission_service: PermissionService,
        tool_manager: ToolManager,
        milvus_service: MilvusService,
        embedding_service: EmbeddingService
    ):
        self.permission_service = permission_service
        self.tool_manager = tool_manager
        self.milvus_service = milvus_service
        self.embedding_service = embedding_service
        
        # Initialize workflow components
        self.query_analysis_node = QueryAnalysisNode(embedding_service)
        self.permission_check_node = PermissionCheckNode(permission_service)
        self.retrieval_node = RetrievalNode(milvus_service, permission_service)
        self.synthesis_node = SynthesisNode(tool_manager, permission_service)
        self.security_gate_node = SecurityGateNode(permission_service)
        
        # Initialize routing logic
        self.routing_edge = RoutingEdge()
        self.condition_edge = ConditionEdge()
        
        # Build workflow graph
        self.workflow = self._build_workflow_graph()
    
    def _build_workflow_graph(self) -> StateGraph:
        """
        Build LangGraph workflow với permission-aware nodes và edges
        """
        # Create state graph
        workflow = StateGraph(RAGWorkflowState)
        
        # Add nodes
        workflow.add_node("query_analysis", self._query_analysis_step)
        workflow.add_node("permission_check", self._permission_check_step)
        workflow.add_node("access_scope_determination", self._access_scope_step)
        workflow.add_node("route_decision", self._route_decision_step)
        workflow.add_node("single_agent_retrieval", self._single_agent_retrieval_step)
        workflow.add_node("multi_agent_retrieval", self._multi_agent_retrieval_step)
        workflow.add_node("tool_invocation", self._tool_invocation_step)
        workflow.add_node("cross_department_handling", self._cross_department_step)
        workflow.add_node("security_gate", self._security_gate_step)
        workflow.add_node("response_synthesis", self._response_synthesis_step)
        workflow.add_node("content_sanitization", self._content_sanitization_step)
        workflow.add_node("final_synthesis", self._final_synthesis_step)
        workflow.add_node("audit_logging", self._audit_logging_step)
        
        workflow.set_entry_point("query_analysis")
        
        workflow.add_edge("query_analysis", "permission_check")
        workflow.add_edge("permission_check", "access_scope_determination")
        workflow.add_edge("access_scope_determination", "route_decision")
        
        workflow.add_conditional_edges(
            "route_decision",
            self._route_condition,
            {
                "single_agent": "single_agent_retrieval",
                "multi_agent": "multi_agent_retrieval",
                "cross_department": "cross_department_handling",
                "permission_denied": END
            }
        )
        
        workflow.add_edge("single_agent_retrieval", "tool_invocation")
        workflow.add_edge("multi_agent_retrieval", "tool_invocation")
        workflow.add_edge("cross_department_handling", "tool_invocation")
        workflow.add_edge("tool_invocation", "security_gate")
        workflow.add_edge("security_gate", "response_synthesis")
        workflow.add_edge("response_synthesis", "content_sanitization")
        workflow.add_edge("content_sanitization", "final_synthesis")
        workflow.add_edge("final_synthesis", "audit_logging")
        workflow.add_edge("audit_logging", END)
        
        return workflow
    
    async def execute_workflow(
        self, 
        query: str, 
        user_id: str, 
        tenant_id: str,
        session_id: str = None
    ) -> RAGWorkflowState:
        """
        Execute complete RAG workflow với permission control
        """
        # Initialize state
        initial_state = RAGWorkflowState(
            query=query,
            original_query=query,
            user_id=user_id,
            tenant_id=tenant_id,
            session_id=session_id or f"session_{datetime.now().isoformat()}",
            timestamp=datetime.now(),
            user_context={},
            user_permissions=[],
            user_department="",
            user_role="",
            accessible_collections=[],
            max_access_level=None,
            domain_classification=[],
            query_complexity=0.0,
            intent_analysis={},
            requires_cross_department=False,
            estimated_processing_time=0.0,
            available_tools=[],
            enabled_tools=[],
            tool_permissions={},
            selected_tools=[],
            raw_retrieval_results={},
            filtered_retrieval_results={},
            permission_filtered_count=0,
            total_documents_found=0,
            relevance_scores={},
            router_decision={},
            domain_agent_responses={},
            tool_agent_outputs={},
            cross_references=[],
            raw_synthesis="",
            sanitized_content="",
            redacted_sections=[],
            final_response="",
            response_metadata={},
            confidence_scores={},
            quality_metrics={},
            factual_consistency_score=0.0,
            relevance_score=0.0,
            access_audit_trail=[],
            security_violations=[],
            redacted_content_log=[],
            permission_checks=[],
            current_stage="initialization",
            processing_status=ProcessingStatus.PENDING,
            error_messages=[],
            warnings=[],
            retry_count=0,
            stage_timestamps={},
            processing_duration={},
            total_processing_time=0.0,
            cache_hits={}
        )
        
        try:
            # Compile workflow với memory saver
            memory = MemorySaver()
            compiled_workflow = self.workflow.compile(checkpointer=memory)
            
            # Execute workflow
            config = {"configurable": {"thread_id": session_id}}
            final_state = await compiled_workflow.ainvoke(initial_state, config=config)
            
            # Calculate total processing time
            start_time = final_state.get('stage_timestamps', {}).get('query_analysis')
            end_time = datetime.now()
            if start_time:
                total_time = (end_time - start_time).total_seconds()
                final_state['total_processing_time'] = total_time
            
            final_state['processing_status'] = ProcessingStatus.COMPLETED
            
            # Create comprehensive audit entry
            await self.permission_service.create_access_audit_entry(
                user_id=final_state['user_id'],
                action="RAG_WORKFLOW_COMPLETED",
                resource_type="workflow",
                resource_id=final_state['session_id'],
                access_granted=True,
                additional_data={
                    "query": final_state['original_query'],
                    "domains": [d.value for d in final_state['domain_classification']],
                    "collections_accessed": final_state['accessible_collections'],
                    "tools_used": final_state['selected_tools'],
                    "processing_duration": final_state['processing_duration'],
                    "total_processing_time": final_state.get('total_processing_time', 0),
                    "documents_retrieved": final_state['total_documents_found'],
                    "permission_filtered": final_state['permission_filtered_count'],
                    "security_violations": len(final_state['security_violations']),
                    "confidence_score": final_state.get('relevance_score', 0),
                    "response_length": len(final_state.get('final_response', '')),
                    "cache_hits": final_state.get('cache_hits', {})
                }
            )
            
            # Update access trail
            final_state['access_audit_trail'].append({
                "timestamp": datetime.now(),
                "action": "workflow_completed",
                "user_id": final_state['user_id'],
                "session_id": final_state['session_id'],
                "success": True
            })
            
            return final_state
            
        except PermissionDeniedError as e:
            initial_state['processing_status'] = ProcessingStatus.PERMISSION_DENIED
            initial_state['error_messages'].append(str(e))
            return initial_state
            
        except Exception as e:
            initial_state['processing_status'] = ProcessingStatus.FAILED
            initial_state['error_messages'].append(str(e))
            return initial_state
    
    # Workflow step implementations
    
    async def _query_analysis_step(self, state: RAGWorkflowState) -> RAGWorkflowState:
        """
        Giai đoạn 1: Phân tích query và xác định intent
        """
        state['current_stage'] = "query_analysis"
        state['stage_timestamps']['query_analysis'] = datetime.now()
        
        start_time = datetime.now()
        
        # Analyze query intent và domain
        analysis_result = await self.query_analysis_node.analyze_query(
            state['query'], 
            state['user_id']
        )
        
        # Update state với analysis results
        state['domain_classification'] = analysis_result['domains']
        state['query_complexity'] = analysis_result['complexity']
        state['intent_analysis'] = analysis_result['intent']
        state['requires_cross_department'] = analysis_result['cross_department']
        state['estimated_processing_time'] = analysis_result['estimated_time']
        
        # Record processing time
        processing_time = (datetime.now() - start_time).total_seconds()
        state['processing_duration']['query_analysis'] = processing_time
        
        return state
    
    async def _permission_check_step(self, state: RAGWorkflowState) -> RAGWorkflowState:
        """
        Giai đoạn 2: Kiểm tra permissions và user context
        """
        state['current_stage'] = "permission_check"
        state['stage_timestamps']['permission_check'] = datetime.now()
        
        start_time = datetime.now()
        
        # Get user context và permissions
        permission_result = await self.permission_check_node.check_permissions(
            state['user_id'],
            state['tenant_id']
        )
        
        # Update state với permission info
        state['user_context'] = permission_result['user_context']
        state['user_permissions'] = permission_result['permissions']
        state['user_department'] = permission_result['department']
        state['user_role'] = permission_result['role']
        state['max_access_level'] = permission_result['max_access_level']
        
        # Record permission checks
        state['permission_checks'].extend(permission_result['checks'])
        
        processing_time = (datetime.now() - start_time).total_seconds()
        state['processing_duration']['permission_check'] = processing_time
        
        return state
    
    async def _access_scope_step(self, state: RAGWorkflowState) -> RAGWorkflowState:
        """
        Giai đoạn 3: Xác định phạm vi collections có thể truy cập
        """
        state['current_stage'] = "access_scope_determination"
        state['stage_timestamps']['access_scope_determination'] = datetime.now()
        
        start_time = datetime.now()
        
        # Get accessible collections
        accessible_collections = await self.permission_service.get_accessible_collections(
            state['user_id']
        )
        state['accessible_collections'] = accessible_collections
        
        # Get available tools
        available_tools = await self.tool_manager.get_available_tools_for_user(
            state['user_id']
        )
        state['available_tools'] = [tool['tool_id'] for tool in available_tools]
        state['tool_permissions'] = {
            tool['tool_id']: tool['required_permissions'] 
            for tool in available_tools
        }
        
        processing_time = (datetime.now() - start_time).total_seconds()
        state['processing_duration']['access_scope_determination'] = processing_time
        
        return state
    
    async def _route_decision_step(self, state: RAGWorkflowState) -> RAGWorkflowState:
        """
        Giai đoạn 4: Quyết định routing strategy
        """
        state['current_stage'] = "route_decision"
        state['stage_timestamps']['route_decision'] = datetime.now()
        
        start_time = datetime.now()
        
        # Make routing decision
        routing_decision = await self.routing_edge.decide_route(state)
        state['router_decision'] = routing_decision
        
        processing_time = (datetime.now() - start_time).total_seconds()
        state['processing_duration']['route_decision'] = processing_time
        
        return state
    
    async def _single_agent_retrieval_step(self, state: RAGWorkflowState) -> RAGWorkflowState:
        """
        Single agent retrieval cho simple queries
        """
        state['current_stage'] = "single_agent_retrieval"
        state['stage_timestamps']['single_agent_retrieval'] = datetime.now()
        
        start_time = datetime.now()
        
        retrieval_result = await self.retrieval_node.single_agent_retrieval(state)
        
        state['raw_retrieval_results'] = retrieval_result['raw_results']
        state['filtered_retrieval_results'] = retrieval_result['filtered_results']
        state['permission_filtered_count'] = retrieval_result['filtered_count']
        state['total_documents_found'] = retrieval_result['total_found']
        state['relevance_scores'] = retrieval_result['relevance_scores']
        
        processing_time = (datetime.now() - start_time).total_seconds()
        state['processing_duration']['single_agent_retrieval'] = processing_time
        
        return state
    
    async def _multi_agent_retrieval_step(self, state: RAGWorkflowState) -> RAGWorkflowState:
        """
        Multi-agent retrieval cho complex queries
        """
        state['current_stage'] = "multi_agent_retrieval"
        state['stage_timestamps']['multi_agent_retrieval'] = datetime.now()
        
        start_time = datetime.now()
        
        retrieval_result = await self.retrieval_node.multi_agent_retrieval(state)
        
        state['raw_retrieval_results'] = retrieval_result['raw_results']
        state['filtered_retrieval_results'] = retrieval_result['filtered_results']
        state['domain_agent_responses'] = retrieval_result['agent_responses']
        state['cross_references'] = retrieval_result['cross_references']
        
        processing_time = (datetime.now() - start_time).total_seconds()
        state['processing_duration']['multi_agent_retrieval'] = processing_time
        
        return state
    
    async def _cross_department_step(self, state: RAGWorkflowState) -> RAGWorkflowState:
        """
        Cross-department query handling với enhanced permission checking
        """
        state['current_stage'] = "cross_department_handling"
        state['stage_timestamps']['cross_department_handling'] = datetime.now()
        
        start_time = datetime.now()
        
        cross_dept_result = await self.retrieval_node.cross_department_retrieval(state)
        
        state['raw_retrieval_results'] = cross_dept_result['raw_results']
        state['filtered_retrieval_results'] = cross_dept_result['filtered_results']
        state['domain_agent_responses'] = cross_dept_result['agent_responses']
        state['permission_filtered_count'] = cross_dept_result['filtered_count']
        
        processing_time = (datetime.now() - start_time).total_seconds()
        state['processing_duration']['cross_department_handling'] = processing_time
        
        return state
    
    async def _tool_invocation_step(self, state: RAGWorkflowState) -> RAGWorkflowState:
        """
        Tool invocation với permission checking
        """
        state['current_stage'] = "tool_invocation"
        state['stage_timestamps']['tool_invocation'] = datetime.now()
        
        start_time = datetime.now()
        
        # Select appropriate tools
        selected_tools = await self._select_tools_for_query(state)
        state['selected_tools'] = selected_tools
        
        # Execute tools
        tool_outputs = {}
        for tool_id in selected_tools:
            try:
                output = await self.tool_manager.execute_tool(
                    tool_id=tool_id,
                    user_id=state['user_id'],
                    method_name="process",
                    parameters={
                        "query": state['query'],
                        "retrieval_results": state['filtered_retrieval_results'],
                        "user_context": state['user_context']
                    },
                    context={"workflow_stage": "tool_invocation"}
                )
                tool_outputs[tool_id] = output
            except Exception as e:
                state['warnings'].append(f"Tool {tool_id} failed: {str(e)}")
        
        state['tool_agent_outputs'] = tool_outputs
        
        processing_time = (datetime.now() - start_time).total_seconds()
        state['processing_duration']['tool_invocation'] = processing_time
        
        return state
    
    async def _security_gate_step(self, state: RAGWorkflowState) -> RAGWorkflowState:
        """
        Security gate để validate content trước synthesis
        """
        state['current_stage'] = "security_gate"
        state['stage_timestamps']['security_gate'] = datetime.now()
        
        start_time = datetime.now()
        
        security_result = await self.security_gate_node.validate_content(state)
        
        if not security_result['passed']:
            state['security_violations'].extend(security_result['violations'])
            state['warnings'].extend(security_result['warnings'])
        
        processing_time = (datetime.now() - start_time).total_seconds()
        state['processing_duration']['security_gate'] = processing_time
        
        return state
    
    async def _response_synthesis_step(self, state: RAGWorkflowState) -> RAGWorkflowState:
        """
        Response synthesis từ retrieval results và tool outputs
        """
        state['current_stage'] = "response_synthesis"
        state['stage_timestamps']['response_synthesis'] = datetime.now()
        
        start_time = datetime.now()
        
        synthesis_result = await self.synthesis_node.synthesize_response(state)
        
        state['raw_synthesis'] = synthesis_result['raw_response']
        state['confidence_scores'] = synthesis_result['confidence_scores']
        state['quality_metrics'] = synthesis_result['quality_metrics']
        
        processing_time = (datetime.now() - start_time).total_seconds()
        state['processing_duration']['response_synthesis'] = processing_time
        
        return state
    
    async def _content_sanitization_step(self, state: RAGWorkflowState) -> RAGWorkflowState:
        """
        Content sanitization để remove sensitive information
        """
        state['current_stage'] = "content_sanitization"
        state['stage_timestamps']['content_sanitization'] = datetime.now()
        
        start_time = datetime.now()
        
        sanitization_result = await self.security_gate_node.sanitize_content(
            state['raw_synthesis'],
            state['user_context'],
            state['user_permissions']
        )
        
        state['sanitized_content'] = sanitization_result['sanitized_content']
        state['redacted_sections'] = sanitization_result['redacted_sections']
        state['redacted_content_log'] = sanitization_result['redaction_log']
        
        processing_time = (datetime.now() - start_time).total_seconds()
        state['processing_duration']['content_sanitization'] = processing_time
        
        return state
    
    async def _final_synthesis_step(self, state: RAGWorkflowState) -> RAGWorkflowState:
        """
        Final response synthesis với formatting
        """
        state['current_stage'] = "final_synthesis"
        state['stage_timestamps']['final_synthesis'] = datetime.now()
        
        start_time = datetime.now()
        
        final_result = await self.synthesis_node.finalize_response(state)
        
        state['final_response'] = final_result['final_response']
        state['response_metadata'] = final_result['metadata']
        state['factual_consistency_score'] = final_result['consistency_score']
        state['relevance_score'] = final_result['relevance_score']
        
        processing_time = (datetime.now() - start_time).total_seconds()
        state['processing_duration']['final_synthesis'] = processing_time
        
        return state
    
    async def _audit_logging_step(self, state: RAGWorkflowState) -> RAGWorkflowState:
        """
        Final audit logging
        """
        state['current_stage'] = "audit_logging"
        state['stage_timestamps']['audit_logging'] = datetime.now()
        
        await self.permission_service.create_access_audit_entry(
            user_id=state['user_id'],
            action="RAG_WORKFLOW_COMPLETED",
            resource_type="workflow",
            resource_id=state['session_id'],
            access_granted=True,
            additional_data={
                "query": state['original_query'],
                "domains": [d.value for d in state['domain_classification']],
                "collections_accessed": state['accessible_collections'],
                "tools_used": state['selected_tools'],
                "processing_duration": state['processing_duration'],
                "total_processing_time": state.get('total_processing_time', 0),
                "documents_retrieved": state['total_documents_found'],
                "permission_filtered": state['permission_filtered_count'],
                "security_violations": len(state['security_violations']),
                "confidence_score": state.get('relevance_score', 0),
                "response_length": len(state.get('final_response', '')),
                "cache_hits": state.get('cache_hits', {})
            }
        )
        
        state['access_audit_trail'].append({
            "timestamp": datetime.now(),
            "action": "workflow_completed",
            "user_id": state['user_id'],
            "session_id": state['session_id'],
            "success": True
        })
        
        return state
    
    
    def _route_condition(self, state: RAGWorkflowState) -> str:
        """
        Conditional routing logic dựa trên query complexity và permissions
        """
        if not state['accessible_collections']:
            return "permission_denied"
        
        if state['requires_cross_department']:
            return "cross_department"
        
        domain_count = len(state['domain_classification'])
        complexity = state['query_complexity']
        
        if domain_count > 1 or complexity > 0.7:
            return "multi_agent"
        else:
            return "single_agent"
    
    async def _select_tools_for_query(self, state: RAGWorkflowState) -> List[str]:
        """
        Select appropriate tools dựa trên query intent và user permissions
        """
        selected_tools = []
        
        for tool_id in state['available_tools']:
            required_perms = state['tool_permissions'].get(tool_id, [])
            user_perms = state['user_permissions']
            
            has_permission = all(perm in user_perms for perm in required_perms)
            
            if has_permission:
                tool_relevance = await self._check_tool_relevance(
                    tool_id, 
                    state['domain_classification']
                )
                
                if tool_relevance > 0.5:
                    selected_tools.append(tool_id)
        
        max_tools = 3
        if len(selected_tools) > max_tools:
            tool_scores = {}
            for tool_id in selected_tools:
                tool_scores[tool_id] = await self._calculate_tool_score(
                    tool_id, 
                    state
                )
            
            selected_tools = sorted(
                selected_tools, 
                key=lambda x: tool_scores[x], 
                reverse=True
            )[:max_tools]
        
        return selected_tools
    
    async def _check_tool_relevance(
        self, 
        tool_id: str, 
        domains: List[QueryDomain]
    ) -> float:
        """
        Check relevance của tool cho specific domains
        """
        tool_metadata = await self.tool_manager.get_tool_metadata(tool_id)
        tool_domains = tool_metadata.get('supported_domains', [])
        
        if not tool_domains:
            return 0.5 
        
        domain_values = [d.value for d in domains]
        overlap = len(set(tool_domains) & set(domain_values))
        total_domains = len(set(tool_domains) | set(domain_values))
        
        return overlap / total_domains if total_domains > 0 else 0.0
    
    async def _calculate_tool_score(
        self, 
        tool_id: str, 
        state: RAGWorkflowState
    ) -> float:
        """
        Calculate comprehensive score cho tool selection
        """
        relevance_score = await self._check_tool_relevance(
            tool_id, 
            state['domain_classification']
        )
        
        performance_score = await self.tool_manager.get_tool_performance_score(tool_id)
        
        user_pref_score = await self._get_user_tool_preference_score(
            state['user_id'], 
            tool_id
        )
        
        final_score = (
            relevance_score * 0.5 +
            performance_score * 0.3 +
            user_pref_score * 0.2
        )
        
        return final_score
    
    async def _get_user_tool_preference_score(
        self, 
        user_id: str, 
        tool_id: str
    ) -> float:
        """
        Get user's historical preference score cho specific tool
        """
        return 0.5
    
    async def get_workflow_status(self, session_id: str) -> Dict[str, Any]:
        """
        Get current status của workflow session
        """
        return {
            "session_id": session_id,
            "status": "unknown",
            "message": "Status checking not yet implemented"
        }
    
    async def cancel_workflow(self, session_id: str) -> bool:
        """
        Cancel running workflow
        """
        return False
    
    def get_workflow_metrics(self) -> Dict[str, Any]:
        """
        Get workflow performance metrics
        """
        return {
            "total_workflows_executed": 0,
            "average_processing_time": 0.0,
            "success_rate": 0.0,
            "common_failure_reasons": [],
            "performance_by_stage": {}
        }