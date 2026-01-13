"""
Story router for direct story generation and listing API.

v1.2.0: Adds synchronous story generation endpoint (mirrors CLI behavior).

Endpoints:
- POST /story/generate - Generate a story directly (blocking)
- GET /story/list - List stories from registry
- GET /story/{story_id} - Get story details
"""

import json
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from ..schemas.story import (
    StoryGenerateRequest,
    StoryGenerateResponse,
    StoryListItem,
    StoryListResponse,
    StoryDetailResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def extract_title_from_metadata(metadata: dict) -> Optional[str]:
    """Extract title from story metadata or skeleton info."""
    if metadata.get("skeleton_template"):
        return metadata["skeleton_template"].get("template_name")
    return None


@router.post("/generate", response_model=StoryGenerateResponse)
async def generate_story(request: StoryGenerateRequest):
    """
    Generate a story directly (blocking).

    This endpoint generates a story synchronously and returns the result.
    Use the jobs API for non-blocking generation.

    If topic is provided:
    - Searches for existing research cards matching the topic
    - If not found and auto_research=True, generates new research
    - Uses the research card for story context

    If topic is not provided:
    - Selects a random template
    - Uses existing research cards based on template affinity
    """
    try:
        from src.story.generator import generate_with_topic
        from src.registry.story_registry import StoryRegistry

        # Get registry for dedup
        registry = None
        try:
            registry = StoryRegistry()
        except Exception as e:
            logger.warning(f"[StoryAPI] Registry init failed: {e}")

        # Generate story
        result = generate_with_topic(
            topic=request.topic,
            auto_research=request.auto_research,
            model_spec=request.model,
            research_model_spec=request.research_model,
            save_output=request.save_output,
            registry=registry
        )

        if not result.get("success", True):
            return StoryGenerateResponse(
                success=False,
                error=result.get("error", "Generation failed"),
                metadata=result.get("metadata", {})
            )

        metadata = result.get("metadata", {})
        story_text = result.get("story", "")

        # Extract title from story text
        title = None
        if story_text:
            # Try to extract title from first line if it starts with #
            lines = story_text.strip().split("\n")
            if lines and lines[0].startswith("#"):
                title = lines[0].lstrip("#").strip()

        return StoryGenerateResponse(
            success=True,
            story_id=metadata.get("story_id"),
            story=story_text,
            title=title or extract_title_from_metadata(metadata),
            file_path=result.get("file_path"),
            word_count=metadata.get("word_count"),
            metadata=metadata
        )

    except Exception as e:
        logger.error(f"[StoryAPI] Generation error: {e}", exc_info=True)
        return StoryGenerateResponse(
            success=False,
            error=str(e)
        )


@router.get("/list", response_model=StoryListResponse)
async def list_stories(
    limit: int = Query(default=50, ge=1, le=500, description="Maximum stories to return"),
    offset: int = Query(default=0, ge=0, description="Offset for pagination"),
    accepted_only: bool = Query(default=False, description="Only return accepted stories"),
):
    """
    List stories from the registry.

    Returns stories sorted by creation time (newest first).
    """
    try:
        from src.registry.story_registry import StoryRegistry

        registry = StoryRegistry()
        records = registry.load_recent_accepted(limit=limit + offset)

        # Apply offset
        records = records[offset:offset + limit]

        # Filter if needed
        if accepted_only:
            records = [r for r in records if r.accepted]

        stories = []
        for record in records:
            research_used = []
            if record.research_used_json:
                try:
                    research_used = json.loads(record.research_used_json)
                except json.JSONDecodeError:
                    pass

            stories.append(StoryListItem(
                story_id=record.id,
                title=record.title,
                template_id=record.template_id,
                template_name=record.template_name,
                created_at=record.created_at,
                accepted=record.accepted,
                decision_reason=record.decision_reason,
                story_signature=record.story_signature,
                research_used=research_used
            ))

        return StoryListResponse(
            stories=stories,
            total=len(stories),
            message=f"Found {len(stories)} stories"
        )

    except Exception as e:
        logger.error(f"[StoryAPI] List error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to list stories: {e}")


@router.get("/{story_id}", response_model=StoryDetailResponse)
async def get_story_detail(story_id: str):
    """
    Get detailed information about a specific story.
    """
    try:
        from src.registry.story_registry import StoryRegistry

        registry = StoryRegistry()

        # Search for the story
        records = registry.load_recent_accepted(limit=1000)
        record = None
        for r in records:
            if r.id == story_id:
                record = r
                break

        if not record:
            raise HTTPException(status_code=404, detail=f"Story not found: {story_id}")

        # Parse JSON fields
        canonical_core = None
        if record.canonical_core_json:
            try:
                canonical_core = json.loads(record.canonical_core_json)
            except json.JSONDecodeError:
                pass

        research_used = []
        if record.research_used_json:
            try:
                research_used = json.loads(record.research_used_json)
            except json.JSONDecodeError:
                pass

        return StoryDetailResponse(
            story_id=record.id,
            title=record.title,
            template_id=record.template_id,
            template_name=record.template_name,
            semantic_summary=record.semantic_summary,
            created_at=record.created_at,
            accepted=record.accepted,
            decision_reason=record.decision_reason,
            story_signature=record.story_signature,
            canonical_core=canonical_core,
            research_used=research_used
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[StoryAPI] Detail error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get story: {e}")
