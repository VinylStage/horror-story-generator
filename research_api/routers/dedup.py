"""
Dedup operations router.

Endpoints:
- POST /dedup/evaluate - Evaluate dedup signal for a story
"""

from fastapi import APIRouter

from ..schemas.dedup import (
    DedupEvaluateRequest,
    DedupEvaluateResponse,
    SimilarStory,
)
from ..services import dedup_service

router = APIRouter()


@router.post("/evaluate", response_model=DedupEvaluateResponse)
async def evaluate_dedup(request: DedupEvaluateRequest):
    """
    Evaluate deduplication signal for a story.

    Returns similarity signal (LOW/MEDIUM/HIGH) based on
    canonical dimension matching against existing stories.
    """
    # Convert Pydantic model to dict for service
    canonical_core = None
    if request.canonical_core:
        canonical_core = {
            "setting": request.canonical_core.setting or "",
            "primary_fear": request.canonical_core.primary_fear or "",
            "antagonist": request.canonical_core.antagonist or "",
            "mechanism": request.canonical_core.mechanism or "",
            "twist": request.canonical_core.twist or "",
        }

    result = await dedup_service.evaluate_dedup(
        template_id=request.template_id,
        canonical_core=canonical_core,
        title=request.title,
    )

    similar_stories = [
        SimilarStory(
            story_id=s["story_id"],
            template_id=s["template_id"],
            similarity_score=s["similarity_score"],
            matched_dimensions=s["matched_dimensions"],
        )
        for s in result.get("similar_stories", [])
    ]

    return DedupEvaluateResponse(
        signal=result.get("signal", "LOW"),
        similarity_score=result.get("similarity_score", 0.0),
        similar_stories=similar_stories,
        message=result.get("message"),
    )
