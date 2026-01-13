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
        description="Story topic. If provided, searches for matching research card or auto-generates one."
    )
    auto_research: bool = Field(
        default=True,
        description="Auto-generate research if no matching card found for topic"
    )
    model: Optional[str] = Field(
        default=None,
        description="Story model. Default: Claude Sonnet. Format: 'ollama:qwen3:30b' for Ollama"
    )
    research_model: Optional[str] = Field(
        default=None,
        description="Research model for auto-research. Default: Ollama qwen3:30b"
    )
    save_output: bool = Field(
        default=True,
        description="Save generated story to file"
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
