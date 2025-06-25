from typing import Dict, Any, List
from datetime import datetime
import re

from .base_node import BaseWorkflowNode, AnalysisNode
from ..state.unified_state import UnifiedRAGState, QueryDomain, AccessLevel, ProcessingStatus
from services.llm.provider_manager import llm_provider_manager
from utils.logging import get_logger

logger = get_logger(__name__)

class QueryAnalysisNode(AnalysisNode):
    """Comprehensive query analysis trong một node"""
    
    async def process(self, state: UnifiedRAGState) -> UnifiedRAGState:
        """Phân tích toàn diện query: domain, complexity, intent"""
        
        query = state["query"]
        user_context = state.get("user_context", {})
        
        # Build comprehensive analysis prompt
        analysis_prompt = f"""
Phân tích toàn diện câu hỏi:

Query: "{query}"
User Department: {user_context.get('department', 'unknown')}
User Role: {user_context.get('role', 'user')}

Trả về JSON:
{{
    "domain_analysis": {{
        "primary_domain": "hr|finance|it|general",
        "secondary_domains": ["domain1", "domain2"],
        "requires_cross_department": false
    }},
    "complexity_analysis": {{
        "score": 0.7,
        "factors": ["length", "semantic", "technical"],
        "estimated_time": 5.0
    }},
    "intent_analysis": {{
        "type": "information_request|action_request|help_request",
        "scope": "summary|detailed|comprehensive",
        "urgency": "low|medium|high",
        "response_format": "narrative|structured|examples"
    }},
    "confidence": 0.8,
    "reasoning": "explanation"
}}
"""
        
        try:
            analysis_result = await self._analyze_with_llm(analysis_prompt)
            
            # Extract results
            domain_analysis = analysis_result.get("domain_analysis", {})
            complexity_analysis = analysis_result.get("complexity_analysis", {})
            intent_analysis = analysis_result.get("intent_analysis", {})
            
            # Map domains
            domains = self._map_domains(
                domain_analysis.get("primary_domain"),
                domain_analysis.get("secondary_domains", [])
            )
            
            return {
                **state,
                "domain_classification": domains,
                "query_complexity": complexity_analysis.get("score", 0.5),
                "complexity_score": complexity_analysis.get("score", 0.5),
                "intent_analysis": intent_analysis,
                "requires_cross_department": domain_analysis.get("requires_cross_department", False),
                "estimated_processing_time": complexity_analysis.get("estimated_time", 5.0),
                "confidence_scores": self._update_confidence(state, analysis_result.get("confidence", 0.5))
            }
            
        except Exception as e:
            logger.error(f"Query analysis failed: {e}")
            return await self._fallback_analysis(state)
    
    def _map_domains(self, primary: str, secondary: List[str]) -> List[QueryDomain]:
        """Map string domains to enum"""
        mapping = {
            "hr": QueryDomain.HR,
            "finance": QueryDomain.FINANCE,
            "it": QueryDomain.IT,
            "general": QueryDomain.GENERAL
        }
        
        result = []
        if primary and primary in mapping:
            result.append(mapping[primary])
            
        for domain in secondary:
            if domain in mapping and mapping[domain] not in result:
                result.append(mapping[domain])
        
        if not result:
            result.append(QueryDomain.GENERAL)
            
        if len(result) > 1:
            result.append(QueryDomain.CROSS_DEPARTMENT)
            
        return result
    
    async def _fallback_analysis(self, state: UnifiedRAGState) -> UnifiedRAGState:
        """Fallback keyword-based analysis"""
        query = state["query"].lower()
        
        # Simple domain detection
        domain = QueryDomain.GENERAL
        if any(k in query for k in ["nhân sự", "hr", "lương"]):
            domain = QueryDomain.HR
        elif any(k in query for k in ["tài chính", "chi phí"]):
            domain = QueryDomain.FINANCE
        elif any(k in query for k in ["it", "máy tính", "hệ thống"]):
            domain = QueryDomain.IT
        
        return {
            **state,
            "domain_classification": [domain],
            "query_complexity": 0.5,
            "complexity_score": 0.5,
            "intent_analysis": {"type": "information_request", "confidence": 0.3},
            "requires_cross_department": False,
            "estimated_processing_time": 5.0
        }


