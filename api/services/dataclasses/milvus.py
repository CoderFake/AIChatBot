from dataclasses import dataclass
from typing import Dict, Any

@dataclass
class ChunkingConfig:
    """Configuration cho text chunking"""
    base_chunk_size: int = 512
    base_overlap: int = 128
    min_chunk_size: int = 100
    max_chunk_size: int = 1024
    size_multiplier: float = 1.0

@dataclass
class SearchResult:
    """Vector search result"""
    id: str
    score: float
    content: str
    metadata: Dict[str, Any]
    document_id: str
    chunk_index: int
