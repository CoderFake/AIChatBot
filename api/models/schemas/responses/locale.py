from typing import List
from pydantic import BaseModel


class LocaleListResponse(BaseModel):
    languages: List[str]
    default_language: str


