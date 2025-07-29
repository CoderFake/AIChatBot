from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from enum import Enum
import json
import asyncio

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from services.llm.provider_manager import llm_provider_manager
from services.types import QueryType, ExecutionStrategy
from services.dataclasses.orchestrator import QueryAnalysis, TaskDistribution, ToolSelection, ConflictResolution
from services.tools.tool_manager import tool_manager
from services.vector.milvus_service import milvus_service
from services.auth.permission_service import PermissionService
from agents.domain.hr_agent import HRSpecialistAgent
from agents.domain.finance_agent import FinanceSpecialistAgent
from agents.domain.it_agent import ITSpecialistAgent
from agents.domain.general_agent import GeneralAgent
from config.settings import get_settings
from utils.logging import get_logger

logger = get_logger(__name__)

class OrchestratorService:
    """
    Service điều phối thông minh cho Agentic RAG
    Sử dụng LLM để đưa ra quyết định, không hardcode
    """
    
    def __init__(self, db_session=None):
        self.settings = get_settings()
        self._conversation_memory: Dict[str, List[Dict]] = {}
        self.permission_service = PermissionService(db_session) if db_session else None
        
        # Initialize domain agents
        self.agents = {
            "hr_specialist": HRSpecialistAgent(),
            "finance_specialist": FinanceSpecialistAgent(),
            "it_specialist": ITSpecialistAgent(),
            "general_assistant": GeneralAgent()
        }
        
    async def orchestrate_complete_flow(
        self,
        original_query: str,
        user_context: Dict[str, Any],
        conversation_history: List[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Orchestrate toàn bộ luồng xử lý RAG
        """
        logger.info(f"🎯 Starting orchestration for: {original_query[:100]}...")
        
        try:
            query_analysis = await self._analyze_and_refine_query(
                original_query, user_context, conversation_history
            )
            
            if query_analysis.query_type == QueryType.CHITCHAT:
                return await self._handle_chitchat(query_analysis, user_context)
            
            task_distribution = await self._distribute_tasks(query_analysis, user_context)
            
            tool_selection = await self._select_tools(
                query_analysis, task_distribution, user_context
            )
            
            retrieval_results = await self._execute_rag_retrieval(
                query_analysis, task_distribution, user_context
            )
            
            ranked_documents = await self._evaluate_and_rank_documents(
                retrieval_results, query_analysis
            )
            
            agent_responses = await self._execute_agents(
                task_distribution, tool_selection, ranked_documents, query_analysis
            )
            
            conflict_resolution = await self._resolve_conflicts(agent_responses, query_analysis)
            
            final_response = await self._assemble_final_response(
                conflict_resolution, ranked_documents, query_analysis
            )
            
            return final_response
            
        except Exception as e:
            logger.error(f"Orchestration failed: {e}")
            return {
                "response": f"Xin lỗi, đã có lỗi xảy ra: {str(e)}",
                "evidence": [],
                "confidence": 0.1,
                "language": user_context.get("language", "vi"),
                "metadata": {"error": str(e)}
            }
    
    async def _analyze_and_refine_query(
        self,
        original_query: str,
        user_context: Dict[str, Any],
        conversation_history: List[Dict[str, Any]] = None
    ) -> QueryAnalysis:
        """
        B1: Phân tích và tinh chỉnh query sử dụng LLM
        """
        logger.info("Analyzing and refining query...")
        
        try:
            llm = await llm_provider_manager.get_provider()
            
            conversation_context = ""
            if conversation_history:
                recent_turns = conversation_history[-3:]
                conversation_context = "\n".join([
                    f"User: {turn.get('user_message', '')}\nBot: {turn.get('bot_response', '')}"
                    for turn in recent_turns
                ])
            
            analysis_prompt = f"""
Bạn là AI Assistant chuyên phân tích query. Phân tích câu hỏi sau:

Câu hỏi gốc: "{original_query}"

Ngữ cảnh hội thoại gần đây:
{conversation_context if conversation_context else "Không có lịch sử hội thoại"}

User context:
- Department: {user_context.get('department', 'unknown')}
- Role: {user_context.get('role', 'user')}
- Language preference: {user_context.get('language', 'vi')}

Nhiệm vụ:
1. Xác định ngôn ngữ chính của câu hỏi
2. Tinh chỉnh câu hỏi để rõ ràng hơn (dựa vào context)
3. Phân loại loại query: rag_query, chitchat, action_request, clarification
4. Đánh giá mức độ tin cậy của phân tích

Trả về JSON:
{{
    "refined_query": "câu hỏi đã được tinh chỉnh",
    "query_type": "rag_query|chitchat|action_request|clarification",
    "language": "vi|en|ja|ko",
    "confidence": 0.85,
    "reasoning": "lý do phân tích",
    "conversation_context": {{
        "refers_to_previous": true,
        "context_summary": "tóm tắt ngữ cảnh liên quan"
    }}
}}
"""
            
            response = await llm.ainvoke(analysis_prompt)
            analysis_data = self._parse_json_response(response.content)
            
            return QueryAnalysis(
                refined_query=analysis_data.get("refined_query", original_query),
                query_type=QueryType(analysis_data.get("query_type", "rag_query")),
                language=analysis_data.get("language", "vi"),
                confidence=analysis_data.get("confidence", 0.5),
                reasoning=analysis_data.get("reasoning", ""),
                conversation_context=analysis_data.get("conversation_context", {})
            )
            
        except Exception as e:
            logger.error(f"Query analysis failed: {e}")
            return QueryAnalysis(
                refined_query=original_query,
                query_type=QueryType.RAG_QUERY,
                language="vi",
                confidence=0.3,
                reasoning="Fallback analysis due to error",
                conversation_context={}
            )
    
    async def _distribute_tasks(
        self,
        query_analysis: QueryAnalysis,
        user_context: Dict[str, Any]
    ) -> TaskDistribution:
        """
        B2: Phân phối nhiệm vụ cho agents dựa trên LLM analysis
        """
        logger.info("Distributing tasks to agents...")
        
        try:
            llm = await llm_provider_manager.get_provider()
            
            enabled_agents = self.settings.get_enabled_agents()
            user_accessible_domains = self._get_user_accessible_domains(user_context)
            
            distribution_prompt = f"""
Bạn là AI Orchestrator. Quyết định cách phân phối nhiệm vụ:

Query đã tinh chỉnh: "{query_analysis.refined_query}"
Loại query: {query_analysis.query_type.value}
Ngôn ngữ: {query_analysis.language}

Available agents: {enabled_agents}
User accessible domains: {user_accessible_domains}
User department: {user_context.get('department', 'unknown')}
User role: {user_context.get('role', 'user')}

Quyết định:
1. Chiến lược thực hiện: single_agent, multi_agent, tool_only, rag_only
2. Agents tham gia (nếu có)
3. Có cần chia nhỏ query không?
4. Cấu hình cho từng agent

Trả về JSON:
{{
    "strategy": "single_agent|multi_agent|tool_only|rag_only",
    "selected_agents": ["agent1", "agent2"],
    "sub_queries": {{
        "agent1": "nhiệm vụ cụ thể cho agent1",
        "agent2": "nhiệm vụ cụ thể cho agent2"
    }},
    "agent_configs": {{
        "agent1": {{"focus": "area", "priority": "high"}},
        "agent2": {{"focus": "area", "priority": "medium"}}
    }},
    "reasoning": "lý do lựa chọn chiến lược này"
}}
"""
            
            response = await llm.ainvoke(distribution_prompt)
            distribution_data = self._parse_json_response(response.content)
            
            return TaskDistribution(
                strategy=ExecutionStrategy(distribution_data.get("strategy", "single_agent")),
                selected_agents=distribution_data.get("selected_agents", []),
                sub_queries=distribution_data.get("sub_queries", {}),
                agent_configs=distribution_data.get("agent_configs", {}),
                reasoning=distribution_data.get("reasoning", "")
            )
            
        except Exception as e:
            logger.error(f"Task distribution failed: {e}")
            return self._fallback_task_distribution(query_analysis, user_context)
    
    async def _select_tools(
        self,
        query_analysis: QueryAnalysis,
        task_distribution: TaskDistribution,
        user_context: Dict[str, Any]
    ) -> ToolSelection:
        """
        B3: Lựa chọn tools dựa trên user permissions và LLM analysis
        """
        logger.info("🛠️ Selecting tools for execution...")
        
        try:
            llm = await llm_provider_manager.get_provider()
            
            enabled_tools = self.settings.get_enabled_tools()
            user_tool_permissions = await self._get_user_tool_permissions(user_context)
            
            tool_selection_prompt = f"""
Bạn là Tool Selector. Chọn tools phù hợp:

Query: "{query_analysis.refined_query}"
Strategy: {task_distribution.strategy.value}
Selected agents: {task_distribution.selected_agents}

Available tools: {enabled_tools}
User tool permissions: {user_tool_permissions}

Agent sub-queries:
{json.dumps(task_distribution.sub_queries, ensure_ascii=False, indent=2)}

Quyết định:
1. Tools nào cần thiết?
2. Cấu hình cho từng tool
3. Chiến lược sử dụng tools

Trả về JSON:
{{
    "selected_tools": ["tool1", "tool2"],
    "tool_configs": {{
        "tool1": {{"max_results": 10, "threshold": 0.7}},
        "tool2": {{"timeout": 30}}
    }},
    "usage_strategy": "parallel|sequential|conditional",
    "reasoning": "lý do chọn tools này"
}}
"""
            
            response = await llm.ainvoke(tool_selection_prompt)
            selection_data = self._parse_json_response(response.content)
            
            selected_tools = [
                tool for tool in selection_data.get("selected_tools", [])
                if tool in user_tool_permissions
            ]
            
            return ToolSelection(
                selected_tools=selected_tools,
                tool_configs=selection_data.get("tool_configs", {}),
                usage_strategy=selection_data.get("usage_strategy", "parallel"),
                reasoning=selection_data.get("reasoning", "")
            )
            
        except Exception as e:
            logger.error(f"Tool selection failed: {e}")
            return ToolSelection(
                selected_tools=["document_search"],
                tool_configs={},
                usage_strategy="parallel",
                reasoning="Fallback tool selection"
            )
    
    async def _execute_rag_retrieval(
        self,
        query_analysis: QueryAnalysis,
        task_distribution: TaskDistribution,
        user_context: Dict[str, Any]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        B4: Thực hiện RAG retrieval với permission check
        """
        logger.info("🔍 Executing RAG retrieval...")
        
        retrieval_results = {}
        
        try:
            for agent_name in task_distribution.selected_agents:
                agent_collections = await self._get_agent_collections(agent_name, user_context)
                sub_query = task_distribution.sub_queries.get(agent_name, query_analysis.refined_query)
                
                agent_results = []
                for collection in agent_collections:
                    try:
                        vector_results = await milvus_service.search(
                            query=sub_query,
                            collection_name=collection,
                            top_k=self.settings.rag.get("default_top_k", 10),
                            threshold=self.settings.rag.get("default_threshold", 0.7)
                        )
                        
                        filtered_results = await self._apply_permission_filter(
                            vector_results, user_context
                        )
                        
                        agent_results.extend(filtered_results)
                        
                    except Exception as e:
                        logger.warning(f"Retrieval failed for {collection}: {e}")
                
                retrieval_results[agent_name] = agent_results
                
        except Exception as e:
            logger.error(f"RAG retrieval failed: {e}")
            retrieval_results = {}
        
        return retrieval_results
    
    async def _evaluate_and_rank_documents(
        self,
        retrieval_results: Dict[str, List[Dict[str, Any]]],
        query_analysis: QueryAnalysis
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        B5: Đánh giá và xếp hạng documents sử dụng LLM
        """
        logger.info("Evaluating and ranking documents...")
        
        try:
            llm = await llm_provider_manager.get_provider()
            ranked_results = {}
            
            for agent_name, documents in retrieval_results.items():
                if not documents:
                    ranked_results[agent_name] = []
                    continue
                
                # Group by document để tránh fragment
                doc_groups = self._group_chunks_by_document(documents)
                
                # Evaluate relevance của từng document
                evaluated_docs = []
                for doc_id, chunks in doc_groups.items():
                    doc_content = self._merge_chunks(chunks)
                    
                    relevance_prompt = f"""
Đánh giá mức độ liên quan của tài liệu:

Query: "{query_analysis.refined_query}"
Document content (first 1000 chars): {doc_content[:1000]}...

Đánh giá:
1. Mức độ liên quan (0-1)
2. Thông tin chính
3. Độ tin cậy

Trả về JSON:
{{
    "relevance_score": 0.85,
    "key_information": "thông tin chính từ tài liệu",
    "credibility": 0.9,
    "reasoning": "lý do đánh giá"
}}
"""
                    
                    try:
                        response = await llm.ainvoke(relevance_prompt)
                        evaluation = self._parse_json_response(response.content)
                        
                        evaluated_docs.append({
                            "document_id": doc_id,
                            "chunks": chunks,
                            "merged_content": doc_content,
                            "relevance_score": evaluation.get("relevance_score", 0.5),
                            "key_information": evaluation.get("key_information", ""),
                            "credibility": evaluation.get("credibility", 0.5),
                            "reasoning": evaluation.get("reasoning", "")
                        })
                        
                    except Exception as e:
                        logger.warning(f"Document evaluation failed: {e}")
                        evaluated_docs.append({
                            "document_id": doc_id,
                            "chunks": chunks,
                            "merged_content": doc_content,
                            "relevance_score": 0.5,
                            "key_information": doc_content[:200],
                            "credibility": 0.5,
                            "reasoning": "Fallback evaluation"
                        })
                
                evaluated_docs.sort(key=lambda x: x["relevance_score"], reverse=True)
                ranked_results[agent_name] = evaluated_docs[:5] 
            
            return ranked_results
            
        except Exception as e:
            logger.error(f"Document evaluation failed: {e}")
            return retrieval_results
    
    async def _execute_agents(
        self,
        task_distribution: TaskDistribution,
        tool_selection: ToolSelection,
        ranked_documents: Dict[str, List[Dict[str, Any]]],
        query_analysis: QueryAnalysis
    ) -> Dict[str, Dict[str, Any]]:
        """
        B6: Thực hiện agents sử dụng domain agents đã có
        """
        logger.info("Executing domain agents...")
        
        agent_responses = {}
        
        tasks = []
        for agent_name in task_distribution.selected_agents:
            if agent_name in self.agents:
                task = self._execute_domain_agent(
                    agent_name,
                    task_distribution.sub_queries.get(agent_name, query_analysis.refined_query),
                    ranked_documents.get(agent_name, []),
                    tool_selection.selected_tools,
                    query_analysis.language
                )
                tasks.append((agent_name, task))
        
        for agent_name, task in tasks:
            try:
                result = await task
                agent_responses[agent_name] = result
            except Exception as e:
                logger.error(f"Agent {agent_name} execution failed: {e}")
                agent_responses[agent_name] = {
                    "response": f"Agent {agent_name} không thể xử lý yêu cầu",
                    "confidence": 0.1,
                    "evidence": [],
                    "error": str(e)
                }
        
        return agent_responses
    
    async def _execute_domain_agent(
        self,
        agent_name: str,
        query: str,
        documents: List[Dict[str, Any]],
        available_tools: List[str],
        language: str
    ) -> Dict[str, Any]:
        """Execute domain agent sử dụng agent classes đã có"""
        
        try:
            if agent_name not in self.agents:
                raise ValueError(f"Agent {agent_name} not found")
            
            agent = self.agents[agent_name]
            
            context = {
                "documents": documents,
                "query": query,
                "language": language,
                "available_tools": available_tools
            }
            
            response = await agent.execute_task(
                task=query,
                context=context,
                enabled_tools=available_tools
            )
            
            return {
                "response": response.content if hasattr(response, 'content') else str(response),
                "confidence": getattr(response, 'confidence', 0.8),
                "evidence": [doc.get("document_id", f"doc_{i}") for i, doc in enumerate(documents[:3])],
                "documents_used": len(documents),
                "tools_used": available_tools
            }
            
        except Exception as e:
            logger.error(f"Domain agent {agent_name} execution failed: {e}")
            raise
    
    async def _resolve_conflicts(
        self,
        agent_responses: Dict[str, Dict[str, Any]],
        query_analysis: QueryAnalysis
    ) -> ConflictResolution:
        """
        B6: Giải quyết conflicts giữa agents sử dụng LLM
        """
        logger.info("⚖️ Resolving conflicts between agents...")
        
        if len(agent_responses) <= 1:
            # No conflict to resolve
            single_response = next(iter(agent_responses.values())) if agent_responses else {
                "response": "Không có thông tin phù hợp",
                "confidence": 0.1,
                "evidence": []
            }
            return ConflictResolution(
                winning_response=single_response["response"],
                evidence_ranking=single_response.get("evidence", []),
                conflict_explanation="Không có xung đột",
                confidence_score=single_response.get("confidence", 0.1)
            )
        
        try:
            llm = await llm_provider_manager.get_provider()
            
            responses_summary = []
            for agent_name, response_data in agent_responses.items():
                responses_summary.append({
                    "agent": agent_name,
                    "response": response_data["response"][:500],  # Limit length
                    "confidence": response_data.get("confidence", 0.5),
                    "evidence_count": len(response_data.get("evidence", []))
                })
            
            conflict_resolution_prompt = f"""
Bạn là Conflict Resolver. Giải quyết xung đột giữa các agent responses:

Original query: "{query_analysis.refined_query}"

Agent responses:
{json.dumps(responses_summary, ensure_ascii=False, indent=2)}

Nhiệm vụ:
1. Chọn response tốt nhất hoặc tổng hợp
2. Xếp hạng evidence theo độ tin cậy
3. Giải thích lý do lựa chọn
4. Đánh giá confidence tổng thể

Trả về JSON:
{{
    "winning_agent": "agent_name hoặc 'synthesized'",
    "synthesized_response": "response đã được tổng hợp (nếu cần)",
    "evidence_ranking": [
        {{"source": "source1", "credibility": 0.9, "relevance": 0.8}},
        {{"source": "source2", "credibility": 0.7, "relevance": 0.9}}
    ],
    "conflict_explanation": "giải thích về conflicts và cách giải quyết",
    "confidence_score": 0.85
}}
"""
            
            response = await llm.ainvoke(conflict_resolution_prompt)
            resolution_data = self._parse_json_response(response.content)
            
            winning_agent = resolution_data.get("winning_agent", "")
            if winning_agent in agent_responses:
                winning_response = agent_responses[winning_agent]["response"]
            else:
                winning_response = resolution_data.get("synthesized_response", "Không thể tổng hợp thông tin")
            
            return ConflictResolution(
                winning_response=winning_response,
                evidence_ranking=resolution_data.get("evidence_ranking", []),
                conflict_explanation=resolution_data.get("conflict_explanation", ""),
                confidence_score=resolution_data.get("confidence_score", 0.5)
            )
            
        except Exception as e:
            logger.error(f"Conflict resolution failed: {e}")
            # Fallback: choose highest confidence response
            best_agent = max(agent_responses.items(), key=lambda x: x[1].get("confidence", 0))
            return ConflictResolution(
                winning_response=best_agent[1]["response"],
                evidence_ranking=best_agent[1].get("evidence", []),
                conflict_explanation="Chọn response có confidence cao nhất",
                confidence_score=best_agent[1].get("confidence", 0.5)
            )
    
    async def _assemble_final_response(
        self,
        conflict_resolution: ConflictResolution,
        ranked_documents: Dict[str, List[Dict[str, Any]]],
        query_analysis: QueryAnalysis
    ) -> Dict[str, Any]:
        """
        B7: Tạo response cuối cùng với evidence theo format ngôn ngữ
        """
        logger.info("📝 Assembling final response...")
        
        # Format response theo ngôn ngữ
        formatted_response = await self._format_response_by_language(
            conflict_resolution.winning_response,
            conflict_resolution.evidence_ranking,
            query_analysis.language
        )
        
        # Collect all evidence sources
        all_evidence = []
        for agent_docs in ranked_documents.values():
            for doc in agent_docs:
                source_info = {
                    "title": doc.get("title", "Unknown Document"),
                    "url": doc.get("url", ""),
                    "credibility": doc.get("credibility", 0.5),
                    "relevance": doc.get("relevance_score", 0.5)
                }
                all_evidence.append(source_info)
        
        unique_evidence = []
        seen_urls = set()
        for evidence in all_evidence:
            if evidence["url"] not in seen_urls:
                unique_evidence.append(evidence)
                seen_urls.add(evidence["url"])
        
        unique_evidence.sort(key=lambda x: x["credibility"], reverse=True)
        
        return {
            "response": formatted_response,
            "evidence": unique_evidence[:10],
            "confidence": conflict_resolution.confidence_score,
            "language": query_analysis.language,
            "metadata": {
                "query_type": query_analysis.query_type.value,
                "refined_query": query_analysis.refined_query,
                "conflict_explanation": conflict_resolution.conflict_explanation,
                "total_documents_considered": sum(len(docs) for docs in ranked_documents.values()),
                "processing_timestamp": datetime.now().isoformat()
            }
        }
    
    
    async def _handle_chitchat(
        self,
        query_analysis: QueryAnalysis,
        user_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Xử lý chitchat queries"""
        try:
            llm = await llm_provider_manager.get_provider()
            
            chitchat_prompt = f"""
Bạn là AI Assistant thân thiện. Trả lời câu chuyện phiếm:

Query: "{query_analysis.refined_query}"
Language: {query_analysis.language}

Trả lời ngắn gọn, thân thiện bằng {query_analysis.language}.
"""
            
            response = await llm.ainvoke(chitchat_prompt)
            
            return {
                "response": response.content,
                "evidence": [],
                "confidence": 0.8,
                "language": query_analysis.language,
                "metadata": {
                    "query_type": "chitchat",
                    "refined_query": query_analysis.refined_query
                }
            }
        except Exception as e:
            logger.error(f"Chitchat handling failed: {e}")
            return {
                "response": "Xin chào! Tôi có thể giúp gì cho bạn?",
                "evidence": [],
                "confidence": 0.5,
                "language": query_analysis.language,
                "metadata": {"error": str(e)}
            }
    
    def _get_user_accessible_domains(self, user_context: Dict[str, Any]) -> List[str]:
        """Get domains user có thể access"""
        user_department = user_context.get("department", "").lower()
        user_role = user_context.get("role", "user").lower()
        
        accessible = ["general"]
        
        # Department access
        if user_department:
            accessible.append(user_department)
        
        # Cross-department access cho managers
        if user_role in ["manager", "director", "ceo"]:
            accessible.extend(["hr", "finance", "it"])
        
        return list(set(accessible))
    
    async def _get_user_tool_permissions(self, user_context: Dict[str, Any]) -> List[str]:
        """DRY: Dùng permission_service thay vì duplicate logic"""
        user_id = user_context.get('user_id')
        if not user_id:
            return []
        
        if not self.permission_service:
            # Fallback cho case không có permission_service
            return ["document_search", "datetime"]
        
        # Dùng permission_service để get tool permissions
        tool_perms = await self.permission_service.get_user_tool_permissions(user_id)
        
        # Flatten categories thành list tool names
        allowed_tools = []
        for category_tools in tool_perms.values():
            for tool in category_tools:
                allowed_tools.append(tool['name'])
        
        return allowed_tools if allowed_tools else ["document_search", "datetime"]
    
    async def _get_agent_collections(self, agent_name: str, user_context: Dict[str, Any]) -> List[str]:
        """Get collections cho specific agent dựa trên user permissions"""
        user_role = user_context.get("role", "user").lower()
        user_department = user_context.get("department", "").lower()
        
        # Base collections mapping
        domain_collections = {
            "hr_specialist": ["hr_documents", "hr_policies"],
            "finance_specialist": ["finance_documents", "finance_reports"],
            "it_specialist": ["it_documents", "it_procedures"],
            "general_assistant": ["general_documents"]
        }
        
        base_collections = domain_collections.get(agent_name, ["general_documents"])
        
        # Filter collections based on user permissions
        accessible_collections = []
        
        for collection in base_collections:
            collection_department = collection.split("_")[0]  # hr, finance, it, general
            
            # Check if user can access this department's collection
            if collection_department == "general":
                accessible_collections.append(collection)
            elif collection_department == user_department:
                accessible_collections.append(collection)
            elif user_role in ["director", "ceo", "admin"]:
                accessible_collections.append(collection)  # Senior roles access all
        
        return accessible_collections if accessible_collections else ["general_documents"]
    
    async def _apply_permission_filter(
        self,
        documents: List[Dict[str, Any]],
        user_context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Apply permission filtering to documents dựa trên role"""
        user_role = user_context.get("role", "user").lower()
        user_department = user_context.get("department", "").lower()
        
        filtered_docs = []
        
        for doc in documents:
            metadata = doc.get("metadata", {})
            doc_access_level = metadata.get("access_level", "public")
            doc_department = metadata.get("department", "").lower()
            
            # Check access level based on role
            can_access = False
            
            if doc_access_level == "public":
                can_access = True
            elif doc_access_level == "internal" and user_role in ["employee", "staff", "manager", "senior", "director", "ceo", "admin"]:
                can_access = True
            elif doc_access_level == "confidential" and user_role in ["manager", "senior", "director", "ceo", "admin"]:
                can_access = True
            elif doc_access_level == "restricted" and user_role in ["director", "ceo", "admin"]:
                can_access = True
            
            # Check department access
            if can_access and doc_department:
                if doc_department == user_department:
                    can_access = True
                elif user_role in ["director", "ceo", "admin"]:
                    can_access = True  # Senior roles can access cross-department
                else:
                    can_access = False
            
            if can_access:
                filtered_docs.append(doc)
        
        return filtered_docs
    
    def _group_chunks_by_document(self, chunks: List[Dict[str, Any]]) -> Dict[str, List[Dict]]:
        """Group chunks by document ID"""
        groups = {}
        for chunk in chunks:
            doc_id = chunk.get("document_id", "unknown")
            if doc_id not in groups:
                groups[doc_id] = []
            groups[doc_id].append(chunk)
        return groups
    
    def _merge_chunks(self, chunks: List[Dict[str, Any]]) -> str:
        """Merge chunks into single document content"""
        sorted_chunks = sorted(chunks, key=lambda x: x.get("chunk_index", 0))
        return " ".join([chunk.get("content", "") for chunk in sorted_chunks])
    
    async def _execute_single_agent(
        self,
        agent_name: str,
        query: str,
        documents: List[Dict[str, Any]],
        available_tools: List[str],
        language: str
    ) -> Dict[str, Any]:
        """Execute single agent task"""
        llm = await llm_provider_manager.get_provider()
        
        context = ""
        evidence = []
        if documents:
            for doc in documents[:3]:  # Top 3 documents
                context += f"Document: {doc.get('key_information', '')}\n"
                evidence.append({
                    "source": doc.get("document_id", "unknown"),
                    "credibility": doc.get("credibility", 0.5)
                })
        
        agent_prompt = f"""
Bạn là {agent_name}. Trả lời câu hỏi dựa vào context:

Query: {query}
Context: {context if context else "Không có context cụ thể"}
Available tools: {available_tools}

Trả lời bằng {language}, chuyên nghiệp và chính xác.
"""
        
        response = await llm.ainvoke(agent_prompt)
        
        return {
            "response": response.content,
            "evidence": evidence,
            "confidence": 0.9,
            "metadata": {
                "agent": agent_name,
                "tools_used": available_tools,
                "documents_count": len(documents)
            }
        }