class PermissionNode(BaseWorkflowNode):
    """Permission check và document filtering"""
    
    async def process(self, state: UnifiedRAGState) -> UnifiedRAGState:
        """Check permissions và filter documents"""
        
        # Permission check
        permission_result = await self._check_permissions(state)
        if not permission_result["granted"]:
            return {
                **state,
                "processing_status": ProcessingStatus.PERMISSION_DENIED,
                "error_messages": ["Insufficient permissions"],
                "permission_checks": [permission_result]
            }
        
        # Filter documents if retrieval results exist
        if state.get("raw_retrieval_results"):
            filtered_state = await self._filter_documents(state)
            return {**filtered_state, "permission_checks": [permission_result]}
        
        return {**state, "permission_checks": [permission_result]}
    
    async def _check_permissions(self, state: UnifiedRAGState) -> Dict[str, Any]:
        """Check user permissions"""
        user_permissions = state.get("user_permissions", [])
        domains = state.get("domain_classification", [])
        
        # Domain permission mapping
        required_perms = {
            QueryDomain.HR: ["hr_read"],
            QueryDomain.FINANCE: ["finance_read"],
            QueryDomain.IT: ["it_read"],
            QueryDomain.GENERAL: ["general_read"]
        }
        
        # Check domain access
        domain_access = True
        for domain in domains:
            if domain in required_perms:
                if not any(perm in user_permissions for perm in required_perms[domain]):
                    domain_access = False
                    break
        
        # Check cross-department access
        cross_dept_access = True
        if state.get("requires_cross_department") and "cross_department_access" not in user_permissions:
            cross_dept_access = False
        
        return {
            "timestamp": datetime.now(),
            "user_id": state.get("user_id"),
            "granted": domain_access and cross_dept_access,
            "domain_access": domain_access,
            "cross_dept_access": cross_dept_access
        }
    
    async def _filter_documents(self, state: UnifiedRAGState) -> UnifiedRAGState:
        """Filter documents based on permissions"""
        raw_results = state.get("raw_retrieval_results", {})
        user_permissions = state.get("user_permissions", [])
        max_access = state.get("max_access_level", AccessLevel.PUBLIC)
        
        filtered_results = {}
        filtered_count = 0
        
        for collection, docs in raw_results.items():
            filtered_docs = []
            for doc in docs:
                if self._check_doc_access(doc, user_permissions, max_access):
                    filtered_docs.append(doc)
                else:
                    filtered_count += 1
            filtered_results[collection] = filtered_docs
        
        return {
            **state,
            "filtered_retrieval_results": filtered_results,
            "permission_filtered_count": filtered_count
        }
    
    def _check_doc_access(self, doc: Dict, permissions: List[str], max_level: AccessLevel) -> bool:
        """Check access to specific document"""
        metadata = doc.get("metadata", {})
        doc_level = metadata.get("access_level", "public")
        required_perms = metadata.get("required_permissions", [])
        
        # Check access level
        level_hierarchy = {"public": 1, "internal": 2, "confidential": 3, "restricted": 4}
        user_level = level_hierarchy.get(max_level.value if hasattr(max_level, 'value') else str(max_level), 1)
        doc_level_value = level_hierarchy.get(doc_level, 1)
        
        if user_level < doc_level_value:
            return False
        
        # Check required permissions
        if required_perms and not any(perm in permissions for perm in required_perms):
            return False
        
        return True


