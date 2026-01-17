"""
Story operation schemas.

v1.2.0: Direct story generation and listing API schemas.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class StoryGenerateRequest(BaseModel):
    """Request for direct story generation."""

    topic: Optional[str] = Field(
        default=None,
        description="Story topic. If provided, searches for matching research card or auto-generates one.",
        json_schema_extra={"examples": ["Korean apartment horror", "Subway late night encounter"]}
    )
    auto_research: bool = Field(
        default=True,
        description="Auto-generate research if no matching card found for topic"
    )
    model: Optional[str] = Field(
        default=None,
        description="Story model. Options: null (Claude Sonnet default), 'claude-sonnet-4-5-20250929', 'claude-opus-4-5-20251101', 'ollama:qwen3:30b' (local Ollama)",
        json_schema_extra={"examples": [None, "claude-sonnet-4-5-20250929", "ollama:qwen3:30b"]}
    )
    research_model: Optional[str] = Field(
        default=None,
        description="Research model for auto-research. Options: null/'qwen3:30b' (Ollama), 'gemini', 'deep-research' (Gemini Deep Research)",
        json_schema_extra={"examples": ["qwen3:30b", "gemini", "deep-research"]}
    )
    save_output: bool = Field(
        default=True,
        description="Save generated story to file"
    )
    target_length: Optional[int] = Field(
        default=None,
        ge=300,
        le=10000,
        description="Target story length in characters (soft limit, ±10%). If not provided, uses default (~3000-4000 chars).",
        json_schema_extra={"examples": [1500, 3000, 4500]}
    )
    # v1.4.3: Webhook support for sync endpoints
    webhook_url: Optional[str] = Field(
        default=None,
        description="Webhook URL for completion notification (fire-and-forget)",
        json_schema_extra={"examples": ["https://example.com/webhook"]}
    )


class StoryGenerateResponse(BaseModel):
    """Response from story generation."""

    success: bool
    story_id: Optional[str] = None
    story: Optional[str] = None
    title: Optional[str] = None
    file_path: Optional[str] = None
    word_count: Optional[int] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None
    # v1.4.3: Webhook notification status
    webhook_triggered: bool = Field(
        default=False,
        description="Whether a webhook notification was triggered"
    )


class StoryListItem(BaseModel):
    """Single story in list response."""

    story_id: str
    title: Optional[str] = None
    template_id: Optional[str] = None
    template_name: Optional[str] = None
    created_at: str
    accepted: bool
    decision_reason: Optional[str] = None
    story_signature: Optional[str] = None
    research_used: List[str] = Field(default=[])


class StoryListResponse(BaseModel):
    """Response from story list endpoint."""

    stories: List[StoryListItem] = Field(default=[])
    total: int
    message: Optional[str] = None


class StoryDetailResponse(BaseModel):
    """Response from story detail endpoint."""

    story_id: str
    title: Optional[str] = None
    template_id: Optional[str] = None
    template_name: Optional[str] = None
    semantic_summary: Optional[str] = None
    created_at: str
    accepted: bool
    decision_reason: Optional[str] = None
    story_signature: Optional[str] = None
    canonical_core: Optional[Dict[str, str]] = None
    research_used: List[str] = Field(default=[])
