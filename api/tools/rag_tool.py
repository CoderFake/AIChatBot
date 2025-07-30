from langchain_core.tools import tool
from utils.logging import get_logger

logger = get_logger(__name__)


@tool
async def rag_tool():
    """
    - Document search(RAG) (mmr 0,6 and 0,4)
    """
    pass