class RetrievalNode(BaseWorkflowNode):
    """Document retrieval với vector search"""
    
    async def process(self, state: UnifiedRAGState) -> UnifiedRAGState:
        """Vector search documents"""
        
        try:
            from services.vector.milvus_service import milvus_service
            
            query = state["query"]
            collections = state.get("accessible_collections", [])
            
            # Determine collections from domains
            target_collections = self._get_target_collections(
                state.get("domain_classification", []),
                collections
            )
            
            results = {}
            total_found = 0
            
            # Search each collection
            for collection in target_collections:
                try:
                    search_results = await milvus_service.search(
                        query=query,
                        collection_name=collection,
                        top_k=self.settings.rag.get("default_top_k", 10),
                        threshold=self.settings.rag.get("default_threshold", 0.7)
                    )
                    results[collection] = search_results
                    total_found += len(search_results)
                except Exception as e:
                    logger.warning(f"Search failed for {collection}: {e}")
                    results[collection] = []
            
            # Calculate relevance scores
            relevance_scores = {}
            for collection, docs in results.items():
                if docs:
                    avg_score = sum(doc.get("score", 0.0) for doc in docs) / len(docs)
                    relevance_scores[collection] = avg_score
                else:
                    relevance_scores[collection] = 0.0
            
            return {
                **state,
                "raw_retrieval_results": results,
                "retrieved_documents": [doc for docs in results.values() for doc in docs],
                "total_documents_found": total_found,
                "relevance_scores": relevance_scores
            }
            
        except Exception as e:
            logger.error(f"Document retrieval failed: {e}")
            return {
                **state,
                "raw_retrieval_results": {},
                "retrieved_documents": [],
                "total_documents_found": 0,
                "error_messages": state.get("error_messages", []) + [f"Retrieval error: {str(e)}"]
            }
    
    def _get_target_collections(self, domains: List[QueryDomain], accessible: List[str]) -> List[str]:
        """Get target collections from domains"""
        domain_mapping = {
            QueryDomain.HR: ["hr_documents", "hr_policies"],
            QueryDomain.FINANCE: ["finance_documents", "finance_reports"],
            QueryDomain.IT: ["it_documents", "it_procedures"],
            QueryDomain.GENERAL: ["general_documents"]
        }
        
        collections = set()
        for domain in domains:
            if domain in domain_mapping:
                collections.update(domain_mapping[domain])
        
        return [col for col in collections if col in accessible]


class SecurityNode(BaseWorkflowNode):
    """Content security và sanitization"""
    
    def __init__(self):
        super().__init__()
        self._init_patterns()
    
    def _init_patterns(self):
        """Initialize sensitive data patterns"""
        self.patterns = {
            "email": r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            "phone": r'(\+84|0)[1-9]\d{8,9}',
            "id_number": r'\b\d{9,12}\b',
            "salary": r'\b\d{1,3}(?:\.\d{3})*(?:\,\d{3})?\s?(?:VND|USD|triệu)\b'
        }
    
    async def process(self, state: UnifiedRAGState) -> UnifiedRAGState:
        """Sanitize và validate content security"""
        
        content = state.get("raw_synthesis", "")
        if not content:
            return state
        
        # Sanitize content
        sanitized, redacted = self._sanitize_content(content, state.get("user_permissions", []))
        
        # Security validation
        violations = self._validate_security(sanitized)
        
        return {
            **state,
            "sanitized_content": sanitized,
            "redacted_sections": redacted,
            "security_violations": violations,
            "content_safety": {
                "is_safe": len(violations) == 0,
                "violation_count": len(violations),
                "timestamp": datetime.now()
            }
        }
    
    def _sanitize_content(self, content: str, permissions: List[str]) -> tuple:
        """Sanitize content based on permissions"""
        sanitized = content
        redacted_sections = []
        
        # Determine patterns to apply
        patterns_to_use = self._get_patterns_for_user(permissions)
        
        for pattern_name, pattern in patterns_to_use.items():
            matches = list(re.finditer(pattern, sanitized, re.IGNORECASE))
            for match in matches:
                original = match.group()
                replacement = f"[{pattern_name.upper()}_REDACTED]"
                sanitized = sanitized.replace(original, replacement)
                redacted_sections.append({
                    "type": pattern_name,
                    "original": original,
                    "replacement": replacement
                })
        
        return sanitized, redacted_sections
    
    def _get_patterns_for_user(self, permissions: List[str]) -> Dict[str, str]:
        """Get patterns based on user permissions"""
        if "admin" in permissions:
            return {}  # No sanitization for admin
        elif "sensitive_data_access" in permissions:
            return {"email": self.patterns["email"]}  # Minimal sanitization
        else:
            return self.patterns  # Full sanitization
    
    def _validate_security(self, content: str) -> List[Dict[str, Any]]:
        """Validate content security"""
        violations = []
        
        # Check length
        max_length = self.settings.security.get("max_response_length", 5000)
        if len(content) > max_length:
            violations.append({
                "type": "content_length",
                "severity": "medium",
                "message": f"Content too long: {len(content)} > {max_length}"
            })
        
        # Check for injection patterns
        injection_patterns = [r'<script[^>]*>', r'javascript:', r'data:text/html']
        for pattern in injection_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                violations.append({
                    "type": "potential_injection",
                    "severity": "high",
                    "message": "Potential code injection detected"
                })
                break
        
        return violations


