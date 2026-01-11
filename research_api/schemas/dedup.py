"""
Dedup operation schemas.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class CanonicalCore(BaseModel):
    """Canonical dimensions for a story."""

    setting: Optional[str] = None
    primary_fear: Optional[str] = None
    antagonist: Optional[str] = None
    mechanism: Optional[str] = None
    twist: Optional[str] = None


class DedupEvaluateRequest(BaseModel):
    """Request to evaluate dedup signal."""

    template_id: Optional[str] = Field(default=None, description="Template ID being used")
    canonical_core: Optional[CanonicalCore] = Field(
        default=None, description="Canonical dimensions for comparison"
    )
    title: Optional[str] = Field(default=None, description="Story title for similarity check")


class SimilarStory(BaseModel):
    """Summary of a similar story."""

    story_id: str
    template_id: str
    similarity_score: float
    matched_dimensions: List[str]


class DedupEvaluateResponse(BaseModel):
    """Response from dedup evaluation."""

    signal: str = Field(..., description="Dedup signal: LOW, MEDIUM, or HIGH")
    similarity_score: float = Field(..., description="Maximum similarity score (0.0-1.0)")
    similar_stories: List[SimilarStory] = Field(
        default=[], description="List of similar stories found"
    )
    message: Optional[str] = Field(default=None, description="Advisory message")
