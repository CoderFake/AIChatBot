from typing import List, Dict, Any, Optional, Union
import json
from datetime import datetime
from pymilvus import (
    MilvusClient,
    DataType,
    FunctionType,
    AnnSearchRequest,
    RRFRanker
)
from services.embedding.embedding_service import embedding_service
from common.types import DBDocumentPermissionLevel
from config.settings import get_settings
from utils.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class MilvusService:
    """
    Milvus 2.6 service with latest features:
    - JSON path indexing for complex queries
    - Dynamic schema for flexible data models
    - Hybrid vector + keyword search
    - Connection pooling for scalability
    """

    def __init__(self):
        self.public_client = None
        self.private_client = None
        self.collection_cache = {}
        self.function_cache = {}
        self._initialize_clients()
        self._setup_connection_pool()

    def _initialize_clients(self):
        """Initialize Milvus 2.6 clients with advanced configuration"""
        try:
            connection_config = {
                "uri": "",
                "db_name": "default",
                "token": "",
                "connect_timeout": 30,
                "request_timeout": settings.MILVUS_QUERY_TIMEOUT_MS / 1000,
                "pool_size": settings.MILVUS_CONNECTION_POOL_SIZE
            }

            public_uri = getattr(settings, 'MILVUS_PUBLIC_URI', 'http://milvus_public:19530')
            connection_config["uri"] = public_uri
            self.public_client = MilvusClient(**connection_config)

            private_uri = getattr(settings, 'MILVUS_PRIVATE_URI', 'http://milvus_private:19530')
            connection_config["uri"] = private_uri
            self.private_client = MilvusClient(**connection_config)

            logger.info("Milvus 2.6 clients initialized successfully with advanced features")

        except Exception as e:
            logger.error(f"Failed to initialize Milvus 2.6 clients: {e}")
            raise

    def _setup_connection_pool(self):
        """Setup connection pooling for better performance"""
        try:
            self.public_client.list_collections()
            self.private_client.list_collections()
            logger.info("Milvus connection pool established")
        except Exception as e:
            logger.warning(f"Connection pool test failed: {e}")
    
    def _get_client(self, milvus_instance: str) -> MilvusClient:
        """Get appropriate Milvus client based on instance type"""
        if milvus_instance == DBDocumentPermissionLevel.PUBLIC.value:
            return self.public_client
        elif milvus_instance == DBDocumentPermissionLevel.PRIVATE.value:
            return self.private_client
        else:
            raise ValueError(f"Invalid Milvus instance: {milvus_instance}")
    
    async def ensure_collection_exists(
        self, 
        collection_name: str, 
        milvus_instance: str
    ) -> bool:
        """
        Ensure collection exists, create if not found
        """
        try:
            client = self._get_client(milvus_instance)
            cache_key = f"{milvus_instance}:{collection_name}"
            
            if cache_key in self.collection_cache:
                return True
            
            if client.has_collection(collection_name):
                self.collection_cache[cache_key] = True
                logger.info(f"Collection {collection_name} exists in {milvus_instance}")
                return True
            
            success = self._create_collection(
                collection_name=collection_name,
                client=client
            )
            
            if success:
                self.collection_cache[cache_key] = True
                logger.info(f"Created collection {collection_name} in {milvus_instance}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error ensuring collection exists: {e}")
            return False
    
    def _create_collection(
        self,
        collection_name: str,
        client: MilvusClient
    ) -> bool:
        """
        Create new collection with Milvus 2.6 advanced schema
        Supports JSON indexing, dynamic fields, and RaBitQ compression
        """
        try:
            schema = {
                "fields": [
                    {
                        "name": "vector",
                        "type": DataType.FLOAT_VECTOR,
                        "dimension": settings.EMBEDDING_DIMENSIONS,
                        "params": {
                            "enable_RaBitQ": settings.MILVUS_USE_RABITQ_COMPRESSION
                        }
                    },
                    {
                        "name": "text",
                        "type": DataType.VARCHAR,
                        "max_length": 65535,
                        "enable_analyzer": True 
                    },
                    {
                        "name": "document_id",
                        "type": DataType.VARCHAR,
                        "max_length": 255
                    },
                    {
                        "name": "department",
                        "type": DataType.VARCHAR,
                        "max_length": 100
                    },
                    {
                        "name": "document_source",
                        "type": DataType.VARCHAR,
                        "max_length": 255
                    },
                    {
                        "name": "metadata",
                        "type": DataType.JSON,
                        "enable_dynamic_field": settings.MILVUS_DYNAMIC_SCHEMA_ENABLED
                    },
                    {
                        "name": "created_at",
                        "type": DataType.INT64,
                        "default_value": int(datetime.now().timestamp() * 1000)
                    }
                ],
                "enable_dynamic_field": settings.MILVUS_DYNAMIC_SCHEMA_ENABLED,
                "description": f"RAG collection for {collection_name} with Milvus 2.6 features"
            }

            client.create_collection(
                collection_name=collection_name,
                schema=schema,
                index_params={
                    "field_name": "vector",
                    "index_type": settings.MILVUS_INDEX_TYPE,
                    "metric_type": settings.MILVUS_METRIC_TYPE,
                    "params": settings.MILVUS_INDEX_PARAMS
                }
            )

            if settings.MILVUS_HYBRID_SEARCH_ENABLED:
                self._create_text_search_function(client, collection_name)

            client.load_collection(collection_name)

            logger.info(f"Successfully created Milvus 2.6 collection: {collection_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to create Milvus 2.6 collection {collection_name}: {e}")
            return False

    def _create_text_search_function(self, client: MilvusClient, collection_name: str):
        """Create text search function for hybrid search capability"""
        try:
            function_name = f"{collection_name}_text_search"

            if function_name in self.function_cache:
                return

            client.create_function(
                function_name=function_name,
                function_type=FunctionType.BM25,
                input_field_names=["text"],
                output_field_names=["sparse_vector"],
                params={
                    "k1": 1.5,
                    "b": 0.75
                }
            )

            self.function_cache[function_name] = True
            logger.info(f"Created text search function: {function_name}")

        except Exception as e:
            logger.warning(f"Failed to create text search function: {e}")
    
    async def search_documents(
        self,
        query: str,
        collection_name: str,
        milvus_instance: str,
        top_k: int = 10,
        score_threshold: float = 0.7,
        filter_expr: Optional[str] = None,
        enable_hybrid_search: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Search documents using Milvus 2.6 hybrid search (vector + keyword)
        """
        try:
            await self.ensure_collection_exists(collection_name, milvus_instance)

            client = self._get_client(milvus_instance)

            if enable_hybrid_search and settings.MILVUS_HYBRID_SEARCH_ENABLED:
                return await self._hybrid_search(
                    client, query, collection_name, top_k, score_threshold, filter_expr
                )
            else:
                return await self._vector_search_only(
                    client, query, collection_name, top_k, score_threshold, filter_expr
                )

        except Exception as e:
            logger.error(f"Search failed in collection {collection_name}: {e}")
            return []

    async def _hybrid_search(
        self,
        client: MilvusClient,
        query: str,
        collection_name: str,
        top_k: int,
        score_threshold: float,
        filter_expr: Optional[str]
    ) -> List[Dict[str, Any]]:
        """Perform hybrid vector + keyword search using Milvus 2.6"""
        try:
            query_embeddings = await embedding_service.encode_queries([query])
            query_vector = query_embeddings["dense_vectors"][0].tolist()

            vector_search = AnnSearchRequest(
                data=[query_vector],
                anns_field="vector",
                search_params={
                    "metric_type": settings.MILVUS_METRIC_TYPE,
                    "params": {"ef": 200}
                },
                limit=top_k * 2,
                expr=filter_expr
            )

            text_search = AnnSearchRequest(
                data=[query],
                anns_field="sparse_vector",
                search_params={
                    "metric_type": "BM25",
                    "params": {}
                },
                limit=top_k * 2,
                expr=filter_expr
            )

            search_results = client.hybrid_search(
                collection_name=collection_name,
                reqs=[vector_search, text_search],
                ranker=RRFRanker(k=60),
                limit=top_k,
                output_fields=["text", "document_id", "department", "document_source", "metadata", "created_at"]
            )

            return self._process_search_results(search_results, score_threshold, "hybrid")

        except Exception as e:
            logger.warning(f"Hybrid search failed, falling back to vector search: {e}")
            return await self._vector_search_only(
                client, query, collection_name, top_k, score_threshold, filter_expr
            )

    async def _vector_search_only(
        self,
        client: MilvusClient,
        query: str,
        collection_name: str,
        top_k: int,
        score_threshold: float,
        filter_expr: Optional[str]
    ) -> List[Dict[str, Any]]:
        """Fallback to vector-only search"""
        try:
            query_embeddings = await embedding_service.encode_queries([query])
            query_vector = query_embeddings["dense_vectors"][0].tolist()

            search_results = client.search(
                collection_name=collection_name,
                data=[query_vector],
                limit=top_k,
                search_params={
                    "metric_type": settings.MILVUS_METRIC_TYPE,
                    "params": {"ef": 200}
                },
                output_fields=["text", "document_id", "department", "document_source", "metadata", "created_at"],
                filter=filter_expr
            )

            return self._process_search_results(search_results, score_threshold, "vector")

        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            return []

    def _process_search_results(
        self,
        search_results: List,
        score_threshold: float,
        search_type: str
    ) -> List[Dict[str, Any]]:
        """Process and normalize search results"""
        processed_results = []

        for hits in search_results:
            for hit in hits:
                score = float(hit.distance) if hasattr(hit, 'distance') else float(hit.score)

                if score >= score_threshold:
                    entity = hit.entity if hasattr(hit, 'entity') else hit

                    metadata = entity.get("metadata", {})
                    if isinstance(metadata, str):
                        try:
                            metadata = json.loads(metadata)
                        except:
                            metadata = {}

                    processed_results.append({
                        "id": entity.get("document_id", "unknown"),
                        "content": entity.get("text", ""),
                        "score": score,
                        "search_type": search_type,
                        "metadata": {
                            "document_id": entity.get("document_id", "unknown"),
                            "department": entity.get("department", "unknown"),
                            "document_source": entity.get("document_source", "unknown"),
                            "created_at": entity.get("created_at"),
                            **metadata
                        }
                    })

        logger.info(f"Found {len(processed_results)} results using {search_type} search")
        return processed_results
    
    async def insert_documents(
        self,
        documents: List[Dict[str, Any]],
        collection_name: str,
        milvus_instance: str
    ) -> bool:
        """
        Insert documents into collection with real embeddings
        """
        try:
            await self.ensure_collection_exists(collection_name, milvus_instance)
            
            client = self._get_client(milvus_instance)
            
            texts = [doc["text"] for doc in documents]
            
            embeddings = await embedding_service.encode_documents(texts)
            dense_vectors = embeddings["dense_vectors"]
            
            insert_data = []
            current_time = int(datetime.now().timestamp() * 1000)  # Milvus timestamp format

            for i, doc in enumerate(documents):
                insert_data.append({
                    "vector": dense_vectors[i].tolist(),
                    "text": doc["text"],
                    "document_id": doc["document_id"],
                    "department": doc["department"],
                    "document_source": doc["document_source"],
                    "metadata": doc.get("metadata", {}),
                    "created_at": current_time
                })
            
            result = client.insert(
                collection_name=collection_name,
                data=insert_data
            )
            
            logger.info(f"Inserted {len(insert_data)} documents into {collection_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to insert documents into {collection_name}: {e}")
            return False
    
    async def create_department_collections(
        self,
        department_id: str
    ) -> Dict[str, bool]:
        """
        Create both public and private collections for a department using dept_id format
        Format: {dept_id}-public and {dept_id}-private
        """
        results = {}

        public_collection = f"{department_id}-public"
        results["public"] = await self.ensure_collection_exists(
            public_collection,
            DBDocumentPermissionLevel.PUBLIC.value
        )

        private_collection = f"{department_id}-private"
        results["private"] = await self.ensure_collection_exists(
            private_collection,
            DBDocumentPermissionLevel.PRIVATE.value
        )

        logger.info(f"Created collections for department {department_id}: {public_collection}, {private_collection}")
        return results
    
    def get_collection_stats(self) -> Dict[str, Any]:
        """
        Get comprehensive collection statistics with Milvus 2.6 features
        """
        try:
            stats = {
                "milvus_version": "2.6",
                "total_collections": len(self.collection_cache),
                "cached_collections": list(self.collection_cache.keys()),
                "cached_functions": list(self.function_cache.keys()),
                "features_enabled": {
                    "RaBitQ_compression": settings.MILVUS_USE_RABITQ_COMPRESSION,
                    "JSON_indexing": settings.MILVUS_JSON_INDEXING_ENABLED,
                    "dynamic_schema": settings.MILVUS_DYNAMIC_SCHEMA_ENABLED,
                    "hybrid_search": settings.MILVUS_HYBRID_SEARCH_ENABLED
                },
                "index_config": {
                    "type": settings.MILVUS_INDEX_TYPE,
                    "metric": settings.MILVUS_METRIC_TYPE,
                    "params": settings.MILVUS_INDEX_PARAMS
                },
                "performance_config": {
                    "connection_pool_size": settings.MILVUS_CONNECTION_POOL_SIZE,
                    "query_timeout_ms": settings.MILVUS_QUERY_TIMEOUT_MS,
                    "load_timeout_ms": settings.MILVUS_LOAD_TIMEOUT_MS
                },
                "public_instance": {
                    "host": settings.MILVUS_PUBLIC_HOST,
                    "port": settings.MILVUS_PUBLIC_PORT,
                    "collections": [],
                    "functions": []
                },
                "private_instance": {
                    "host": settings.MILVUS_PRIVATE_HOST,
                    "port": settings.MILVUS_PRIVATE_PORT,
                    "collections": [],
                    "functions": []
                }
            }

            try:
                public_collections = self.public_client.list_collections()
                stats["public_instance"]["collections"] = public_collections
                stats["public_instance"]["count"] = len(public_collections)

                for collection in public_collections:
                    try:
                        desc = self.public_client.describe_collection(collection)
                        stats["public_instance"][f"{collection}_schema"] = desc
                    except Exception as e:
                        logger.debug(f"Failed to describe collection {collection}: {e}")

            except Exception as e:
                logger.error(f"Failed to get public collections: {e}")
                stats["public_instance"]["error"] = str(e)

            try:
                private_collections = self.private_client.list_collections()
                stats["private_instance"]["collections"] = private_collections
                stats["private_instance"]["count"] = len(private_collections)

                for collection in private_collections:
                    try:
                        desc = self.private_client.describe_collection(collection)
                        stats["private_instance"][f"{collection}_schema"] = desc
                    except Exception as e:
                        logger.debug(f"Failed to describe collection {collection}: {e}")

            except Exception as e:
                logger.error(f"Failed to get private collections: {e}")
                stats["private_instance"]["error"] = str(e)

            return stats

        except Exception as e:
            logger.error(f"Failed to get collection stats: {e}")
            return {
                "total_collections": len(self.collection_cache),
                "cached_collections": list(self.collection_cache.keys()),
                "cached_functions": list(self.function_cache.keys()),
                "error": str(e)
            }
    
    async def bulk_delete_by_filter(
        self,
        filter_expr: str,
        collection_name: str,
        milvus_instance: str
    ) -> bool:
        """
        Bulk delete documents using complex filter expressions
        
        Args:
            filter_expr: Milvus filter expression (e.g., "department == 'hr'")
            collection_name: Target collection
            milvus_instance: Milvus instance type
            
        Returns:
            True if deletion successful
        """
        try:
            client = self._get_client(milvus_instance)
            
            if not client.has_collection(collection_name):
                logger.warning(f"Collection {collection_name} does not exist")
                return False
            
            result = client.delete(
                collection_name=collection_name,
                filter=filter_expr
            )
            
            delete_count = getattr(result, 'delete_count', 0)
            logger.info(f"Bulk deleted {delete_count} documents from {collection_name} with filter: {filter_expr}")
            
            await self.compact_collection(collection_name, milvus_instance)
            
            return True
            
        except Exception as e:
            logger.error(f"Bulk delete failed in {collection_name}: {e}")
            return False
    
    async def rebuild_collection_index(
        self,
        collection_name: str,
        milvus_instance: str,
        new_index_params: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Completely rebuild collection index with new parameters
        """
        try:
            client = self._get_client(milvus_instance)
            
            default_params = {
                "field_name": "vector",
                "index_type": "HNSW",
                "metric_type": "COSINE",
                "params": {"M": 16, "efConstruction": 200}
            }
            
            index_params = new_index_params if new_index_params else default_params
            
            client.release_collection(collection_name)
            
            try:
                client.drop_index(collection_name, "vector")
            except Exception:
                pass 
            
            client.create_index(
                collection_name=collection_name,
                **index_params
            )
            
            client.load_collection(collection_name)
            
            logger.info(f"Successfully rebuilt index for {collection_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to rebuild index for {collection_name}: {e}")
            return False

    async def compact_collection(
        self,
        collection_name: str,
        milvus_instance: str
    ) -> bool:
        """Compact collection to optimize storage"""
        try:
            client = self._get_client(milvus_instance)
            client.compact(collection_name)
            logger.info(f"Compacted collection {collection_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to compact collection {collection_name}: {e}")
            return False

    async def index_document_chunks(
        self,
        collection_name: str,
        chunks: List[Any],
        metadata: Dict[str, Any],
        milvus_instance: str
    ) -> int:
        """
        Index document chunks into Milvus collection
        
        Args:
            collection_name: Target collection name
            chunks: List of document chunks (from FileProcessor)
            metadata: Base metadata for all chunks
            milvus_instance: Milvus instance type (public/private)
            
        Returns:
            Number of chunks indexed
        """
        try:
            await self.ensure_collection_exists(collection_name, milvus_instance)
            
            documents = []
            texts = []
            
            for i, chunk in enumerate(chunks):
                if hasattr(chunk, 'page_content'):
                    text = chunk.page_content
                elif isinstance(chunk, dict):
                    text = chunk.get('content', chunk.get('text', str(chunk)))
                else:
                    text = str(chunk)
                
                texts.append(text)
                
                chunk_metadata = metadata.copy()
                if hasattr(chunk, 'metadata') and isinstance(chunk.metadata, dict):
                    chunk_metadata.update(chunk.metadata)
                elif isinstance(chunk, dict) and 'metadata' in chunk:
                    chunk_metadata.update(chunk['metadata'])
                
                documents.append({
                    "text": text,
                    "document_id": metadata.get("document_id", "unknown"),
                    "department": metadata.get("department_id", "unknown"),
                    "document_source": f"chunk_{i}",
                    "metadata": chunk_metadata
                })
            
            success = await self.insert_documents(
                documents=documents,
                collection_name=collection_name,
                milvus_instance=milvus_instance
            )
            
            if success:
                logger.info(f"Successfully indexed {len(chunks)} chunks into {collection_name}")
                return len(chunks)
            else:
                logger.error(f"Failed to index chunks into {collection_name}")
                return 0
                
        except Exception as e:
            logger.error(f"Error indexing document chunks: {e}")
            raise

    async def delete_document_vectors(
        self,
        collection_name: str,
        document_id: str
    ) -> bool:
        """
        Delete all vectors for a specific document
        
        Args:
            collection_name: Target collection name
            document_id: Document ID to delete
            
        Returns:
            True if deletion successful
        """
        try:
            filter_expr = f'document_id == "{document_id}"'
            
            try:
                public_result = await self.bulk_delete_by_filter(
                    filter_expr=filter_expr,
                    collection_name=collection_name,
                    milvus_instance=DBDocumentPermissionLevel.PUBLIC.value
                )
            except Exception as e:
                logger.debug(f"Public instance delete failed (expected if not public): {e}")
                public_result = False
            
            try:
                private_result = await self.bulk_delete_by_filter(
                    filter_expr=filter_expr,
                    collection_name=collection_name,
                    milvus_instance=DBDocumentPermissionLevel.PRIVATE.value
                )
            except Exception as e:
                logger.debug(f"Private instance delete failed (expected if not private): {e}")
                private_result = False
            
            success = public_result or private_result
            if success:
                logger.info(f"Successfully deleted vectors for document {document_id} from {collection_name}")
            else:
                logger.warning(f"No vectors found for document {document_id} in {collection_name}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error deleting document vectors: {e}")
            raise

    async def json_path_search(
        self,
        collection_name: str,
        milvus_instance: str,
        json_path: str,
        value: Any,
        top_k: int = 10,
        operator: str = "=="
    ) -> List[Dict[str, Any]]:
        """
        Search using JSON path queries (Milvus 2.6 feature)
        Example: json_path="metadata.category", value="hr", operator="=="
        """
        try:
            await self.ensure_collection_exists(collection_name, milvus_instance)
            client = self._get_client(milvus_instance)

            filter_expr = f"metadata['{json_path}'] {operator} {repr(value)}"

            search_results = client.search(
                collection_name=collection_name,
                data=[[0.0] * settings.EMBEDDING_DIMENSIONS],
                limit=top_k,
                search_params={"metric_type": settings.MILVUS_METRIC_TYPE},
                output_fields=["text", "document_id", "department", "document_source", "metadata"],
                filter=filter_expr
            )

            return self._process_search_results(search_results, 0.0, "json_path")

        except Exception as e:
            logger.error(f"JSON path search failed: {e}")
            return []

    async def add_dynamic_field(
        self,
        collection_name: str,
        milvus_instance: str,
        field_name: str,
        field_value: Any,
        filter_expr: str
    ) -> bool:
        """
        Add dynamic field to existing documents (Milvus 2.6 feature)
        Only works if dynamic schema is enabled
        """
        try:
            if not settings.MILVUS_DYNAMIC_SCHEMA_ENABLED:
                logger.warning("Dynamic schema is disabled in settings")
                return False

            client = self._get_client(milvus_instance)

            update_data = {
                f"metadata['{field_name}']": field_value
            }

            result = client.upsert(
                collection_name=collection_name,
                data=[update_data],
                filter=filter_expr
            )

            logger.info(f"Added dynamic field '{field_name}' to documents matching: {filter_expr}")
            return True

        except Exception as e:
            logger.error(f"Failed to add dynamic field: {e}")
            return False

    async def time_range_search(
        self,
        collection_name: str,
        milvus_instance: str,
        start_time: datetime,
        end_time: Optional[datetime] = None,
        top_k: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Search documents within time range using timestamp field
        """
        try:
            await self.ensure_collection_exists(collection_name, milvus_instance)
            client = self._get_client(milvus_instance)

            start_timestamp = int(start_time.timestamp() * 1000)
            end_timestamp = int((end_time or datetime.now()).timestamp() * 1000)

            filter_expr = f"created_at >= {start_timestamp} and created_at <= {end_timestamp}"

            search_results = client.search(
                collection_name=collection_name,
                data=[[0.0] * settings.EMBEDDING_DIMENSIONS],
                limit=top_k,
                search_params={"metric_type": settings.MILVUS_METRIC_TYPE},
                output_fields=["text", "document_id", "department", "document_source", "metadata", "created_at"],
                filter=filter_expr
            )

            return self._process_search_results(search_results, 0.0, "time_range")

        except Exception as e:
            logger.error(f"Time range search failed: {e}")
            return []

    async def advanced_filter_search(
        self,
        collection_name: str,
        milvus_instance: str,
        filters: Dict[str, Any],
        top_k: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Advanced search with multiple filters including JSON paths
        """
        try:
            filter_conditions = []

            for key, value in filters.items():
                if key.startswith("metadata."):
                    json_path = key.replace("metadata.", "")
                    filter_conditions.append(f"metadata['{json_path}'] == {repr(value)}")
                elif key == "time_range":
                    if isinstance(value, dict):
                        start_time = value.get("start")
                        end_time = value.get("end")
                        if start_time and end_time:
                            start_ts = int(start_time.timestamp() * 1000)
                            end_ts = int(end_time.timestamp() * 1000)
                            filter_conditions.append(f"created_at >= {start_ts} and created_at <= {end_ts}")
                else:
                    filter_conditions.append(f"{key} == {repr(value)}")

            filter_expr = " and ".join(filter_conditions) if filter_conditions else None

            return await self.search_documents(
                query="",
                collection_name=collection_name,
                milvus_instance=milvus_instance,
                top_k=top_k,
                score_threshold=0.0,
                filter_expr=filter_expr,
                enable_hybrid_search=False
            )

        except Exception as e:
            logger.error(f"Advanced filter search failed: {e}")
            return []

    def clear_cache(self):
        """Clear collection existence cache"""
        self.collection_cache.clear()
        self.function_cache.clear()
        logger.info("Cleared Milvus collection and function cache")


milvus_service = MilvusService()