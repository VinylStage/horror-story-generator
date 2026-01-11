"""
Dedup operations router.

Endpoints:
- POST /dedup/evaluate - Evaluate dedup signal for a story
"""

from fastapi import APIRouter

from ..schemas.dedup import (
    DedupEvaluateRequest,
    DedupEvaluateResponse,
)

router = APIRouter()


@router.post("/evaluate", response_model=DedupEvaluateResponse)
async def evaluate_dedup(request: DedupEvaluateRequest):
    """
    Evaluate deduplication signal for a story.

    Returns similarity signal (LOW/MEDIUM/HIGH) based on
    canonical dimension matching.

    Stub response for skeleton implementation.
    """
    # TODO: STEP 3 - Connect to story_registry for similarity check
    return DedupEvaluateResponse(
        signal="LOW",
        similarity_score=0.0,
        similar_stories=[],
        message="Stub response - dedup evaluation pending",
    )