class ResponseNode(BaseWorkflowNode):
    """Response generation, quality check và finalization"""
    
    async def process(self, state: UnifiedRAGState) -> UnifiedRAGState:
        """Generate, check và finalize response"""
        
        # Generate response
        synthesis_result = await self._generate_response(state)
        
        # Quality check
        quality_result = await self._quality_check(synthesis_result)
        
        # Finalize response
        final_result = await self._finalize_response(quality_result)
        
        return final_result
    
    async def _generate_response(self, state: UnifiedRAGState) -> UnifiedRAGState:
        """Generate response from documents"""
        
        try:
            enabled_providers = self.settings.get_enabled_providers()
            if not enabled_providers:
                raise ValueError("No LLM providers enabled")
            
            llm = await llm_provider_manager.get_provider(enabled_providers[0])
            
            # Prepare context
            context = self._prepare_context(state)
            prompt = self._build_prompt(state, context)
            
            response = await llm.ainvoke(prompt)
            
            return {
                **state,
                "raw_synthesis": response.content,
                "draft_response": response.content
            }
            
        except Exception as e:
            logger.error(f"Response generation failed: {e}")
            return {
                **state,
                "raw_synthesis": "Xin lỗi, tôi không thể tạo câu trả lời lúc này.",
                "draft_response": "Xin lỗi, tôi không thể tạo câu trả lời lúc này.",
                "error_messages": state.get("error_messages", []) + [f"Generation error: {str(e)}"]
            }
    
    def _prepare_context(self, state: UnifiedRAGState) -> str:
        """Prepare context from documents"""
        filtered_results = state.get("filtered_retrieval_results", {})
        
        context_parts = []
        for collection, docs in filtered_results.items():
            if docs:
                collection_context = f"\n=== {collection.upper()} ===\n"
                for i, doc in enumerate(docs[:3]):
                    content = doc.get("content", "")[:500] + "..." if len(doc.get("content", "")) > 500 else doc.get("content", "")
                    collection_context += f"Document {i+1}: {content}\n"
                context_parts.append(collection_context)
        
        return "\n".join(context_parts) if context_parts else "Không có tài liệu tham khảo."
    
    def _build_prompt(self, state: UnifiedRAGState, context: str) -> str:
        """Build synthesis prompt"""
        query = state["query"]
        intent = state.get("intent_analysis", {})
        
        style_instructions = self._get_style_instructions(intent)
        
        return f"""
Bạn là AI Assistant chuyên nghiệp. Trả lời câu hỏi dựa vào thông tin được cung cấp.

Câu hỏi: {query}

Thông tin tham khảo:
{context}

Yêu cầu:
{style_instructions}

Trả lời bằng tiếng Việt, chính xác và hữu ích:
"""
    
    def _get_style_instructions(self, intent: Dict[str, Any]) -> str:
        """Get style instructions from intent analysis"""
        scope = intent.get("scope", "standard")
        response_format = intent.get("response_format", "narrative")
        
        instructions = []
        
        if scope == "summary":
            instructions.append("- Trả lời ngắn gọn, súc tích")
        elif scope == "detailed":
            instructions.append("- Trả lời chi tiết, đầy đủ")
        
        if response_format == "structured":
            instructions.append("- Sử dụng cấu trúc rõ ràng (bullet points, số thứ tự)")
        elif response_format == "examples":
            instructions.append("- Cung cấp ví dụ cụ thể")
        
        return "\n".join(instructions) if instructions else "- Trả lời tự nhiên và hữu ích"
    
    async def _quality_check(self, state: UnifiedRAGState) -> UnifiedRAGState:
        """Quality check response"""
        content = state.get("sanitized_content", state.get("raw_synthesis", ""))
        
        quality_metrics = {
            "length_check": self._check_length(content),
            "content_check": self._check_content_quality(content),
            "relevance_check": self._check_relevance(content, state["query"]),
            "safety_check": 1.0 if state.get("content_safety", {}).get("is_safe", True) else 0.5
        }
        
        overall_quality = sum(quality_metrics.values()) / len(quality_metrics)
        quality_threshold = self.settings.workflow.get("quality_threshold", 0.7)
        
        return {
            **state,
            "quality_metrics": quality_metrics,
            "quality_checks": {
                "overall_score": overall_quality,
                "passed": overall_quality >= quality_threshold,
                "threshold": quality_threshold
            },
            "factual_consistency_score": quality_metrics["relevance_check"],
            "relevance_score": quality_metrics["relevance_check"]
        }
    
    def _check_length(self, content: str) -> float:
        """Check content length appropriateness"""
        length = len(content.strip())
        if length < 20:
            return 0.3
        elif length > 3000:
            return 0.7
        else:
            return 1.0
    
    def _check_content_quality(self, content: str) -> float:
        """Check general content quality"""
        score = 0.5
        
        if content.strip().endswith('.'):
            score += 0.2
        
        if any(indicator in content.lower() for indicator in ["xin lỗi", "không thể", "lỗi"]):
            score -= 0.3
        
        # Vietnamese language check
        vietnamese_chars = "àáảãạăắằẳẵặâấầẩẫậèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗộơớờởỡợùúủũụưứừửữựỳýỷỹỵđ"
        if any(char in content.lower() for char in vietnamese_chars):
            score += 0.3
        
        return max(0.0, min(score, 1.0))
    
    def _check_relevance(self, content: str, query: str) -> float:
        """Check relevance to query"""
        query_words = set(query.lower().split())
        content_words = set(content.lower().split())
        
        if not query_words:
            return 0.5
        
        overlap = len(query_words.intersection(content_words))
        return min(overlap / len(query_words), 1.0)
    
    async def _finalize_response(self, state: UnifiedRAGState) -> UnifiedRAGState:
        """Finalize response với citations"""
        content = state.get("sanitized_content", "")
        
        # Add citations
        if self.settings.workflow.get("enable_citation_generation", True):
            content = self._add_citations(content, state)
        
        # Generate metadata
        metadata = self._generate_metadata(state)
        
        # Calculate final confidence
        final_confidence = self._calculate_final_confidence(state)
        
        return {
            **state,
            "final_response": content,
            "response_metadata": metadata,
            "confidence_score": final_confidence,
            "confidence_scores": {
                **state.get("confidence_scores", {}),
                "final": final_confidence
            },
            "processing_status": ProcessingStatus.COMPLETED
        }
    
    def _add_citations(self, content: str, state: UnifiedRAGState) -> str:
        """Add citations to response"""
        doc_sources = state.get("document_sources", [])
        
        if doc_sources:
            citations = "\n\nNguồn tham khảo:\n" + "\n".join(f"- {source}" for source in doc_sources[:3])
            return content + citations
        
        return content
    
    def _generate_metadata(self, state: UnifiedRAGState) -> Dict[str, Any]:
        """Generate response metadata"""
        return {
            "total_documents": state.get("total_documents_found", 0),
            "filtered_documents": state.get("permission_filtered_count", 0),
            "quality_score": state.get("quality_metrics", {}).get("overall_score", 0.0),
            "domains": [d.value for d in state.get("domain_classification", [])],
            "processing_time": sum(state.get("processing_duration", {}).values()),
            "timestamp": datetime.now()
        }
    
    def _calculate_final_confidence(self, state: UnifiedRAGState) -> float:
        """Calculate final confidence score"""
        confidence_scores = state.get("confidence_scores", {})
        
        if not confidence_scores:
            return 0.3
        
        # Weighted average
        weights = {"analysis": 0.3, "retrieval": 0.3, "synthesis": 0.4}
        weighted_sum = 0.0
        total_weight = 0.0
        
        for score_type, weight in weights.items():
            if score_type in confidence_scores:
                weighted_sum += confidence_scores[score_type] * weight
                total_weight += weight
        
        return weighted_sum / total_weight if total_weight > 0 else 0.3 