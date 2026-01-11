"""
Research operations router.

Endpoints:
- POST /research/run - Execute research generation
- POST /research/validate - Validate a research card
- GET /research/list - List research cards
"""

from typing import Optional
from fastapi import APIRouter, Query

from ..schemas.research import (
    ResearchRunRequest,
    ResearchRunResponse,
    ResearchValidateRequest,
    ResearchValidateResponse,
    ResearchListResponse,
    ResearchCardSummary,
)
from ..services import research_service

router = APIRouter()


@router.post("/run", response_model=ResearchRunResponse)
async def run_research(request: ResearchRunRequest):
    """
    Execute research generation via Ollama.

    This endpoint triggers research_executor CLI via subprocess.
    """
    result = await research_service.execute_research(
        topic=request.topic,
        tags=request.tags,
        model=request.model,
        timeout=request.timeout,
    )

    return ResearchRunResponse(
        card_id=result.get("card_id", ""),
        status=result.get("status", "error"),
        message=result.get("message"),
        output_path=result.get("output_path"),
    )


@router.post("/validate", response_model=ResearchValidateResponse)
async def validate_research(request: ResearchValidateRequest):
    """
    Validate an existing research card.
    """
    result = await research_service.validate_card(card_id=request.card_id)

    return ResearchValidateResponse(
        card_id=result.get("card_id", ""),
        is_valid=result.get("is_valid", False),
        quality_score=result.get("quality_score", "unknown"),
        message=result.get("message"),
    )


@router.get("/list", response_model=ResearchListResponse)
async def list_research(
    limit: int = Query(default=10, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    quality: Optional[str] = Query(default=None),
):
    """
    List research cards with optional filtering.
    """
    result = await research_service.list_cards(
        limit=limit,
        offset=offset,
        quality=quality,
    )

    cards = [
        ResearchCardSummary(
            card_id=c["card_id"],
            title=c["title"],
            topic=c.get("topic", ""),
            quality_score=c["quality_score"],
            created_at=c["created_at"],
        )
        for c in result.get("cards", [])
    ]

    return ResearchListResponse(
        cards=cards,
        total=result.get("total", 0),
        limit=result.get("limit", limit),
        offset=result.get("offset", offset),
        message=result.get("message"),
    )
