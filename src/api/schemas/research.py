"""
Research operation schemas.
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class ResearchRunRequest(BaseModel):
    """Request to run research generation."""

    topic: str = Field(
        ...,
        description="Research topic to analyze",
        json_schema_extra={"examples": ["Korean apartment horror", "Urban isolation fear"]}
    )
    tags: List[str] = Field(
        default=[],
        description="Optional tags for categorization",
        json_schema_extra={"examples": [["urban", "isolation"], ["supernatural"]]}
    )
    model: Optional[str] = Field(
        default=None,
        description="Model selection. Options: null/'qwen3:30b' (Ollama default), 'gemini' (Gemini API), 'deep-research' (Gemini Deep Research Agent - recommended). Gemini requires GEMINI_ENABLED=true",
        json_schema_extra={"examples": ["qwen3:30b", "gemini", "deep-research"]}
    )
    timeout: Optional[int] = Field(
        default=None,
        description="Timeout in seconds. Recommended: 60 (Ollama), 120 (gemini), 300-600 (deep-research)",
        json_schema_extra={"examples": [60, 120, 300]}
    )
    # v1.4.3: Webhook support for sync endpoints
    webhook_url: Optional[str] = Field(
        default=None,
        description="Webhook URL for completion notification (fire-and-forget)",
        json_schema_extra={"examples": ["https://example.com/webhook"]}
    )


class ResearchRunResponse(BaseModel):
    """Response from research generation."""

    card_id: str = Field(..., description="Generated card ID")
    status: str = Field(..., description="Execution status")
    message: Optional[str] = Field(default=None, description="Status message")
    output_path: Optional[str] = Field(default=None, description="Path to output file")
    # v1.4.3: Webhook notification status
    webhook_triggered: bool = Field(
        default=False,
        description="Whether a webhook notification was triggered"
    )


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


class ResearchDedupCheckRequest(BaseModel):
    """Request to check research card for semantic duplicates."""

    card_id: str = Field(..., description="Card ID to check for duplicates")


class SimilarCard(BaseModel):
    """Summary of a similar research card."""

    card_id: str
    similarity_score: float
    title: Optional[str] = None


class ResearchDedupCheckResponse(BaseModel):
    """Response from research semantic dedup check."""

    card_id: str = Field(..., description="Checked card ID")
    signal: str = Field(..., description="Dedup signal: LOW, MEDIUM, or HIGH")
    similarity_score: float = Field(..., description="Highest similarity score (0.0-1.0)")
    nearest_card_id: Optional[str] = Field(default=None, description="Most similar card ID")
    similar_cards: List[SimilarCard] = Field(default=[], description="List of similar cards")
    index_size: int = Field(default=0, description="Number of cards in FAISS index")
    message: Optional[str] = Field(default=None, description="Status message")


# =============================================================================
# Issue #21: Cross-pipeline Canonical Key Matching (Research → Templates)
# =============================================================================


class MatchingTemplateItem(BaseModel):
    """Summary of a matching template for a research card."""

    template_id: str = Field(..., description="Template ID (e.g., T-SYS-001)")
    template_name: str = Field(..., description="Human-readable template name")
    match_score: float = Field(..., description="Match score (0.0-1.0)")
    canonical_core: dict = Field(default={}, description="Template's canonical core values")
    match_details: Optional[dict] = Field(default=None, description="Per-dimension match breakdown")


class ResearchMatchingTemplatesRequest(BaseModel):
    """Request to find matching templates for a research card."""

    card_id: str = Field(
        ...,
        description="Research card ID to match against templates",
        json_schema_extra={"examples": ["RC-20260115-143052"]}
    )
    max_templates: int = Field(
        default=5,
        ge=1,
        le=15,
        description="Maximum number of templates to return"
    )
    min_score: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Minimum match score threshold (0.0-1.0)"
    )


class ResearchMatchingTemplatesResponse(BaseModel):
    """Response with matching templates for a research card."""

    card_id: str = Field(..., description="Research card ID that was matched")
    matching_templates: List[MatchingTemplateItem] = Field(
        default=[],
        description="List of matching templates sorted by score (highest first)"
    )
    total_templates: int = Field(..., description="Total number of templates evaluated")
    card_affinity: Optional[dict] = Field(
        default=None,
        description="The research card's canonical affinity used for matching"
    )
    message: Optional[str] = Field(default=None, description="Status message")
