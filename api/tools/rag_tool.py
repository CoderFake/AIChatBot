"""
RAG Tool implementation
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Type
import uuid
from langchain_core.tools import BaseTool
from langchain_core.callbacks import AsyncCallbackManagerForToolRun, CallbackManagerForToolRun
from pydantic import BaseModel

from common.types import AccessLevel
from models.models import RAGSearchInput
from utils.logging import get_logger
from config.settings import get_settings
import json
from sqlalchemy import select

from models.database.document import Document

settings = get_settings()

logger = get_logger(__name__)


class RAGSearchTool(BaseTool):
    """
    RAG search tool wrapper for LangChain integration
    Returns raw JSON results without formatting to preserve full context
    """
    name: str = "rag_search"
    description: str = "Search through documents using semantic similarity based on user's department and access levels. Returns relevant information from knowledge base."
    args_schema: Type[BaseModel] = RAGSearchInput
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        logger.info("Initialized RAG search tool")

    def _run(
        self,
        query: str,
        department: str,
        user_id: str,
        access_levels: List[str] = ["public"],
        access_scope_override: Optional[str] = None,
        user_role: Optional[str] = None,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> dict:
        """
        Execute RAG search synchronously
        
        Args:
            query: The search query to find relevant documents
            department: Department name to search in (hr, finance, it, etc.)
            user_id: User ID for permission validation
            access_levels: List of access levels - ["public"], ["private"], or ["public", "private"]
            run_manager: Callback manager for tool run
            
        Returns:
            JSON string containing search results, context, and metadata
        """
        try:
            import asyncio
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        asyncio.run,
                        self._async_search(
                            query,
                            department,
                            user_id,
                            access_levels,
                            access_scope_override,
                            user_role=user_role,
                        )
                    )
                    return future.result()

            return asyncio.run(
                self._async_search(
                    query,
                    department,
                    user_id,
                    access_levels,
                    access_scope_override,
                    user_role=user_role,
                )
            )
            
        except Exception as e:
            error_msg = f"RAG search failed: {str(e)}"
            logger.error(f"RAG search error for user {user_id}: {e}")
            return {
                "context": "",
                "documents": [],
                "sources": [],
                "error": error_msg,
                "department": department,
                "user_id": user_id
            }

    async def _arun(
        self,
        query: str,
        department: str,
        user_id: str,
        access_levels: List[str] = ["public"],
        access_scope_override: Optional[str] = None,
        user_role: Optional[str] = None,
        run_manager: Optional[AsyncCallbackManagerForToolRun] = None,
    ) -> dict:
        """
        Execute RAG search asynchronously

        Args:
            query: The search query to find relevant documents
            department: Department name to search in (hr, finance, it, etc.)
            user_id: User ID for permission validation
            access_levels: List of access levels - ["public"], ["private"], or ["public", "private"]
            access_scope_override: Override access scope ('public', 'private', 'both', or None)
            run_manager: Async callback manager for tool run

        Returns:
            Dict containing search results, sources, and metadata
        """
        try:
            if run_manager:
                await run_manager.on_tool_start(
                    serialized={"name": self.name},
                    input_str=f"Query: {query}, Department: {department}, User: {user_id}"
                )
            
            logger.info(f"Async RAG search - User: {user_id}, Dept: {department}, Query: {query[:50]}...")

            if access_scope_override:
                if access_scope_override == "public":
                    effective_access_levels = ["public"]
                elif access_scope_override == "private":
                    effective_access_levels = ["private"]
                elif access_scope_override == "both":
                    effective_access_levels = ["public", "private"]
                else:
                    effective_access_levels = access_levels
                logger.info(f"Access scope override applied: {access_scope_override} -> {effective_access_levels}")
            else:
                effective_access_levels = access_levels

            results = await self._async_search(
                query,
                department,
                user_id,
                effective_access_levels,
                access_scope_override,
                user_role=user_role,
            )

            if run_manager:
                await run_manager.on_tool_end(json.dumps(results, ensure_ascii=False))

            return results
            
        except Exception as e:
            error_msg = f"RAG search failed: {str(e)}"
            logger.error(f"Async RAG search error for user {user_id}: {e}")
            
            if run_manager:
                await run_manager.on_tool_error(e)

            return {
                "context": "",
                "documents": [],
                "sources": [],
                "error": error_msg,
                "department": department,
                "user_id": user_id
            }

    @staticmethod
    def _parse_datetime(value: Any) -> Optional[datetime]:
        """Parse different datetime formats into a timezone-aware datetime."""

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

            # Try ISO format first
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

    async def _async_search(
        self,
        query: str,
        department: str,
        user_id: str,
        access_levels: List[str] = ["public"],
        access_scope_override: Optional[str] = None,
        user_role: Optional[str] = None
    ) -> str:
        """
        Core async search implementation
        Returns raw JSON results without any formatting to preserve full context

        Args:
            query: The search query to find relevant documents
            department: Department name to search in (hr, finance, it, etc.)
            user_id: User ID for permission validation
            access_levels: List of access levels - ["public"], ["private"], or ["public", "private"]
            access_scope_override: Override access scope for permission check
            user_role: Optional user role hint for cross-department admin access

        Returns:
            JSON string containing search results, context, and metadata
        """
        try:
            from config.database import get_db_context
            from services.auth.permission_service import RAGPermissionService
            from services.vector.milvus_service import milvus_service

            valid_levels = [AccessLevel.PUBLIC.value, AccessLevel.PRIVATE.value]
            access_levels = [level for level in access_levels if level in valid_levels]

            if not access_levels:
                access_levels = [AccessLevel.PUBLIC.value]

            normalized_role = user_role.upper() if isinstance(user_role, str) else ""
            normalized_department = (department or "").strip()

            async with get_db_context() as db_session:
                permission_service = RAGPermissionService(db_session)

                all_accessible_collections = []
                effective_access_levels = []

                admin_cross_department_access = False
                if normalized_role in {"ADMIN", "MAINTAINER", "TENANT_ADMIN"}:
                    if (access_scope_override and access_scope_override == "both") or not normalized_department:
                        admin_cross_department_access = True
                    elif normalized_department.lower() in {"all", "both", "*", "any"}:
                        admin_cross_department_access = True

                for access_level in access_levels:
                    has_access, accessible_collections, effective_level = await permission_service.check_rag_access_with_override(
                        user_id=user_id,
                        department_name=normalized_department,
                        requested_access_level=access_level,
                        access_scope_override=access_scope_override,
                        admin_cross_department_access=admin_cross_department_access
                    )

                    if has_access and accessible_collections:
                        all_accessible_collections.extend(accessible_collections)
                        if effective_level not in effective_access_levels:
                            effective_access_levels.append(effective_level)

                all_accessible_collections = list(dict.fromkeys(all_accessible_collections))

                if not all_accessible_collections:
                    return {
                        "context": "",
                        "documents": [],
                        "sources": [],
                        "error": "Access denied: No accessible collections found for requested access levels",
                        "department": normalized_department or "all",
                        "requested_access_levels": access_levels,
                        "effective_access_levels": []
                    }

                all_results = []
                search_summary = {
                    "collections_searched": [],
                    "collections_failed": [],
                    "total_results_by_collection": {}
                }
                
                for collection_name in all_accessible_collections:
                    try:
                        if collection_name.endswith("_public"):
                            milvus_instance = settings.MILVUS_PUBLIC_HOST
                            collection_type = "public"
                        else:
                            milvus_instance = settings.MILVUS_PRIVATE_HOST
                            collection_type = "private"

                        department_filter = None
                        if normalized_department and normalized_department.lower() not in {"all", "both", "*", "any"}:
                            safe_department = normalized_department.replace('"', '\\"')
                            department_filter = f'department == "{safe_department}"'

                        collection_results = await milvus_service.search_documents(
                            query=query,
                            collection_name=collection_name,
                            milvus_instance=milvus_instance,
                            top_k=10,
                            score_threshold=0.7,
                            filter_expr=department_filter
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
                    return {
                        "context": "",
                        "documents": [],
                        "sources": [],
                        "message": f"No relevant documents found in {department} collections for your query",
                        "department": normalized_department or "all",
                        "requested_access_levels": access_levels,
                        "effective_access_levels": effective_access_levels,
                        "search_summary": search_summary
                    }
                
                all_results.sort(key=lambda x: x.get("score", 0.0), reverse=True)
                top_results = all_results[:15]  

                default_sort_dt = datetime.min.replace(tzinfo=timezone.utc)

                documents_candidates: List[Dict[str, Any]] = []

                for result in top_results:
                    content = result.get("content", "")
                    metadata = result.get("metadata", {})

                    created_at_value = metadata.get("created_at") or metadata.get("timestamp")
                    parsed_created_at = self._parse_datetime(created_at_value)

                    documents_candidates.append({
                        "document_id": metadata.get("document_id", result.get("id", "unknown")),
                        "content": content,
                        "score": round(result.get("score", 0.0), 3),
                        "source": metadata.get("document_source", "Unknown"),
                        "department": metadata.get("department", normalized_department or "all"),
                        "collection": result.get("collection", "unknown"),
                        "collection_type": result.get("collection_type", "unknown"),
                        "datetime": created_at_value or "Unknown",
                        "created_at": created_at_value or "Unknown",
                        "metadata": metadata,
                        "_parsed_created_at": parsed_created_at,
                    })

                best_documents: Dict[str, Dict[str, Any]] = {}

                for doc in documents_candidates:
                    key = doc.get("document_id")
                    if not key or key in {"", "unknown"}:
                        key = f"{doc.get('collection', 'unknown')}::{doc.get('source', 'document')}::{hash(doc.get('content', ''))}"

                    existing = best_documents.get(key)
                    if not existing:
                        best_documents[key] = doc
                        continue

                    new_dt = doc.get("_parsed_created_at")
                    existing_dt = existing.get("_parsed_created_at")

                    if new_dt and (not existing_dt or new_dt > existing_dt):
                        best_documents[key] = doc
                        continue

                    if not new_dt and not existing_dt and doc.get("score", 0.0) > existing.get("score", 0.0):
                        best_documents[key] = doc

                documents = list(best_documents.values())

                documents.sort(
                    key=lambda item: (
                        item.get("_parsed_created_at") or default_sort_dt,
                        item.get("score", 0.0)
                    ),
                    reverse=True
                )

                context_parts = []
                for doc in documents:
                    content = doc.get("content", "")
                    if content and content not in context_parts:
                        context_parts.append(content)

                context = "\n\n---\n\n".join(context_parts)

                document_details: Dict[str, Dict[str, Any]] = {}
                document_ids: List[str] = []
                for doc in documents:
                    doc_id = doc.get("document_id")
                    if doc_id and doc_id not in ["unknown", ""]:
                        document_ids.append(doc_id)

                if document_ids:
                    unique_ids = []
                    for doc_id in document_ids:
                        try:
                            unique_ids.append(uuid.UUID(doc_id))
                        except (TypeError, ValueError):
                            continue

                    if unique_ids:
                        db_documents = await db_session.execute(
                            select(Document).where(Document.id.in_(unique_ids))
                        )
                        for db_doc in db_documents.scalars().all():
                            document_details[str(db_doc.id)] = {
                                "title": db_doc.title or db_doc.filename,
                                "filename": db_doc.filename,
                            }

                api_base_url = getattr(settings, "API_URL", None) or f"http://localhost:{settings.APP_PORT}"
                api_base_url = str(api_base_url).rstrip("/")

                sources = []
                seen_keys = set()

                for doc in documents:
                    doc_id = str(doc.get("document_id", ""))
                    detail_info = document_details.get(doc_id, {})
                    title = detail_info.get("title") or doc.get("source") or doc.get("metadata", {}).get("source") or "Document"
                    evidence_url = None
                    if doc_id and doc_id not in ["", "unknown"]:
                        evidence_url = f"{api_base_url}/api/v1/documents/{doc_id}/download"

                    doc["title"] = title
                    if evidence_url:
                        doc["url"] = evidence_url
                        doc["evidence_url"] = evidence_url

                    evidence_entry = {
                        "document_id": doc_id,
                        "title": title,
                        "url": evidence_url,
                        "score": doc.get("score"),
                        "collection": doc.get("collection"),
                        "access_level": doc.get("collection_type"),
                        "created_at": doc.get("created_at"),
                    }

                    dedup_key = evidence_url or doc_id or title
                    if dedup_key and dedup_key not in seen_keys:
                        sources.append(evidence_entry)
                        seen_keys.add(dedup_key)

                for doc in documents:
                    doc.pop("_parsed_created_at", None)

                results_by_access_level = {}
                for level in effective_access_levels:
                    if level == "both":
                        level_results = documents
                    else:
                        level_results = [doc for doc in documents if (
                            (level == AccessLevel.PUBLIC.value and doc["collection_type"] == "public") or
                            (level == AccessLevel.PRIVATE.value and doc["collection_type"] == "private")
                        )]
                    results_by_access_level[level] = len(level_results)

                result = {
                    "context": context,
                    "documents": documents,
                    "sources": sources,
                    "total_results": len(all_results),
                    "displayed_results": len(documents),
                    "department": normalized_department or "all",
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
                
                return result

        except Exception as e:
            logger.error(f"RAG search failed: {e}")
            error_result = {
                "context": "",
                "documents": [],
                "sources": [],
                "error": f"Search failed: {str(e)}",
                "department": normalized_department or "all",
                "requested_access_levels": access_levels if 'access_levels' in locals() else ["public"]
            }
            return error_result
