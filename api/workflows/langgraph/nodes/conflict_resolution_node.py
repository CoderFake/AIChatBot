"""
LLM-based Conflict Resolution Node
Uses LLM to decide conflict resolution based on evidence quality, recency, and accuracy consensus
"""
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union
from langchain_core.runnables import RunnableConfig
from .base import ExecutionNode
from workflows.langgraph.state.state import RAGState
from utils.logging import get_logger
from services.orchestrator.orchestrator import Orchestrator
from config.settings import get_settings

logger = get_logger(__name__)
settings = get_settings()


class ConflictResolutionNode(ExecutionNode):
    """
    LLM-based conflict resolution between multiple agent responses
    No hardcoded rules - LLM decides based on evidence quality
    """
    
    def __init__(self):
        super().__init__("conflict_resolution")
        api_url = getattr(settings, "API_URL", None) or f"http://localhost:{settings.APP_PORT}"
        self._api_base_url = str(api_url).rstrip("/")
    
    async def execute(self, state: RAGState, config: RunnableConfig) -> Dict[str, Any]:
        """
        Use LLM to resolve conflicts between agent responses
        """
        try:
            agent_responses = state.get("agent_responses", [])
            original_query = state.get("query", "")
            
            if len(agent_responses) <= 1:
                return {
                    "next_action": "final_response",
                    "processing_status": "completed",
                    "progress_percentage": 95,
                    "progress_message": "No conflict resolution needed",
                    "should_yield": True
                }
            
            logger.info(f"LLM resolving conflicts between {len(agent_responses)} agent responses")

            detected_language = state.get("detected_language", "english")
            
            conflict_resolution = await self._llm_resolve_conflicts(
                agent_responses, original_query, detected_language, state
            )
            
            return {
                "conflict_resolution": conflict_resolution,
                "next_action": "final_response",
                "processing_status": "completed",
                "progress_percentage": 95,
                "progress_message": "Conflict resolution completed by LLM analysis",
                "should_yield": True
            }
            
        except Exception as e:
            logger.error(f"Conflict resolution failed: {e}")
            return {
                "error_message": f"Conflict resolution failed: {str(e)}",
                "next_action": "error",
                "processing_status": "failed",
                "should_yield": True
            }
    
    async def _llm_resolve_conflicts(
        self,
        agent_responses: List[Dict[str, Any]],
        original_query: str,
        detected_language: str,
        state
    ) -> Dict[str, Any]:
        """Use LLM to analyze and resolve conflicts between agent responses"""
        try:
            provider_name = state.get("provider_name")
            if provider_name:
                orchestrator = Orchestrator()
                provider = await orchestrator.llm(provider_name)
            else:
                logger.warning("Provider name not found in state, returning first response")
                return {
                    "final_answer": agent_responses[0]["content"] if agent_responses else "",
                    "resolution_method": "fallback",
                    "confidence_score": 0.5
                }
            
            responses_with_evidence = []
            for i, response in enumerate(agent_responses):
                sources = response.get("sources", [])

                evidence_analysis = self._analyze_evidence(sources)
                latest_evidence_dt: Optional[datetime] = None
                if isinstance(sources, list):
                    parsed_dates = [
                        self._parse_source_datetime(source.get("created_at") if isinstance(source, dict) else None)
                        for source in sources
                    ]
                    parsed_dates = [dt for dt in parsed_dates if dt]
                    if parsed_dates:
                        latest_evidence_dt = max(parsed_dates)

                responses_with_evidence.append({
                    "agent_index": i,
                    "agent_name": response.get("agent_name", f"Agent_{i}"),
                    "content": response.get("content", ""),
                    "confidence": response.get("confidence", 0.0),
                    "tools_used": response.get("tools_used", []),
                    "execution_time": response.get("execution_time", 0.0),
                    "sources_count": len(sources),
                    "evidence_analysis": evidence_analysis,
                    "latest_evidence_at": latest_evidence_dt.isoformat() if latest_evidence_dt else None,
                })

            merged_sources = self._merge_sources(agent_responses)
            
            conflict_resolution_prompt = f"""
You are an expert conflict resolution system for multi-agent responses. Analyze the following agent responses and determine the best final answer.

ORIGINAL QUERY: {original_query}
RESPONSE LANGUAGE: {detected_language}

AGENT RESPONSES WITH EVIDENCE:
{json.dumps(responses_with_evidence, ensure_ascii=False, indent=2)}

ANALYSIS CRITERIA:
1. **Evidence Quality**: Sources with more recent timestamps are more valuable
2. **Accuracy Consensus**: If multiple agents agree on facts, that's stronger evidence  
3. **Completeness**: More comprehensive answers with supporting evidence
4. **Source Reliability**: Consider source types and reliability indicators
5. **Consistency**: Look for contradictions vs confirmations between responses

CONFLICT RESOLUTION RULES:
- Use consensus voting: if 3+ agents say "true" and 1 says "false", choose "true"
- Prefer more recent information (newer timestamps in sources)
- Weight responses by evidence quality, not just confidence scores
- Combine complementary information from different agents when possible
- Always respond in the detected language: {detected_language}

Provide your analysis and resolution in this JSON format:
{{
    "final_answer": "Combined and resolved answer in {detected_language}",
    "winning_agents": ["list", "of", "primary", "agent", "names"],
    "conflict_level": "low|medium|high",
    "resolution_method": "consensus_voting|recency_priority|evidence_quality|combination",
    "evidence_ranking": [
        {{
            "agent": "agent_name",
            "rank": 1,
            "reasoning": "Why this agent's evidence is ranked this way",
            "evidence_score": 0.95,
            "factors": {{
                "recency": 0.9,
                "consensus": 0.8,
                "completeness": 0.9,
                "source_reliability": 0.8
            }}
        }}
    ],
    "resolution_reasoning": "Detailed explanation of how conflicts were resolved",
    "combined_sources": ["list", "of", "final", "authoritative", "sources"],
    "confidence_score": 0.95
}}

IMPORTANT: 
- The final_answer should be comprehensive and in {detected_language}
- Combine information from multiple agents when they complement each other
- Clearly explain your reasoning process
- Focus on factual accuracy over agent confidence scores
"""
            tenant_id = state.get("tenant_id")
            response = await provider.ainvoke(
                conflict_resolution_prompt,
                tenant_id,
                response_format="json_object",
                json_mode=True,
                temperature=0.1,
                max_tokens=4096,
                markdown=False 
            )
            
            if isinstance(response, dict):
                result = response
            elif hasattr(response, 'content'):
                result = json.loads(response.content.strip())
            else:
                raise RuntimeError(f"Unexpected response format: {type(response)}")
            
            logger.info(f"LLM conflict resolution completed with method: {result.get('resolution_method', 'unknown')}")

            combined_sources = result.get("combined_sources")
            if combined_sources:
                result["combined_sources"] = self._deduplicate_sources(combined_sources + merged_sources)
            else:
                result["combined_sources"] = merged_sources

            return result
            
        except Exception as e:
            logger.error(f"LLM conflict resolution failed: {e}")
            
            best_response = max(agent_responses, key=lambda x: x.get("confidence", 0)) if agent_responses else {}
            fallback_sources = self._merge_sources(agent_responses)

            return {
                "final_answer": best_response.get("content", "Unable to resolve conflicts"),
                "winning_agents": [best_response.get("agent_name", "unknown")],
                "conflict_level": "high",
                "resolution_method": "fallback_highest_confidence",
                "evidence_ranking": ([{
                    "agent": best_response.get("agent_name", "unknown"),
                    "rank": 1,
                    "reasoning": "Fallback selection due to LLM resolution failure",
                    "evidence_score": best_response.get("confidence", 0.0),
                    "factors": {
                        "recency": 0.5,
                        "consensus": 0.5,
                        "completeness": 0.5,
                        "source_reliability": 0.5
                    }
                }] if best_response else []),
                "resolution_reasoning": "LLM conflict resolution failed, using highest confidence agent",
                "combined_sources": fallback_sources,
                "confidence_score": best_response.get("confidence", 0.0)
            }

    def _analyze_evidence(self, sources: Union[List[Any], Any]) -> Dict[str, Any]:
        """Analyze evidence quality from sources"""
        try:
            if not sources:
                return {
                    "total_sources": 0,
                    "recency_score": 0.0,
                    "reliability_score": 0.5,
                    "completeness_score": 0.0
                }

            normalized_sources: List[str] = []
            source_list = sources if isinstance(sources, list) else [sources]
            parsed_datetimes: List[datetime] = []
            for source in source_list:
                if isinstance(source, dict):
                    candidate = source.get("url") or source.get("title") or source.get("document_id")
                    if candidate:
                        normalized_sources.append(str(candidate))
                    parsed_dt = self._parse_source_datetime(source.get("created_at") or source.get("datetime"))
                    if parsed_dt:
                        parsed_datetimes.append(parsed_dt)
                        continue
                normalized_sources.append(str(source))

            total_sources = len(normalized_sources)

            recency_score = 0.8
            if parsed_datetimes:
                newest = max(parsed_datetimes)
                age_days = max(0.0, (datetime.now(timezone.utc) - newest).total_seconds() / 86400)
                if age_days <= 1:
                    recency_score = 1.0
                elif age_days <= 7:
                    recency_score = 0.95
                elif age_days <= 30:
                    recency_score = 0.9
                elif age_days <= 90:
                    recency_score = 0.8
                else:
                    recency_score = 0.6

            reliable_indicators = ['.gov', '.edu', '.org', 'intra.', 'wiki.']
            reliable_sources = sum(
                1
                for source in normalized_sources
                if any(indicator in source.lower() for indicator in reliable_indicators)
            )
            
            reliability_score = min(1.0, (reliable_sources / total_sources) + 0.3)
            completeness_score = min(1.0, total_sources / 5) 
            
            return {
                "total_sources": total_sources,
                "recency_score": recency_score,
                "reliability_score": reliability_score,
                "completeness_score": completeness_score,
                "reliable_sources_count": reliable_sources
            }
            
        except Exception as e:
            logger.warning(f"Evidence analysis failed: {e}")
            source_count = len(sources) if isinstance(sources, list) else (1 if sources else 0)
            return {
                "total_sources": source_count,
                "recency_score": 0.5,
                "reliability_score": 0.5,
                "completeness_score": 0.5
            }

    def _normalize_source(self, source: Any) -> Dict[str, Any]:
        """Normalize source entries to a consistent structure."""

        if isinstance(source, dict):
            normalized = {
                "document_id": source.get("document_id") or source.get("id"),
                "title": source.get("title") or source.get("source") or source.get("name"),
                "url": source.get("url") or source.get("evidence_url"),
                "score": source.get("score"),
                "collection": source.get("collection"),
                "access_level": source.get("access_level") or source.get("collection_type"),
                "created_at": source.get("created_at") or source.get("datetime"),
            }

            snippet = source.get("content") or source.get("snippet")
            if isinstance(snippet, str) and snippet:
                normalized["snippet"] = snippet[:400]

            document_id = normalized.get("document_id")
            if document_id and not normalized.get("url"):
                normalized["url"] = self._build_document_url(document_id)

            return {key: value for key, value in normalized.items() if value is not None}

        if source:
            return {"title": str(source)}

        return {}

    def _merge_sources(self, agent_responses: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Merge and deduplicate sources from all agent responses."""

        merged: List[Dict[str, Any]] = []
        seen = set()

        for response in agent_responses or []:
            for source in response.get("sources", []) or []:
                normalized = self._normalize_source(source)
                if not normalized:
                    continue

                dedup_key = normalized.get("url") or normalized.get("document_id") or normalized.get("title")
                if dedup_key and dedup_key in seen:
                    continue
                if dedup_key:
                    seen.add(dedup_key)

                merged.append(normalized)

        merged.sort(
            key=lambda item: self._parse_source_datetime(item.get("created_at")) or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True
        )

        return merged

    def _deduplicate_sources(self, sources: List[Any]) -> List[Dict[str, Any]]:
        """Deduplicate an arbitrary list of sources."""

        deduped: List[Dict[str, Any]] = []
        seen = set()
        for source in sources or []:
            normalized = self._normalize_source(source)
            if not normalized:
                continue
            dedup_key = normalized.get("url") or normalized.get("document_id") or normalized.get("title")
            if dedup_key and dedup_key in seen:
                continue
            if dedup_key:
                seen.add(dedup_key)
            deduped.append(normalized)

        deduped.sort(
            key=lambda item: self._parse_source_datetime(item.get("created_at")) or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True
        )

        return deduped

    def _build_document_url(self, document_id: Optional[str]) -> Optional[str]:
        """Build an absolute download URL for a document."""

        if not document_id or document_id in {"", "unknown"}:
            return None

        return f"{self._api_base_url}/api/v1/documents/{document_id}/download"

    def _parse_source_datetime(self, value: Any) -> Optional[datetime]:
        """Parse datetime information from evidence entries."""

        if isinstance(value, datetime):
            return value if value.tzinfo else value.replace(tzinfo=timezone.utc)

        if isinstance(value, (int, float)):
            try:
                return datetime.fromtimestamp(value, tz=timezone.utc)
            except (OverflowError, OSError, ValueError):
                return None

        if isinstance(value, str):
            text = value.strip()
            if not text:
                return None

            if text.endswith("Z"):
                text = text[:-1] + "+00:00"

            try:
                parsed = datetime.fromisoformat(text)
                return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
            except ValueError:
                pass

            formats = (
                "%Y-%m-%d %H:%M:%S.%f%z",
                "%Y-%m-%d %H:%M:%S%z",
                "%Y-%m-%d %H:%M:%S.%f",
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d",
            )

            for fmt in formats:
                try:
                    parsed = datetime.strptime(text, fmt)
                    if "%z" in fmt:
                        return parsed.astimezone(timezone.utc)
                    return parsed.replace(tzinfo=timezone.utc)
                except ValueError:
                    continue

        return None