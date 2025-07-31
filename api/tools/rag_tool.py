"""
RAG Tool implementation
"""
from langchain_core.tools import tool
from typing import Dict, List, Any, Optional
from common.types import AccessLevel, DBDocumentPermissionLevel
from services.auth.permission_service import RAGPermissionService
from services.vector.milvus_service import milvus_service
from config.database import get_db_context
from utils.logging import get_logger
import json

logger = get_logger(__name__)


@tool
async def rag_search_tool(
    query: str, 
    department: str, 
    user_id: str,
    access_levels: List[str] = ["public"]
) -> str:
    """
    Search documents using RAG with flexible access level control.
    
    This tool searches through department documents based on user permissions.
    Can search in public only, private only, or both based on access_levels parameter.
    
    Args:
        query: The search query to find relevant documents
        department: Department name to search in (hr, finance, it, etc.)
        user_id: User ID for permission validation
        access_levels: List of access levels - ["public"], ["private"], or ["public", "private"]
        
    Returns:
        JSON string containing search results, context, and metadata
    """
    try:
        valid_levels = [AccessLevel.PUBLIC.value, AccessLevel.PRIVATE.value]
        access_levels = [level for level in access_levels if level in valid_levels]
        
        if not access_levels:
            access_levels = [AccessLevel.PUBLIC.value]
        
        async with get_db_context() as db_session:
            permission_service = RAGPermissionService(db_session)
            
            all_accessible_collections = []
            effective_access_levels = []
            
            for access_level in access_levels:
                has_access, accessible_collections, effective_level = await permission_service.check_rag_access_permission(
                    user_id=user_id,
                    department_name=department,
                    requested_access_level=access_level
                )
                
                if has_access and accessible_collections:
                    all_accessible_collections.extend(accessible_collections)
                    if effective_level not in effective_access_levels:
                        effective_access_levels.append(effective_level)
            
            all_accessible_collections = list(dict.fromkeys(all_accessible_collections))
            
            if not all_accessible_collections:
                return json.dumps({
                    "context": "",
                    "documents": [],
                    "error": "Access denied: No accessible collections found for requested access levels",
                    "department": department,
                    "requested_access_levels": access_levels,
                    "effective_access_levels": []
                }, ensure_ascii=False, indent=2)
            
            all_results = []
            search_summary = {
                "collections_searched": [],
                "collections_failed": [],
                "total_results_by_collection": {}
            }
            
            for collection_name in all_accessible_collections:
                try:
                    if collection_name.endswith("_public"):
                        milvus_instance = DBDocumentPermissionLevel.PUBLIC.value
                        collection_type = "public"
                    else:
                        milvus_instance = DBDocumentPermissionLevel.PRIVATE.value
                        collection_type = "private"
                    
                    collection_results = await milvus_service.search_documents(
                        query=query,
                        collection_name=collection_name,
                        milvus_instance=milvus_instance,
                        top_k=10,
                        score_threshold=0.7
                    )
                    
                    for result in collection_results:
                        result["collection"] = collection_name
                        result["collection_type"] = collection_type
                        result["milvus_instance"] = milvus_instance
                    
                    all_results.extend(collection_results)
                    search_summary["collections_searched"].append(collection_name)
                    search_summary["total_results_by_collection"][collection_name] = len(collection_results)
                    
                except Exception as e:
                    logger.warning(f"Failed to search collection {collection_name}: {e}")
                    search_summary["collections_failed"].append({
                        "collection": collection_name,
                        "error": str(e)
                    })
                    continue
            
            if not all_results:
                return json.dumps({
                    "context": "",
                    "documents": [],
                    "message": f"No relevant documents found in {department} collections for your query",
                    "department": department,
                    "requested_access_levels": access_levels,
                    "effective_access_levels": effective_access_levels,
                    "search_summary": search_summary
                }, ensure_ascii=False, indent=2)
            
            all_results.sort(key=lambda x: x.get("score", 0.0), reverse=True)
            top_results = all_results[:15]  

            context_parts = []
            documents = []
            
            for result in top_results:
                content = result.get("content", "")
                metadata = result.get("metadata", {})
                
                if content and content not in context_parts: 
                    context_parts.append(content)
                
                documents.append({
                    "document_id": result.get("id", metadata.get("document_id", "unknown")),
                    "score": round(result.get("score", 0.0), 3),
                    "source": metadata.get("document_source", "Unknown"),
                    "department": metadata.get("department", department),
                    "collection": result.get("collection", "unknown"),
                    "collection_type": result.get("collection_type", "unknown"),
                    "datetime": metadata.get("created_at", metadata.get("timestamp", "Unknown"))
                })
            
            context = "\n\n---\n\n".join(context_parts)
            
            results_by_access_level = {}
            for level in effective_access_levels:
                level_results = [doc for doc in documents if (
                    (level == AccessLevel.PUBLIC.value and doc["collection_type"] == "public") or
                    (level == AccessLevel.PRIVATE.value and doc["collection_type"] == "private")
                )]
                results_by_access_level[level] = len(level_results)
            
            result = {
                "context": context,
                "documents": documents,
                "total_results": len(all_results),
                "displayed_results": len(top_results),
                "department": department,
                "requested_access_levels": access_levels,
                "effective_access_levels": effective_access_levels,
                "results_by_access_level": results_by_access_level,
                "search_summary": search_summary,
                "search_metadata": {
                    "query": query,
                    "top_k_per_collection": 10,
                    "final_top_k": 15,
                    "score_threshold": 0.7,
                    "search_method": "multi_collection_vector_search",
                    "collections_count": len(all_accessible_collections)
                }
            }
            
            return json.dumps(result, ensure_ascii=False, indent=2)
            
    except Exception as e:
        logger.error(f"RAG search failed: {e}")
        error_result = {
            "context": "",
            "documents": [],
            "error": f"Search failed: {str(e)}",
            "department": department,
            "requested_access_levels": access_levels if 'access_levels' in locals() else ["public"]
        }
        return json.dumps(error_result, ensure_ascii=False, indent=2)