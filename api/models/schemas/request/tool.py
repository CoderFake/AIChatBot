from typing import Optional, Dict, Any
from pydantic import BaseModel



class ToolConfigRequest(BaseModel):
    is_enabled: bool
    config_data: Optional[Dict[str, Any]] = None

