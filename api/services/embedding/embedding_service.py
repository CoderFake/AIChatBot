"""
Embedding service implementation using Hugging Face BAAI/bge-m3
"""
from typing import List, Dict, Any, Optional
import numpy as np
from sentence_transformers import SentenceTransformer
from config.settings import get_settings
from utils.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class EmbeddingService:
    """
    BGE-M3 embedding service using sentence-transformers
    """
    
    def __init__(self):
        self.model = None
        self._initialize_model()
    
    def _initialize_model(self):
        """Initialize BGE-M3 model using sentence-transformers"""
        try:
            self.model = SentenceTransformer(
                'BAAI/bge-m3',
                device=settings.DEVICE,
                trust_remote_code=True
            )
            
            logger.info("BGE-M3 embedding model initialized successfully using sentence-transformers")
            
        except Exception as e:
            logger.error(f"Failed to initialize BGE-M3 model: {e}")
            raise
    
    async def encode_documents(self, documents: List[str]) -> Dict[str, Any]:
        """
        Encode documents with dense embeddings
        
        Args:
            documents: List of document texts to encode
            
        Returns:
            Dictionary with dense_vectors
        """
        try:
            if not documents:
                return {"dense_vectors": []}
            
            embeddings = self.model.encode(
                documents,
                batch_size=settings.EMBEDDING_BATCH_SIZE,
                normalize_embeddings=True,
                convert_to_numpy=True,
                show_progress_bar=False
            )
            
            return {
                "dense_vectors": embeddings
            }
            
        except Exception as e:
            logger.error(f"Document encoding failed: {e}")
            raise
    
    async def encode_queries(self, queries: List[str]) -> Dict[str, Any]:
        """
        Encode queries for search
        
        Args:
            queries: List of query texts to encode
            
        Returns:
            Dictionary with dense_vectors
        """
        try:
            if not queries:
                return {"dense_vectors": []}
            
            embeddings = self.model.encode(
                queries,
                batch_size=settings.EMBEDDING_BATCH_SIZE,
                normalize_embeddings=True,
                convert_to_numpy=True,
                show_progress_bar=False
            )
            
            return {
                "dense_vectors": embeddings
            }
            
        except Exception as e:
            logger.error(f"Query encoding failed: {e}")
            raise
    
    def compute_similarity(
        self, 
        query_embedding: np.ndarray, 
        doc_embeddings: List[np.ndarray]
    ) -> List[float]:
        """
        Compute cosine similarity scores between query and documents
        
        Args:
            query_embedding: Query embedding vector  
            doc_embeddings: List of document embedding vectors
            
        Returns:
            List of similarity scores
        """
        try:
            scores = []
            for doc_emb in doc_embeddings:
                score = np.dot(query_embedding, doc_emb)
                scores.append(float(score))
            return scores
                
        except Exception as e:
            logger.error(f"Similarity computation failed: {e}")
            return [0.0] * len(doc_embeddings)
    
    def get_embedding_dimension(self) -> int:
        """Get embedding dimension"""
        return 1024 

embedding_service = EmbeddingService()