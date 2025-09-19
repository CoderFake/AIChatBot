"""
LLM-based Conflict Resolution Node
Uses LLM to decide conflict resolution based on evidence quality, recency, and accuracy consensus
"""
import json
from typing import Dict, Any, List
from langchain_core.runnables import RunnableConfig
from .base import ExecutionNode
from workflows.langgraph.state.state import RAGState
from utils.logging import get_logger

logger = get_logger(__name__)


class ConflictResolutionNode(ExecutionNode):
    """
    LLM-based conflict resolution between multiple agent responses
    No hardcoded rules - LLM decides based on evidence quality
    """
    
    def __init__(self):
        super().__init__("conflict_resolution")
    
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
            provider = state.get("provider")
            if not provider:
                logger.warning("Provider not found in state, returning first response")
                return {
                    "final_answer": agent_responses[0]["content"] if agent_responses else "",
                    "resolution_method": "fallback",
                    "confidence_score": 0.5
                }
            
            responses_with_evidence = []
            for i, response in enumerate(agent_responses):
                sources = response.get("sources", [])
                
                evidence_analysis = self._analyze_evidence(sources)
                
                responses_with_evidence.append({
                    "agent_index": i,
                    "agent_name": response.get("agent_name", f"Agent_{i}"),
                    "content": response.get("content", ""),
                    "confidence": response.get("confidence", 0.0),
                    "tools_used": response.get("tools_used", []),
                    "execution_time": response.get("execution_time", 0.0),
                    "sources_count": len(sources),
                    "evidence_analysis": evidence_analysis
                })
            
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
            response = await provider.ainvoke(
                conflict_resolution_prompt,
                response_format="json_object",
                json_mode=True,
                temperature=0.1,
                max_tokens=2048,
                markdown=False 
            )
            
            if isinstance(response, dict):
                result = response
            elif hasattr(response, 'content'):
                result = json.loads(response.content.strip())
            else:
                raise RuntimeError(f"Unexpected response format: {type(response)}")
            
            logger.info(f"LLM conflict resolution completed with method: {result.get('resolution_method', 'unknown')}")
            
            return result
            
        except Exception as e:
            logger.error(f"LLM conflict resolution failed: {e}")
            
            best_response = max(agent_responses, key=lambda x: x.get("confidence", 0))
            
            return {
                "final_answer": best_response.get("content", "Unable to resolve conflicts"),
                "winning_agents": [best_response.get("agent_name", "unknown")],
                "conflict_level": "high",
                "resolution_method": "fallback_highest_confidence",
                "evidence_ranking": [{
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
                }],
                "resolution_reasoning": "LLM conflict resolution failed, using highest confidence agent",
                "combined_sources": best_response.get("sources", []),
                "confidence_score": best_response.get("confidence", 0.0)
            }
    
    def _analyze_evidence(self, sources: List[str]) -> Dict[str, Any]:
        """Analyze evidence quality from sources"""
        try:
            if not sources:
                return {
                    "total_sources": 0,
                    "recency_score": 0.0,
                    "reliability_score": 0.5,
                    "completeness_score": 0.0
                }
            
            total_sources = len(sources)
            
            recency_score = 0.8
            
            reliable_indicators = ['.gov', '.edu', '.org', 'intra.', 'wiki.']
            reliable_sources = sum(1 for source in sources 
                                 if any(indicator in str(source).lower() 
                                       for indicator in reliable_indicators))
            
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
            return {
                "total_sources": len(sources) if sources else 0,
                "recency_score": 0.5,
                "reliability_score": 0.5,
                "completeness_score": 0.5
            }