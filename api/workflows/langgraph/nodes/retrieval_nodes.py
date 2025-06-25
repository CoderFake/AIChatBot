from typing import Dict, Any, List, Optional
from datetime import datetime

from ..state.workflow_state import RAGWorkflowState, QueryDomain
from config.settings import get_settings
from utils.logging import get_logger

logger = get_logger(__name__)

class VectorRetrievalNode:
    """Vector-based document retrieval"""
    
    def __init__(self):
        self.settings = get_settings()
        
    async def process(self, state: RAGWorkflowState) -> RAGWorkflowState:
        """Thực hiện vector search"""
        
        try:
            from services.vector.milvus_service import milvus_service
            
            query = state["query"]
            accessible_collections = state.get("accessible_collections", [])
            domain_classification = state.get("domain_classification", [])
            
            # Determine collections to search
            collections_to_search = self._determine_collections(
                domain_classification, 
                accessible_collections
            )
            
            # Search parameters
            top_k = self.settings.rag.get("default_top_k", 10)
            threshold = self.settings.rag.get("default_threshold", 0.7)
            
            # Perform searches
            raw_results = {}
            total_found = 0
            
            for collection in collections_to_search:
                try:
                    results = await milvus_service.search(
                        query=query,
                        collection_name=collection,
                        top_k=top_k,
                        threshold=threshold
                    )
                    raw_results[collection] = results
                    total_found += len(results)
                    
                except Exception as e:
                    logger.warning(f"Search failed for collection {collection}: {e}")
                    raw_results[collection] = []
            
            # Calculate relevance scores
            relevance_scores = self._calculate_relevance_scores(raw_results)
            
            return {
                **state,
                "raw_retrieval_results": raw_results,
                "total_documents_found": total_found,
                "relevance_scores": relevance_scores
            }
            
        except Exception as e:
            logger.error(f"Vector retrieval failed: {e}")
            return {
                **state,
                "raw_retrieval_results": {},
                "total_documents_found": 0,
                "relevance_scores": {},
                "error_messages": state.get("error_messages", []) + [f"Retrieval error: {str(e)}"]
            }
    
    def _determine_collections(self, domains: List[QueryDomain], accessible: List[str]) -> List[str]:
        """Determine collections to search based on domains"""
        domain_collections = {
            QueryDomain.HR: ["hr_documents", "hr_policies"],
            QueryDomain.FINANCE: ["finance_documents", "finance_reports"],
            QueryDomain.IT: ["it_documents", "it_procedures"],
            QueryDomain.GENERAL: ["general_documents"]
        }
        
        collections = set()
        for domain in domains:
            if domain in domain_collections:
                collections.update(domain_collections[domain])
        
        # Filter by accessible collections
        return [col for col in collections if col in accessible]
    
    def _calculate_relevance_scores(self, results: Dict[str, List[Dict]]) -> Dict[str, float]:
        """Calculate relevance scores per collection"""
        scores = {}
        
        for collection, docs in results.items():
            if docs:
                scores[collection] = sum(doc.get("score", 0.0) for doc in docs) / len(docs)
            else:
                scores[collection] = 0.0
        
        return scores


class HybridRetrievalNode:
    """Hybrid retrieval combining vector and keyword search"""
    
    def __init__(self):
        self.settings = get_settings()
        
    async def process(self, state: RAGWorkflowState) -> RAGWorkflowState:
        """Hybrid search combining vector và keyword"""
        
        try:
            # Vector search results (from previous node)
            vector_results = state.get("raw_retrieval_results", {})
            
            # Keyword search
            keyword_results = await self._keyword_search(
                state["query"],
                state.get("accessible_collections", [])
            )
            
            # Combine and rerank
            combined_results = self._combine_results(vector_results, keyword_results)
            reranked_results = self._rerank_results(combined_results, state["query"])
            
            return {
                **state,
                "raw_retrieval_results": reranked_results,
                "hybrid_search_metadata": {
                    "vector_results_count": sum(len(docs) for docs in vector_results.values()),
                    "keyword_results_count": sum(len(docs) for docs in keyword_results.values()),
                    "combined_count": sum(len(docs) for docs in reranked_results.values())
                }
            }
            
        except Exception as e:
            logger.error(f"Hybrid retrieval failed: {e}")
            return state
    
    async def _keyword_search(self, query: str, collections: List[str]) -> Dict[str, List[Dict]]:
        """Keyword-based search"""
        return {}
    
    def _combine_results(self, vector_results: Dict, keyword_results: Dict) -> Dict:
        """Combine vector and keyword results"""
        combined = {}
        
        all_collections = set(vector_results.keys()) | set(keyword_results.keys())
        
        for collection in all_collections:
            vec_docs = vector_results.get(collection, [])
            key_docs = keyword_results.get(collection, [])
            
            # Merge and deduplicate
            seen_ids = set()
            combined_docs = []
            
            for doc in vec_docs + key_docs:
                doc_id = doc.get("id", "")
                if doc_id not in seen_ids:
                    seen_ids.add(doc_id)
                    combined_docs.append(doc)
            
            combined[collection] = combined_docs
        
        return combined
    
    def _rerank_results(self, results: Dict, query: str) -> Dict:
        """Rerank combined results"""
        # Simple reranking based on scores
        for collection, docs in results.items():
            results[collection] = sorted(docs, key=lambda x: x.get("score", 0.0), reverse=True)
        
        return results
