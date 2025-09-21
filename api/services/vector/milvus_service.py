from typing import List, Dict, Any, Optional
from datetime import datetime
from pymilvus import (
    MilvusClient,
    DataType,
    FunctionType,
    AnnSearchRequest,
    RRFRanker,
    CollectionSchema,
    FieldSchema
)
from langchain_milvus import Milvus
from services.embedding.embedding_service import embedding_service
from common.types import DocumentAccessLevel
from config.settings import get_settings
from utils.logging import get_logger
import json

logger = get_logger(__name__)
settings = get_settings()


class EmbeddingWrapper:
    """Wrapper to integrate our embedding service with LangChain"""
    
    def __init__(self, embedding_service):
        self.embedding_service = embedding_service
    
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Embed a list of documents"""
        import asyncio
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If in async context, we need to handle this differently
            embeddings = loop.run_until_complete(self.embedding_service.encode_documents(texts))
        else:
            embeddings = asyncio.run(self.embedding_service.encode_documents(texts))
        return embeddings["dense_vectors"].tolist()
    
    def embed_query(self, text: str) -> List[float]:
        """Embed a single query"""
        import asyncio
        loop = asyncio.get_event_loop()
        if loop.is_running():
            embeddings = loop.run_until_complete(self.embedding_service.encode_queries([text]))
        else:
            embeddings = asyncio.run(self.embedding_service.encode_queries([text]))
        return embeddings["dense_vectors"][0].tolist()


class MilvusService:
    """
    Milvus 2.6 service with latest features:
    - JSON path indexing for complex queries
    - Dynamic schema for flexible data models
    - Hybrid vector + keyword search
    - Connection pooling for scalability
    - LangChain MMR integration for diversity
    """

    def __init__(self):
        self.public_client = None
        self.private_client = None
        self.public_langchain = None
        self.private_langchain = None
        self.collection_cache = {}
        self.function_cache = {}
        self._initialize_clients()
        self._setup_connection_pool()

    def _initialize_clients(self):
        """Initialize Milvus 2.6 clients with basic configuration"""
        try:
            public_uri = getattr(settings, 'MILVUS_PUBLIC_URI', 'http://milvus_public:19530')
            private_uri = getattr(settings, 'MILVUS_PRIVATE_URI', 'http://milvus_private:19531')

            self.public_client = MilvusClient(uri=public_uri)
            self.private_client = MilvusClient(uri=private_uri)

            # Initialize LangChain clients lazily when needed
            self.public_langchain = None
            self.private_langchain = None

            logger.info("Milvus clients initialized successfully with URI-based configuration")

        except Exception as e:
            logger.error(f"Failed to initialize Milvus clients: {e}")
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
        if milvus_instance == getattr(settings, 'MILVUS_PUBLIC_HOST', 'milvus_public'):
            return self.public_client
        elif milvus_instance == getattr(settings, 'MILVUS_PRIVATE_HOST', 'milvus_private'):
            return self.private_client
        else:
            raise ValueError(f"Invalid Milvus instance: {milvus_instance}")

    def _get_langchain_client(self, milvus_instance: str, collection_name: str) -> Milvus:
        """Get appropriate LangChain Milvus client for MMR operations"""
        try:
            if milvus_instance == getattr(settings, 'MILVUS_PUBLIC_HOST', 'milvus_public'):
                if self.public_langchain is None:
                    embedding_wrapper = EmbeddingWrapper(embedding_service)
                    self.public_langchain = Milvus(
                        embedding_function=embedding_wrapper,
                        collection_name=collection_name,
                        connection_args={"uri": getattr(settings, 'MILVUS_PUBLIC_URI', 'http://milvus_public:19530')}
                    )
                return self.public_langchain
            elif milvus_instance == getattr(settings, 'MILVUS_PRIVATE_HOST', 'milvus_private'):
                if self.private_langchain is None:
                    embedding_wrapper = EmbeddingWrapper(embedding_service)
                    self.private_langchain = Milvus(
                        embedding_function=embedding_wrapper,
                        collection_name=collection_name,
                        connection_args={"uri": getattr(settings, 'MILVUS_PRIVATE_URI', 'http://milvus_private:19531')}
                    )
                return self.private_langchain
            else:
                raise ValueError(f"Invalid Milvus instance: {milvus_instance}")
        except Exception as e:
            logger.error(f"Failed to initialize LangChain Milvus client: {e}")
            raise
    
    async def ensure_collection_exists(
        self, 
        collection_name: str,
        access_level: str
    ) -> bool:
        """
        Ensure collection exists, create if not found
        """
        try:
            if access_level == DocumentAccessLevel.PUBLIC.value:
                client = self._get_client(getattr(settings, 'MILVUS_PUBLIC_HOST', 'milvus_public'))
            elif access_level == DocumentAccessLevel.PRIVATE.value:
                client = self._get_client(getattr(settings, 'MILVUS_PRIVATE_HOST', 'milvus_private'))
            else:
                raise ValueError(f"Invalid access level: {access_level}")

            if client.has_collection(collection_name):
                return True
            
            success = self._create_collection(
                collection_name=collection_name,
                client=client
            )
            
            if success:
                logger.info(f"Created collection {collection_name}")
            
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
        Fixed to use proper FieldSchema and CollectionSchema objects
        """
        try:
            fields = [
                FieldSchema(
                    name="id",
                    dtype=DataType.INT64,
                    is_primary=True,
                    auto_id=True
                ),
                FieldSchema(
                    name="vector",
                    dtype=DataType.FLOAT_VECTOR,
                    dim=getattr(settings, 'EMBEDDING_DIMENSIONS', 1024)
                ),
                FieldSchema(
                    name="text",
                    dtype=DataType.VARCHAR,
                    max_length=65535
                ),
                FieldSchema(
                    name="document_id",
                    dtype=DataType.VARCHAR,
                    max_length=255
                ),
                FieldSchema(
                    name="department",
                    dtype=DataType.VARCHAR,
                    max_length=100
                ),
                FieldSchema(
                    name="document_source",
                    dtype=DataType.VARCHAR,
                    max_length=255
                ),
                FieldSchema(
                    name="metadata",
                    dtype=DataType.JSON
                ),
                FieldSchema(
                    name="created_at",
                    dtype=DataType.INT64
                )
            ]

            schema = CollectionSchema(
                fields=fields,
                description=f"RAG collection for {collection_name} with Milvus 2.6 features",
                enable_dynamic_field=getattr(settings, 'MILVUS_DYNAMIC_SCHEMA_ENABLED', True)
            )

            client.create_collection(
                collection_name=collection_name,
                schema=schema
            )

            client.create_index(
                collection_name=collection_name,
                field_name="vector",
                index_type=getattr(settings, 'MILVUS_INDEX_TYPE', 'HNSW'),
                metric_type=getattr(settings, 'MILVUS_METRIC_TYPE', 'COSINE'),
                params=getattr(settings, 'MILVUS_INDEX_PARAMS', {"M": 16, "efConstruction": 200})
            )

            if getattr(settings, 'MILVUS_HYBRID_SEARCH_ENABLED', False):
                try:
                    self._create_text_search_function(client, collection_name)
                except Exception as e:
                    logger.warning(f"Failed to create text search function: {e}")

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
        enable_hybrid_search: bool = True,
        enable_mmr: bool = False,
        mmr_lambda: float = 0.5,
        mmr_fetch_k: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Search documents using Milvus 2.6 hybrid search (vector + keyword)
        With optional MMR for diversity
        """
        try:
            access_level = DocumentAccessLevel.PRIVATE.value if milvus_instance == getattr(settings, 'MILVUS_PRIVATE_HOST', 'milvus_private') else DocumentAccessLevel.PUBLIC.value
            await self.ensure_collection_exists(collection_name, access_level)

            if enable_mmr:
                return await self._search_with_mmr(
                    query, collection_name, milvus_instance, top_k, 
                    score_threshold, filter_expr, mmr_lambda, mmr_fetch_k
                )

            client = self._get_client(milvus_instance)

            if enable_hybrid_search and getattr(settings, 'MILVUS_HYBRID_SEARCH_ENABLED', False):
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

    async def _search_with_mmr(
        self,
        query: str,
        collection_name: str,
        milvus_instance: str,
        top_k: int,
        score_threshold: float,
        filter_expr: Optional[str],
        lambda_mult: float,
        fetch_k: int
    ) -> List[Dict[str, Any]]:
        """Search with MMR diversity using LangChain integration"""
        try:
            langchain_client = self._get_langchain_client(milvus_instance, collection_name)
            
            docs = langchain_client.max_marginal_relevance_search(
                query=query,
                k=top_k,
                fetch_k=fetch_k,
                lambda_mult=lambda_mult,
                expr=filter_expr
            )
            
            results = []
            for i, doc in enumerate(docs):
                results.append({
                    "id": doc.metadata.get("document_id", "unknown"),
                    "content": doc.page_content,
                    "score": 1.0 - (i * 0.1),  # Synthetic score based on MMR rank
                    "search_type": "mmr",
                    "mmr_rank": i + 1,
                    "metadata": {
                        "document_id": doc.metadata.get("document_id", "unknown"),
                        "department": doc.metadata.get("department", "unknown"),
                        "document_source": doc.metadata.get("document_source", "unknown"),
                        "created_at": doc.metadata.get("created_at"),
                        **doc.metadata
                    }
                })
            
            logger.info(f"Found {len(results)} results using MMR search")
            return results
            
        except Exception as e:
            logger.warning(f"MMR search failed, falling back to hybrid search: {e}")
            client = self._get_client(milvus_instance)
            return await self._hybrid_search(
                client, query, collection_name, top_k, score_threshold, filter_expr
            )

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
                    "metric_type": getattr(settings, 'MILVUS_METRIC_TYPE', 'COSINE'),
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
                    "metric_type": getattr(settings, 'MILVUS_METRIC_TYPE', 'COSINE'),
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
                        except Exception:
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

    def _sanitize_metadata(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Convert UUID and other non-JSON serializable objects to strings in metadata"""
        sanitized = {}
        for key, value in metadata.items():
            if hasattr(value, '__str__') and not isinstance(value, (str, int, float, bool, list, dict, type(None))):
                sanitized[key] = str(value)
            elif isinstance(value, dict):
                sanitized[key] = self._sanitize_metadata(value)
            elif isinstance(value, list):
                sanitized[key] = [str(item) if hasattr(item, '__str__') and not isinstance(item, (str, int, float, bool, dict, type(None))) else item for item in value]
            else:
                sanitized[key] = value
        return sanitized
    
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
            access_level = DocumentAccessLevel.PRIVATE.value if milvus_instance == getattr(settings, 'MILVUS_PRIVATE_HOST', 'milvus_private') else DocumentAccessLevel.PUBLIC.value
            await self.ensure_collection_exists(collection_name, access_level)

            client = self._get_client(milvus_instance)
            
            texts = [doc["text"] for doc in documents]
            
            embeddings = await embedding_service.encode_documents(texts)
            dense_vectors = embeddings["dense_vectors"]
            
            insert_data = []
            current_time = int(datetime.now().timestamp() * 1000)

            for i, doc in enumerate(documents):
                department_value = doc["department"]
                if hasattr(department_value, '__str__'):
                    department_str = str(department_value)
                else:
                    department_str = department_value

                document_id_value = doc["document_id"]
                if hasattr(document_id_value, '__str__'):
                    document_id_str = str(document_id_value)
                else:
                    document_id_str = document_id_value

                document_source_value = doc["document_source"]
                if hasattr(document_source_value, '__str__'):
                    document_source_str = str(document_source_value)
                else:
                    document_source_str = document_source_value

                sanitized_metadata = self._sanitize_metadata(doc.get("metadata", {}))

                insert_data.append({
                    "vector": dense_vectors[i].tolist(),
                    "text": str(doc["text"]),
                    "document_id": document_id_str,
                    "department": department_str,
                    "document_source": document_source_str,
                    "metadata": sanitized_metadata,
                    "created_at": current_time
                })
            
            client.insert(
                collection_name=collection_name,
                data=insert_data
            )
            
            logger.info(f"Inserted {len(insert_data)} documents into {collection_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to insert documents into {collection_name}: {e}")
            return False

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
            
            client.release_collection(collection_name)
            
            try:
                client.drop_index(collection_name, "vector")
            except Exception:
                pass 
            
            if new_index_params:
                client.create_index(
                    collection_name=collection_name,
                    field_name="vector",
                    index_type=new_index_params.get("index_type", "HNSW"),
                    metric_type=new_index_params.get("metric_type", "COSINE"),
                    params=new_index_params.get("params", {"M": 16, "efConstruction": 200})
                )
            else:
                client.create_index(
                    collection_name=collection_name,
                    field_name="vector",
                    index_type="HNSW",
                    metric_type="COSINE",
                    params={"M": 16, "efConstruction": 200}
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
            access_level = DocumentAccessLevel.PRIVATE.value if milvus_instance == getattr(settings, 'MILVUS_PRIVATE_HOST', 'milvus_private') else DocumentAccessLevel.PUBLIC.value
            await self.ensure_collection_exists(collection_name, access_level)

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
                
                sanitized_metadata = self._sanitize_metadata(chunk_metadata)
                
                document_id_value = metadata.get("document_id", "unknown")
                department_value = metadata.get("department_id", "unknown")
                
                documents.append({
                    "text": str(text),
                    "document_id": str(document_id_value),
                    "department": str(department_value),
                    "document_source": f"chunk_{i}",
                    "metadata": sanitized_metadata
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
                    milvus_instance=getattr(settings, 'MILVUS_PUBLIC_HOST', 'milvus_public')
                )
            except Exception as e:
                logger.debug(f"Public instance delete failed (expected if not public): {e}")
                public_result = False

            try:
                private_result = await self.bulk_delete_by_filter(
                    filter_expr=filter_expr,
                    collection_name=collection_name,
                    milvus_instance=getattr(settings, 'MILVUS_PRIVATE_HOST', 'milvus_private')
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


milvus_service = MilvusService()