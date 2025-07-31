"""
Milvus Service implementation
"""
from typing import List, Dict, Any, Optional
from pymilvus import MilvusClient
from services.embedding.embedding_service import embedding_service
from common.types import DBDocumentPermissionLevel
from config.settings import get_settings
from utils.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class MilvusService:
    """
    Milvus service with dual instance support following existing pattern
    """
    
    def __init__(self):
        self.public_client = None
        self.private_client = None
        self.collection_cache = {}
        self._initialize_clients()
    
    def _initialize_clients(self):
        """Initialize Milvus clients for public and private instances"""
        try:
            self.public_client = MilvusClient(
                uri=f"http://{settings.MILVUS_PUBLIC_HOST}:{settings.MILVUS_PUBLIC_PORT}"
            )
            
            self.private_client = MilvusClient(
                uri=f"http://{settings.MILVUS_PRIVATE_HOST}:{settings.MILVUS_PRIVATE_PORT}"
            )
            
            logger.info("Milvus clients initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Milvus clients: {e}")
            raise
    
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
        Create new collection using simplified approach
        """
        try:
            client.create_collection(
                collection_name=collection_name,
                dimension=settings.EMBEDDING_DIMENSIONS,
                metric_type="IP",
                index_type="HNSW",
                auto_id=True
            )
            
            logger.info(f"Successfully created collection: {collection_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create collection {collection_name}: {e}")
            return False
    
    async def search_documents(
        self,
        query: str,
        collection_name: str,
        milvus_instance: str,
        top_k: int = 10,
        score_threshold: float = 0.7,
        filter_expr: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Search documents in collection using real embeddings
        """
        try:
            await self.ensure_collection_exists(collection_name, milvus_instance)
            
            client = self._get_client(milvus_instance)
            
            query_embeddings = await embedding_service.encode_queries([query])
            query_vector = query_embeddings["dense_vectors"][0].tolist()
            
            search_results = client.search(
                collection_name=collection_name,
                data=[query_vector],
                limit=top_k,
                search_params={
                    "metric_type": "COSINE", 
                    "params": {"ef": 200}
                },
                output_fields=["text", "document_id", "department", "document_source", "metadata"],
                filter=filter_expr
            )
            
            processed_results = []
            for hits in search_results:
                for hit in hits:
                    if hit.distance >= score_threshold:
                        entity = hit.entity
                        processed_results.append({
                            "id": entity.get("document_id", "unknown"),
                            "content": entity.get("text", ""),
                            "score": float(hit.distance),
                            "metadata": {
                                "document_id": entity.get("document_id", "unknown"),
                                "department": entity.get("department", "unknown"),
                                "document_source": entity.get("document_source", "unknown"),
                                **entity.get("metadata", {})
                            }
                        })
            
            logger.info(f"Found {len(processed_results)} results in {collection_name}")
            return processed_results
            
        except Exception as e:
            logger.error(f"Search failed in collection {collection_name}: {e}")
            return []
    
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
            for i, doc in enumerate(documents):
                insert_data.append({
                    "vector": dense_vectors[i].tolist(),
                    "text": doc["text"],
                    "document_id": doc["document_id"],
                    "department": doc["department"],
                    "document_source": doc["document_source"],
                    "metadata": doc.get("metadata", {})
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
        department_name: str
    ) -> Dict[str, bool]:
        """
        Create both public and private collections for a department
        """
        results = {}
        
        public_collection = f"{department_name}_public"
        results["public"] = await self.ensure_collection_exists(
            public_collection, 
            DBDocumentPermissionLevel.PUBLIC.value
        )
        
        private_collection = f"{department_name}_private"
        results["private"] = await self.ensure_collection_exists(
            private_collection,
            DBDocumentPermissionLevel.PRIVATE.value
        )
        
        return results
    
    def get_collection_stats(self) -> Dict[str, Any]:
        """
        Get comprehensive collection statistics across both instances
        """
        try:
            stats = {
                "total_collections": len(self.collection_cache),
                "cached_collections": list(self.collection_cache.keys()),
                "public_instance": {
                    "host": settings.MILVUS_PUBLIC_HOST,
                    "port": settings.MILVUS_PUBLIC_PORT,
                    "collections": []
                },
                "private_instance": {
                    "host": settings.MILVUS_PRIVATE_HOST, 
                    "port": settings.MILVUS_PRIVATE_PORT,
                    "collections": []
                }
            }
            
            try:
                public_collections = self.public_client.list_collections()
                stats["public_instance"]["collections"] = public_collections
                stats["public_instance"]["count"] = len(public_collections)
            except Exception as e:
                logger.error(f"Failed to get public collections: {e}")
                stats["public_instance"]["error"] = str(e)
            
            try:
                private_collections = self.private_client.list_collections()
                stats["private_instance"]["collections"] = private_collections
                stats["private_instance"]["count"] = len(private_collections)
            except Exception as e:
                logger.error(f"Failed to get private collections: {e}")
                stats["private_instance"]["error"] = str(e)
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get collection stats: {e}")
            return {
                "total_collections": len(self.collection_cache),
                "cached_collections": list(self.collection_cache.keys()),
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


    def clear_cache(self):
        """Clear collection existence cache"""
        self.collection_cache.clear()
        logger.info("Cleared Milvus collection cache")


milvus_service = MilvusService()