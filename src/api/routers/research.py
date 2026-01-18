"""
Research operations router.

Endpoints:
- POST /research/run - Execute research generation
- POST /research/validate - Validate a research card
- GET /research/list - List research cards
- POST /research/dedup - Check semantic duplicates via FAISS
- POST /research/matching-templates - Find matching templates for a research card (Issue #21)

v1.4.3: Added webhook support for /research/run endpoint.
"""

from typing import Optional
from fastapi import APIRouter, HTTPException, Query

from ..schemas.research import (
    ResearchRunRequest,
    ResearchRunResponse,
    ResearchValidateRequest,
    ResearchValidateResponse,
    ResearchListResponse,
    ResearchCardSummary,
    ResearchDedupCheckRequest,
    ResearchDedupCheckResponse,
    SimilarCard,
    # Issue #21: Cross-pipeline matching
    ResearchMatchingTemplatesRequest,
    ResearchMatchingTemplatesResponse,
    MatchingTemplateItem,
)
from ..services import research_service
from src.infra.webhook import fire_and_forget_webhook

router = APIRouter()


@router.post("/run", response_model=ResearchRunResponse)
async def run_research(request: ResearchRunRequest):
    """
    Execute research generation via Ollama.

    This endpoint triggers src.research.executor CLI via subprocess.

    v1.4.3: Supports webhook_url for completion notification (fire-and-forget).

    Raises:
        HTTPException: 502 on LLM/model errors, 504 on timeout
    """
    result = await research_service.execute_research(
        topic=request.topic,
        tags=request.tags,
        model=request.model,
        timeout=request.timeout,
    )

    # Propagate errors as HTTP errors (Issue #2)
    status = result.get("status", "error")
    if status == "error":
        # v1.4.3: Fire webhook for error case before raising
        if request.webhook_url:
            fire_and_forget_webhook(
                url=request.webhook_url,
                endpoint="/research/run",
                status="error",
                result={"error": result.get("message") or "Research generation failed"},
            )
        raise HTTPException(
            status_code=502,
            detail=result.get("message") or "Research generation failed"
        )
    elif status == "timeout":
        # v1.4.3: Fire webhook for timeout case before raising
        if request.webhook_url:
            fire_and_forget_webhook(
                url=request.webhook_url,
                endpoint="/research/run",
                status="error",
                result={"error": result.get("message") or "Research generation timed out"},
            )
        raise HTTPException(
            status_code=504,
            detail=result.get("message") or "Research generation timed out"
        )

    # v1.4.3: Fire webhook for success case
    webhook_triggered = False
    if request.webhook_url:
        webhook_triggered = fire_and_forget_webhook(
            url=request.webhook_url,
            endpoint="/research/run",
            status="success",
            result={
                "card_id": result.get("card_id", ""),
                "output_path": result.get("output_path"),
                "message": result.get("message"),
            },
        )

    return ResearchRunResponse(
        card_id=result.get("card_id", ""),
        status=status,
        message=result.get("message"),
        output_path=result.get("output_path"),
        webhook_triggered=webhook_triggered,
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


@router.post("/dedup", response_model=ResearchDedupCheckResponse)
async def check_research_dedup(request: ResearchDedupCheckRequest):
    """
    Check semantic duplicates for a research card using FAISS embeddings.

    Uses nomic-embed-text model via Ollama for semantic similarity.
    Returns similarity against existing indexed research cards.
    """
    result = await research_service.check_semantic_dedup(card_id=request.card_id)

    similar_cards = [
        SimilarCard(
            card_id=c["card_id"],
            similarity_score=c["similarity_score"],
            title=c.get("title"),
        )
        for c in result.get("similar_cards", [])
    ]

    return ResearchDedupCheckResponse(
        card_id=result.get("card_id", request.card_id),
        signal=result.get("signal", "LOW"),
        similarity_score=result.get("similarity_score", 0.0),
        nearest_card_id=result.get("nearest_card_id"),
        similar_cards=similar_cards,
        index_size=result.get("index_size", 0),
        message=result.get("message"),
    )


# =============================================================================
# Issue #21: Cross-pipeline Canonical Key Matching (Research → Templates)
# =============================================================================


@router.post("/matching-templates", response_model=ResearchMatchingTemplatesResponse)
async def get_matching_templates(request: ResearchMatchingTemplatesRequest):
    """
    Find matching templates for a research card based on canonical affinity.

    This endpoint implements bi-directional cross-pipeline matching (Issue #21):
    Given a research card's canonical_affinity (arrays), find templates whose
    canonical_core values (single values) match.

    Uses weighted scoring (same as forward matching):
    - primary_fear: 1.5
    - mechanism: 1.3
    - antagonist: 1.2
    - setting: 1.0

    Default minimum score threshold is 0.5 (stricter than forward matching's 0.25).
    """
    result = await research_service.get_matching_templates(
        card_id=request.card_id,
        max_templates=request.max_templates,
        min_score=request.min_score,
    )

    # Check if card was not found
    if result.get("message") and "not found" in result.get("message", ""):
        raise HTTPException(
            status_code=404,
            detail=result.get("message")
        )

    matching_templates = [
        MatchingTemplateItem(
            template_id=t["template_id"],
            template_name=t["template_name"],
            match_score=t["match_score"],
            canonical_core=t.get("canonical_core", {}),
            match_details=t.get("match_details"),
        )
        for t in result.get("matching_templates", [])
    ]

    return ResearchMatchingTemplatesResponse(
        card_id=result.get("card_id", request.card_id),
        matching_templates=matching_templates,
        total_templates=result.get("total_templates", 0),
        card_affinity=result.get("card_affinity"),
        message=result.get("message"),
    )
