"""
Research operation schemas.
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class ResearchRunRequest(BaseModel):
    """Request to run research generation."""

    topic: str = Field(..., description="Research topic to analyze")
    tags: List[str] = Field(default=[], description="Optional tags for categorization")
    model: Optional[str] = Field(default=None, description="Ollama model override")
    timeout: Optional[int] = Field(default=None, description="Timeout in seconds")


class ResearchRunResponse(BaseModel):
    """Response from research generation."""

    card_id: str = Field(..., description="Generated card ID")
    status: str = Field(..., description="Execution status")
    message: Optional[str] = Field(default=None, description="Status message")
    output_path: Optional[str] = Field(default=None, description="Path to output file")


class ResearchValidateRequest(BaseModel):
    """Request to validate a research card."""

    card_id: str = Field(..., description="Card ID to validate")


class ResearchValidateResponse(BaseModel):
    """Response from research validation."""

    card_id: str = Field(..., description="Validated card ID")
    is_valid: bool = Field(..., description="Whether card is valid")
    quality_score: str = Field(..., description="Quality score (good/partial/incomplete)")
    message: Optional[str] = Field(default=None, description="Validation details")


class ResearchCardSummary(BaseModel):
    """Summary of a research card for list response."""

    card_id: str
    title: str
    topic: str
    quality_score: str
    created_at: str


class ResearchListResponse(BaseModel):
    """Response from listing research cards."""

    cards: List[ResearchCardSummary] = Field(default=[], description="List of cards")
    total: int = Field(..., description="Total number of cards")
    limit: int = Field(..., description="Requested limit")
    offset: int = Field(..., description="Requested offset")
    message: Optional[str] = Field(default=None, description="Status message")
