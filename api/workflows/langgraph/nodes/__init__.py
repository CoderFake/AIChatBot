"""
Workflow nodes - tối ưu hóa
Gộp các nodes thành core nodes để giảm complexity
"""

from .base import BaseWorkflowNode, AnalysisNode
from .nodes import (
    QueryAnalysisNode,
    PermissionNode,
    RetrievalNode,
    SecurityNode,
    ResponseNode
)

# Import nodes từ file cũ còn sử dụng
from .permission_nodes import PermissionCheckNode, DocumentFilterNode
from .retrieval_nodes import VectorRetrievalNode, HybridRetrievalNode

__all__ = [
    # Base classes
    "BaseWorkflowNode",
    "AnalysisNode",
    
    # Core nodes (optimized)
    "QueryAnalysisNode",
    "PermissionNode", 
    "RetrievalNode",
    "SecurityNode",
    "ResponseNode",
    
    # Legacy nodes (backwards compatibility)
    "PermissionCheckNode",
    "DocumentFilterNode", 
    "VectorRetrievalNode",
    "HybridRetrievalNode"
]
