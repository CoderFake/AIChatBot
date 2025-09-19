from typing import Optional, Dict, Any
from pydantic import BaseModel


class ProviderConfigRequest(BaseModel):
    is_enabled: bool
    api_keys: Optional[Dict[str, str]] = None
    provider_config: Optional[Dict[str, Any]] = None