from langchain_core.tools import tool
from common.types import AccessLevel
from utils.logging import get_logger
import json

logger = get_logger(__name__)


@tool
async def rag_search_tool(query: str, collection_name: str, access_level: str) -> str:
    """
    Search documents using RAG (Retrieval Augmented Generation).
    Searches in specified Milvus collections based on department and access level.
    
    Args:
        query: Search query string
        collection_name: Department collection name (e.g., "hr_documents", "finance_documents")
        access_level: Access level - "public" or "private" to determine Milvus container
        
    Returns:
        JSON string containing search context and document metadata
    """
    try:
        from services.vector.milvus_service import milvus_service


        public_search_results = await milvus_service.search_documents(
            query=query,
            collection_name=collection_name,
            milvus_instance=f"{collection_name}_public",
            top_k=10,
            score_threshold=0.7
        )
        
        if access_level == AccessLevel.PRIVATE.value:
        
            private_search_results = await milvus_service.search_documents(
                query=query,
                collection_name=collection_name,
                milvus_instance=f"{collection_name}_private",
                top_k=10,
                score_threshold=0.7
            )
        
        if not public_search_results and not private_search_results:
            return json.dumps({
                "context": "",
                "documents": [],
                "message": f"No relevant documents found in {collection_name} ({access_level}) for your query."
            }, ensure_ascii=False, indent=2)
        
        search_results = public_search_results + private_search_results
        
        context_parts = []
        documents = []
        
        for result in search_results:
            content = result.get("content", "")
            metadata = result.get("metadata", {})
            document_id = result.get("id", metadata.get("document_id", "unknown"))
            score = result.get("score", 0.0)
            
            documents.append({
                "document_id": document_id,
                "score": round(score, 3),
                "source": metadata.get("document_source", "Unknown"),
                "department": metadata.get("department", "Unknown"),
                "datetime": metadata.get("created_at", metadata.get("timestamp", "Unknown"))
            })
        
        context = "\n\n---\n\n".join(context_parts)
        
        result = {
            "context": context,
            "documents": documents,
            "total_results": len(search_results),
            "collection_searched": collection_name,
            "milvus_instance": f"{AccessLevel.PUBLIC.value}" if access_level == AccessLevel.PUBLIC.value else f"{AccessLevel.PRIVATE.value}, {AccessLevel.PUBLIC.value}",
            "access_level": access_level
        }
        
        return json.dumps(result, ensure_ascii=False, indent=2)
        
    except Exception as e:
        logger.error(f"RAG search failed: {e}")
        error_result = {
            "context": "",
            "documents": [],
            "error": f"Search failed: {str(e)}",
            "collection_searched": collection_name,
            "access_level": access_level
        }
        return json.dumps(error_result, ensure_ascii=False, indent=2)