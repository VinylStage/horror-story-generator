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
)

router = APIRouter()


@router.post("/run", response_model=ResearchRunResponse)
async def run_research(request: ResearchRunRequest):
    """
    Execute research generation via Ollama.

    This endpoint triggers research_executor CLI via subprocess.
    Stub response for skeleton implementation.
    """
    # TODO: STEP 3 - Connect to research_executor CLI
    return ResearchRunResponse(
        card_id="RC-00000000-000000",
        status="stub",
        message="Stub response - CLI integration pending",
    )


@router.post("/validate", response_model=ResearchValidateResponse)
async def validate_research(request: ResearchValidateRequest):
    """
    Validate an existing research card.

    Stub response for skeleton implementation.
    """
    # TODO: STEP 3 - Connect to research_executor validate command
    return ResearchValidateResponse(
        card_id=request.card_id,
        is_valid=True,
        quality_score="stub",
        message="Stub response - validation pending",
    )


@router.get("/list", response_model=ResearchListResponse)
async def list_research(
    limit: int = Query(default=10, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    quality: Optional[str] = Query(default=None),
):
    """
    List research cards with optional filtering.

    Stub response for skeleton implementation.
    """
    # TODO: STEP 3 - Connect to research_executor list command
    return ResearchListResponse(
        cards=[],
        total=0,
        limit=limit,
        offset=offset,
        message="Stub response - list pending",
    )
