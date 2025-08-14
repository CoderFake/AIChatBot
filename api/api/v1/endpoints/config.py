
from fastapi import APIRouter
from typing import List
from models.schemas.responses.locale import LocaleListResponse
from utils.logging import get_logger

router = APIRouter(prefix="/others", tags=["Others"])
logger = get_logger(__name__)

@router.get("/locales", response_model=LocaleListResponse, summary="List supported UI languages")
async def get_locales() -> LocaleListResponse:
    languages: List[str] = ["vi", "en", "kr", "ja"]
    default_language = "en"
    return LocaleListResponse(languages=languages, default_language=default_language)
