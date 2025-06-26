from typing import Dict, Any, List, Optional, Tuple
from utils.datetime_utils import CustomDatetime as datetime
import asyncio
import math

from pymilvus import (
    connections, Collection, CollectionSchema, FieldSchema, DataType,
    utility, Index, SearchResult
)
from sentence_transformers import SentenceTransformer

from config.settings import get_settings
from utils.logging import get_logger
from core.exceptions import VectorDatabaseError
from services.types import IndexType
from services.dataclasses.milvus import ChunkingConfig, SearchResult
logger = get_logger(__name__)


class OptimizedMilvusService:
    """
    Milvus service tối ưu cho Agentic RAG
    - Collection riêng cho từng agent/domain
    - Chunking tự động theo file size
    - BM25 + Vector hybrid search
    - Reindexing tự động
    """
    
    def __init__(self):
        self.settings = get_settings()
        self.embedding_model = None
        self.collections: Dict[str, Collection] = {}
        self.collection_configs = self._get_collection_configs()
        self._initialized = False
        
    async def initialize(self):
        """Initialize Milvus connection và collections"""
        try:
            # Connect to Milvus
            connections.connect(
                alias="default",
                host=self.settings.vector_db.host,
                port=self.settings.vector_db.port,
                user=self.settings.vector_db.user,
                password=self.settings.vector_db.password
            )
            
            # Initialize embedding model
            await self._initialize_embedding_model()
            
            # Create/load collections cho từng agent
            await self._initialize_collections()
            
            # Setup reindexing scheduler
            asyncio.create_task(self._reindexing_scheduler())
            
            self._initialized = True
            logger.info("Optimized Milvus service initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Milvus service: {e}")
            raise VectorDatabaseError(f"Milvus initialization failed: {e}")
    
    async def _initialize_embedding_model(self):
        """Initialize BAAI/bge-m3 embedding model"""
        try:
            self.embedding_model = SentenceTransformer(
                self.settings.rag.get("embedding_model", "BAAI/bge-m3"),
                device=self.settings.rag.get("embedding_device", "cpu")
            )
            logger.info("Embedding model BAAI/bge-m3 loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load embedding model: {e}")
            raise
    
    def _get_collection_configs(self) -> Dict[str, Dict[str, Any]]:
        """Get collection configurations cho từng agent"""
        return {
            "hr_documents": {
                "description": "HR documents và policies",
                "agent": "hr_specialist",
                "index_type": IndexType.HNSW,
                "metric_type": "COSINE",
                "index_params": {"M": 16, "efConstruction": 200}
            },
            "finance_documents": {
                "description": "Finance documents và reports",
                "agent": "finance_specialist", 
                "index_type": IndexType.HNSW,
                "metric_type": "COSINE",
                "index_params": {"M": 16, "efConstruction": 200}
            },
            "it_documents": {
                "description": "IT documents và procedures",
                "agent": "it_specialist",
                "index_type": IndexType.IVF_FLAT,
                "metric_type": "COSINE",
                "index_params": {"nlist": 1024}
            },
            "general_documents": {
                "description": "General purpose documents",
                "agent": "general_assistant",
                "index_type": IndexType.HNSW,
                "metric_type": "COSINE", 
                "index_params": {"M": 16, "efConstruction": 200}
            }
        }
    
    async def _initialize_collections(self):
        """Initialize tất cả collections"""
        for collection_name, config in self.collection_configs.items():
            try:
                collection = await self._create_or_load_collection(collection_name, config)
                self.collections[collection_name] = collection
                logger.info(f"Collection {collection_name} ready")
            except Exception as e:
                logger.error(f"Failed to initialize collection {collection_name}: {e}")
    
    async def _create_or_load_collection(self, name: str, config: Dict[str, Any]) -> Collection:
        """Create hoặc load existing collection"""
        
        # Check if collection exists
        if utility.has_collection(name):
            collection = Collection(name)
            await self._ensure_collection_indexed(collection, config)
            return collection
        
        # Create new collection
        schema = self._create_collection_schema()
        collection = Collection(name=name, schema=schema, description=config["description"])
        
        # Create index
        await self._create_collection_index(collection, config)
        
        # Load collection
        collection.load()
        
        return collection
    
    def _create_collection_schema(self) -> CollectionSchema:
        """Create collection schema cho documents"""
        fields = [
            FieldSchema(name="id", dtype=DataType.VARCHAR, max_length=100, is_primary=True),
            FieldSchema(name="document_id", dtype=DataType.VARCHAR, max_length=100),
            FieldSchema(name="chunk_index", dtype=DataType.INT64),
            FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=10000),
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=1024),  # BAAI/bge-m3
            
            # Metadata fields
            FieldSchema(name="title", dtype=DataType.VARCHAR, max_length=500),
            FieldSchema(name="author", dtype=DataType.VARCHAR, max_length=200),
            FieldSchema(name="department", dtype=DataType.VARCHAR, max_length=100),
            FieldSchema(name="access_level", dtype=DataType.VARCHAR, max_length=50),
            FieldSchema(name="file_type", dtype=DataType.VARCHAR, max_length=20),
            FieldSchema(name="file_size", dtype=DataType.INT64),
            FieldSchema(name="created_at", dtype=DataType.INT64),  # Unix timestamp
            FieldSchema(name="updated_at", dtype=DataType.INT64),
            
            # Search optimization fields
            FieldSchema(name="language", dtype=DataType.VARCHAR, max_length=10),
            FieldSchema(name="keywords", dtype=DataType.VARCHAR, max_length=1000),
            FieldSchema(name="bm25_score", dtype=DataType.FLOAT),
        ]
        
        return CollectionSchema(
            fields=fields,
            description="Optimized document collection cho Agentic RAG"
        )
    
    async def _create_collection_index(self, collection: Collection, config: Dict[str, Any]):
        """Create index cho collection"""
        index_params = {
            "metric_type": config["metric_type"],
            "index_type": config["index_type"].value,
            "params": config["index_params"]
        }
        
        # Vector index
        collection.create_index(field_name="embedding", index_params=index_params)
        
        # Scalar indexes cho filtering
        collection.create_index(field_name="document_id")
        collection.create_index(field_name="department")
        collection.create_index(field_name="access_level")
        collection.create_index(field_name="language")
        collection.create_index(field_name="created_at")
    
    async def _ensure_collection_indexed(self, collection: Collection, config: Dict[str, Any]):
        """Ensure collection có proper indexes"""
        indexes = collection.indexes
        
        # Check if embedding field has index
        has_vector_index = any(idx.field_name == "embedding" for idx in indexes)
        
        if not has_vector_index:
            logger.info(f"Creating missing index for collection {collection.name}")
            await self._create_collection_index(collection, config)
    
    async def add_document(
        self,
        collection_name: str,
        document_id: str,
        file_content: bytes,
        filename: str,
        metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Add document to collection với optimal chunking
        
        Args:
            collection_name: Target collection
            document_id: Unique document ID
            file_content: Raw file content
            filename: Original filename
            metadata: Document metadata
            
        Returns:
            Processing result
        """
        if not self._initialized:
            await self.initialize()
        
        if collection_name not in self.collections:
            raise VectorDatabaseError(f"Collection {collection_name} not found")
        
        try:
            collection = self.collections[collection_name]
            
            # Extract text from file
            text_content = await self._extract_text_from_file(file_content, filename)
            
            # Calculate optimal chunking config
            chunking_config = self._calculate_chunking_config(len(file_content), len(text_content))
            
            # Create chunks
            chunks = await self._create_optimized_chunks(text_content, chunking_config, metadata)
            
            # Generate embeddings
            embeddings = await self._generate_embeddings([chunk["content"] for chunk in chunks])
            
            # Prepare data for insertion
            entities = self._prepare_entities(document_id, chunks, embeddings, metadata, filename)
            
            # Insert into collection
            insert_result = collection.insert(entities)
            
            # Flush to ensure data is written
            collection.flush()
            
            # Schedule reindexing if needed
            await self._schedule_reindex_if_needed(collection_name)
            
            return {
                "document_id": document_id,
                "collection": collection_name,
                "chunks_created": len(chunks),
                "chunking_config": chunking_config.__dict__,
                "insert_ids": insert_result.primary_keys,
                "status": "success"
            }
            
        except Exception as e:
            logger.error(f"Failed to add document {document_id}: {e}")
            raise VectorDatabaseError(f"Document insertion failed: {e}")
    
    async def search(
        self,
        query: str,
        collection_name: str,
        top_k: int = 10,
        threshold: float = 0.7,
        filters: Optional[Dict[str, Any]] = None,
        hybrid_search: bool = True
    ) -> List[SearchResult]:
        """
        Hybrid search với BM25 + Vector search
        
        Args:
            query: Search query
            collection_name: Target collection
            top_k: Number of results
            threshold: Similarity threshold
            filters: Additional filters
            hybrid_search: Enable BM25 + Vector hybrid
            
        Returns:
            List of search results
        """
        if not self._initialized:
            await self.initialize()
        
        if collection_name not in self.collections:
            logger.warning(f"Collection {collection_name} not found")
            return []
        
        try:
            collection = self.collections[collection_name]
            
            if hybrid_search:
                return await self._hybrid_search(collection, query, top_k, threshold, filters)
            else:
                return await self._vector_search(collection, query, top_k, threshold, filters)
                
        except Exception as e:
            logger.error(f"Search failed in {collection_name}: {e}")
            return []
    
    async def _hybrid_search(
        self,
        collection: Collection,
        query: str,
        top_k: int,
        threshold: float,
        filters: Optional[Dict[str, Any]]
    ) -> List[SearchResult]:
        """Hybrid search combining BM25 and vector search"""
        
        # Vector search
        vector_results = await self._vector_search(collection, query, top_k * 2, threshold, filters)
        
        # BM25 search (simplified implementation)
        bm25_results = await self._bm25_search(collection, query, top_k * 2, filters)
        
        # Combine and rerank results
        combined_results = self._combine_search_results(vector_results, bm25_results, query)
        
        # Return top-k results
        return combined_results[:top_k]
    
    async def _vector_search(
        self,
        collection: Collection,
        query: str,
        top_k: int,
        threshold: float,
        filters: Optional[Dict[str, Any]]
    ) -> List[SearchResult]:
        """Pure vector search"""
        
        # Generate query embedding
        query_embedding = await self._generate_embeddings([query])
        
        # Build search expression
        search_expr = self._build_search_expression(filters)
        
        # Search parameters
        search_params = {
            "metric_type": "COSINE",
            "params": {"ef": min(top_k * 4, 200)}
        }
        
        # Execute search
        results = collection.search(
            data=query_embedding,
            anns_field="embedding",
            param=search_params,
            limit=top_k,
            expr=search_expr,
            output_fields=["id", "document_id", "chunk_index", "content", "title", "author", "department"]
        )
        
        # Process results
        search_results = []
        for hits in results:
            for hit in hits:
                if hit.score >= threshold:
                    search_results.append(SearchResult(
                        id=hit.entity.get("id"),
                        score=hit.score,
                        content=hit.entity.get("content"),
                        metadata={
                            "title": hit.entity.get("title"),
                            "author": hit.entity.get("author"),
                            "department": hit.entity.get("department")
                        },
                        document_id=hit.entity.get("document_id"),
                        chunk_index=hit.entity.get("chunk_index")
                    ))
        
        return search_results
    
    async def _bm25_search(
        self,
        collection: Collection,
        query: str,
        top_k: int,
        filters: Optional[Dict[str, Any]]
    ) -> List[SearchResult]:
        """BM25 keyword search implementation"""
        
        # Simple BM25 implementation using content matching
        query_terms = query.lower().split()
        
        # Build search expression for content matching
        content_expr_parts = []
        for term in query_terms:
            content_expr_parts.append(f'content like "%{term}%"')
        
        content_expr = " or ".join(content_expr_parts)
        
        # Combine with other filters
        search_expr = self._build_search_expression(filters)
        if search_expr and content_expr:
            search_expr = f"({search_expr}) and ({content_expr})"
        elif content_expr:
            search_expr = content_expr
        
        # Query collection
        try:
            results = collection.query(
                expr=search_expr or "",
                output_fields=["id", "document_id", "chunk_index", "content", "title", "author", "department"],
                limit=top_k
            )
            
            # Calculate BM25 scores
            bm25_results = []
            for result in results:
                score = self._calculate_bm25_score(result["content"], query_terms)
                
                bm25_results.append(SearchResult(
                    id=result["id"],
                    score=score,
                    content=result["content"],
                    metadata={
                        "title": result.get("title"),
                        "author": result.get("author"), 
                        "department": result.get("department")
                    },
                    document_id=result["document_id"],
                    chunk_index=result["chunk_index"]
                ))
            
            # Sort by BM25 score
            bm25_results.sort(key=lambda x: x.score, reverse=True)
            return bm25_results
            
        except Exception as e:
            logger.warning(f"BM25 search failed: {e}")
            return []
    
    def _combine_search_results(
        self,
        vector_results: List[SearchResult],
        bm25_results: List[SearchResult],
        query: str
    ) -> List[SearchResult]:
        """Combine và rerank vector và BM25 results"""
        
        # Create result map
        result_map = {}
        
        # Add vector results với weight
        for result in vector_results:
            result_map[result.id] = {
                "result": result,
                "vector_score": result.score,
                "bm25_score": 0.0
            }
        
        # Add BM25 results
        for result in bm25_results:
            if result.id in result_map:
                result_map[result.id]["bm25_score"] = result.score
            else:
                result_map[result.id] = {
                    "result": result,
                    "vector_score": 0.0,
                    "bm25_score": result.score
                }
        
        # Calculate combined scores
        combined_results = []
        for entry in result_map.values():
            # Hybrid scoring: 70% vector, 30% BM25
            combined_score = (entry["vector_score"] * 0.7) + (entry["bm25_score"] * 0.3)
            
            # Update result score
            entry["result"].score = combined_score
            combined_results.append(entry["result"])
        
        # Sort by combined score
        combined_results.sort(key=lambda x: x.score, reverse=True)
        return combined_results
    
    def _calculate_bm25_score(self, content: str, query_terms: List[str]) -> float:
        """Calculate simplified BM25 score"""
        content_lower = content.lower()
        content_terms = content_lower.split()
        
        if not content_terms:
            return 0.0
        
        # BM25 parameters
        k1 = 1.5
        b = 0.75
        avgdl = 100  # Average document length estimate
        
        score = 0.0
        doc_len = len(content_terms)
        
        for term in query_terms:
            # Term frequency
            tf = content_terms.count(term)
            if tf == 0:
                continue
            
            # IDF estimate (simplified)
            idf = math.log(1000 / (1 + tf))  # Assume corpus size of 1000
            
            # BM25 formula
            score += idf * (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * (doc_len / avgdl)))
        
        return score
    
    def _build_search_expression(self, filters: Optional[Dict[str, Any]]) -> str:
        """Build Milvus search expression từ filters"""
        if not filters:
            return ""
        
        expr_parts = []
        
        if "department" in filters:
            expr_parts.append(f'department == "{filters["department"]}"')
        
        if "access_level" in filters:
            expr_parts.append(f'access_level == "{filters["access_level"]}"')
        
        if "language" in filters:
            expr_parts.append(f'language == "{filters["language"]}"')
        
        if "date_range" in filters:
            date_range = filters["date_range"]
            if "start" in date_range:
                expr_parts.append(f'created_at >= {date_range["start"]}')
            if "end" in date_range:
                expr_parts.append(f'created_at <= {date_range["end"]}')
        
        return " and ".join(expr_parts)
    
    async def _extract_text_from_file(self, file_content: bytes, filename: str) -> str:
        """Extract text từ file content"""
        file_ext = filename.lower().split('.')[-1] if '.' in filename else ''
        
        try:
            if file_ext == 'txt':
                return file_content.decode('utf-8', errors='ignore')
            elif file_ext == 'pdf':
                return await self._extract_pdf_text(file_content)
            elif file_ext in ['docx', 'doc']:
                return await self._extract_docx_text(file_content)
            elif file_ext == 'md':
                return file_content.decode('utf-8', errors='ignore')
            else:
                logger.warning(f"Unsupported file type: {file_ext}")
                return file_content.decode('utf-8', errors='ignore')
                
        except Exception as e:
            logger.error(f"Text extraction failed for {filename}: {e}")
            return ""
    
    async def _extract_pdf_text(self, file_content: bytes) -> str:
        """Extract text từ PDF"""
        try:
            import PyPDF2
            import io
            
            pdf_reader = PyPDF2.PdfReader(io.BytesIO(file_content))
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
            return text.strip()
        except Exception as e:
            logger.error(f"PDF extraction failed: {e}")
            return ""
    
    async def _extract_docx_text(self, file_content: bytes) -> str:
        """Extract text từ DOCX"""
        try:
            import docx
            import io
            
            doc = docx.Document(io.BytesIO(file_content))
            text = ""
            for paragraph in doc.paragraphs:
                text += paragraph.text + "\n"
            return text.strip()
        except Exception as e:
            logger.error(f"DOCX extraction failed: {e}")
            return ""
    
    def _calculate_chunking_config(self, file_size: int, text_length: int) -> ChunkingConfig:
        """Calculate optimal chunking config dựa trên file size"""
        
        config = ChunkingConfig()
        
        # Adjust chunk size based on file size
        if file_size < 50 * 1024:  # < 50KB
            config.size_multiplier = 0.5
        elif file_size < 500 * 1024:  # < 500KB
            config.size_multiplier = 1.0
        elif file_size < 5 * 1024 * 1024:  # < 5MB
            config.size_multiplier = 1.5
        else:  # >= 5MB
            config.size_multiplier = 2.0
        
        # Calculate final sizes
        config.base_chunk_size = int(config.base_chunk_size * config.size_multiplier)
        config.base_overlap = int(config.base_overlap * config.size_multiplier)
        
        # Ensure within bounds
        config.base_chunk_size = max(config.min_chunk_size, 
                                   min(config.max_chunk_size, config.base_chunk_size))
        config.base_overlap = min(config.base_chunk_size // 4, config.base_overlap)
        
        logger.info(f"Chunking config: size={config.base_chunk_size}, overlap={config.base_overlap}")
        return config
    
    async def _create_optimized_chunks(
        self,
        text: str,
        config: ChunkingConfig,
        metadata: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Create optimized chunks từ text"""
        
        chunks = []
        
        # Simple sentence-aware chunking
        sentences = text.split('. ')
        current_chunk = ""
        chunk_index = 0
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            
            # Check if adding sentence exceeds chunk size
            potential_chunk = current_chunk + sentence + ". "
            
            if len(potential_chunk) <= config.base_chunk_size:
                current_chunk = potential_chunk
            else:
                # Save current chunk if it's not empty
                if current_chunk.strip():
                    chunks.append({
                        "content": current_chunk.strip(),
                        "chunk_index": chunk_index,
                        "metadata": metadata.copy()
                    })
                    chunk_index += 1
                
                # Start new chunk với overlap
                if config.base_overlap > 0 and current_chunk:
                    # Take last part for overlap
                    overlap_text = current_chunk[-config.base_overlap:]
                    current_chunk = overlap_text + sentence + ". "
                else:
                    current_chunk = sentence + ". "
        
        # Add final chunk
        if current_chunk.strip():
            chunks.append({
                "content": current_chunk.strip(),
                "chunk_index": chunk_index,
                "metadata": metadata.copy()
            })
        
        logger.info(f"Created {len(chunks)} chunks from text")
        return chunks
    
    async def _generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings sử dụng BAAI/bge-m3"""
        if not self.embedding_model:
            raise VectorDatabaseError("Embedding model not initialized")
        
        try:
            embeddings = self.embedding_model.encode(texts, normalize_embeddings=True)
            return embeddings.tolist()
        except Exception as e:
            logger.error(f"Embedding generation failed: {e}")
            raise VectorDatabaseError(f"Embedding generation failed: {e}")
    
    def _prepare_entities(
        self,
        document_id: str,
        chunks: List[Dict[str, Any]],
        embeddings: List[List[float]],
        metadata: Dict[str, Any],
        filename: str
    ) -> List[List]:
        """Prepare entities cho Milvus insertion"""
        
        timestamp = int(datetime.now().timestamp())
        
        entities = [
            [],  # id
            [],  # document_id
            [],  # chunk_index
            [],  # content
            [],  # embedding
            [],  # title
            [],  # author
            [],  # department
            [],  # access_level
            [],  # file_type
            [],  # file_size
            [],  # created_at
            [],  # updated_at
            [],  # language
            [],  # keywords
            []   # bm25_score
        ]
        
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            chunk_id = f"{document_id}_{i}"
            
            entities[0].append(chunk_id)
            entities[1].append(document_id)
            entities[2].append(chunk["chunk_index"])
            entities[3].append(chunk["content"])
            entities[4].append(embedding)
            entities[5].append(metadata.get("title", filename))
            entities[6].append(metadata.get("author", ""))
            entities[7].append(metadata.get("department", ""))
            entities[8].append(metadata.get("access_level", "public"))
            entities[9].append(filename.split('.')[-1] if '.' in filename else "unknown")
            entities[10].append(metadata.get("file_size", 0))
            entities[11].append(timestamp)
            entities[12].append(timestamp)
            entities[13].append(metadata.get("language", "vi"))
            entities[14].append(" ".join(chunk["content"].split()[:20]))  # First 20 words as keywords
            entities[15].append(0.0)  # BM25 score placeholder
        
        return entities
    
    async def delete_document(self, collection_name: str, document_id: str) -> bool:
        """Delete document từ collection"""
        if collection_name not in self.collections:
            return False
        
        try:
            collection = self.collections[collection_name]
            
            # Delete by document_id
            expr = f'document_id == "{document_id}"'
            collection.delete(expr)
            
            # Flush changes
            collection.flush()
            
            # Schedule reindexing
            await self._schedule_reindex_if_needed(collection_name)
            
            logger.info(f"Document {document_id} deleted from {collection_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete document {document_id}: {e}")
            return False
    
    async def _schedule_reindex_if_needed(self, collection_name: str):
        """Schedule reindexing nếu cần thiết"""
        collection = self.collections[collection_name]
        
        # Get collection stats
        stats = collection.get_stats()
        row_count = stats.get("row_count", 0)
        
        # Reindex nếu có > 10000 documents hoặc sau delete operations
        if row_count > 10000:
            asyncio.create_task(self._reindex_collection(collection_name))
    
    async def _reindex_collection(self, collection_name: str):
        """Reindex collection để optimize performance"""
        try:
            collection = self.collections[collection_name]
            config = self.collection_configs[collection_name]
            
            logger.info(f"Starting reindex for collection {collection_name}")
            
            # Release collection
            collection.release()
            
            # Drop old index
            collection.drop_index("embedding")
            
            # Recreate index với optimized parameters
            await self._create_collection_index(collection, config)
            
            # Reload collection
            collection.load()
            
            logger.info(f"Reindex completed for collection {collection_name}")
            
        except Exception as e:
            logger.error(f"Reindexing failed for {collection_name}: {e}")
    
    async def _reindexing_scheduler(self):
        """Background scheduler cho reindexing"""
        while True:
            try:
                # Check mỗi 6 giờ
                await asyncio.sleep(6 * 3600)
                
                # Check từng collection
                for collection_name in self.collections:
                    await self._check_and_reindex(collection_name)
                    
            except Exception as e:
                logger.error(f"Reindexing scheduler error: {e}")
    
    async def _check_and_reindex(self, collection_name: str):
        """Check và reindex collection nếu cần"""
        try:
            collection = self.collections[collection_name]
            stats = collection.get_stats()
            
            # Metrics để quyết định reindex
            row_count = stats.get("row_count", 0)
            # Có thể thêm metrics khác như query performance, fragmentation, etc.
            
            # Reindex conditions
            needs_reindex = (
                row_count > 50000 or  # Large collection
                False  # Add other conditions
            )
            
            if needs_reindex:
                await self._reindex_collection(collection_name)
                
        except Exception as e:
            logger.error(f"Reindex check failed for {collection_name}: {e}")
    
    async def health_check(self) -> bool:
        """Check Milvus service health"""
        try:
            if not self._initialized:
                return False
            
            # Check connection
            connections.get_connection_addr("default")
            
            # Check collections
            for collection_name, collection in self.collections.items():
                if not utility.has_collection(collection_name):
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False
    
    def get_collection_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics cho tất cả collections"""
        stats = {}
        
        for collection_name, collection in self.collections.items():
            try:
                collection_stats = collection.get_stats()
                stats[collection_name] = {
                    "row_count": collection_stats.get("row_count", 0),
                    "agent": self.collection_configs[collection_name]["agent"],
                    "index_type": self.collection_configs[collection_name]["index_type"].value,
                    "last_check": datetime.now().isoformat()
                }
            except Exception as e:
                stats[collection_name] = {"error": str(e)}
        
        return stats

# Global instance
milvus_service = OptimizedMilvusService()