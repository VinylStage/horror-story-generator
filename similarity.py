"""
Similarity observation and dedup control module.

Phase 2B: In-memory generation memory for similarity observation.
Phase 2C: HIGH-only dedup control functions.
"""

import logging
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger("horror_story_generator")


# =============================================================================
# Phase 2B: Generation Memory (In-Process Only, Observation Only)
# =============================================================================
# This memory exists ONLY for similarity observation.
# It does NOT prevent, block, or alter generation in any way.
# It resets on process restart. No disk persistence.
# =============================================================================

@dataclass
class GenerationRecord:
    """Phase 2B: Single generation record for similarity observation."""
    story_id: str
    template_id: Optional[str]
    title: str
    semantic_summary: str  # 1-3 sentence summary for comparison
    canonical_keys: Dict[str, str]  # setting, primary_fear, etc.
    generated_at: str


# Phase 2B: In-memory generation registry (process-scoped only, not persisted)
_generation_memory: List[GenerationRecord] = []


def compute_text_similarity(text1: str, text2: str) -> float:
    """
    Phase 2B: Compute simple similarity between two texts.

    Uses word set-based Jaccard similarity without external libraries.
    This is for observation only, not used for generation decisions.

    Args:
        text1: First text
        text2: Second text

    Returns:
        float: Similarity score between 0.0 and 1.0
    """
    # Simple word-based Jaccard similarity (no external deps)
    words1 = set(re.findall(r'\w+', text1.lower()))
    words2 = set(re.findall(r'\w+', text2.lower()))

    if not words1 or not words2:
        return 0.0

    intersection = len(words1 & words2)
    union = len(words1 | words2)

    return intersection / union if union > 0 else 0.0


def observe_similarity(
    current_summary: str,
    current_title: str,
    canonical_keys: Dict[str, str]
) -> Optional[Dict[str, Any]]:
    """
    Phase 2B: Observe similarity between current story and existing stories.

    ⚠️ This function ONLY observes.
    ⚠️ It does NOT prevent or alter generation.
    ⚠️ Results are only logged.

    Args:
        current_summary: Semantic summary of current story
        current_title: Current story title
        canonical_keys: Canonical keys of current story (setting, primary_fear, etc.)

    Returns:
        Optional[Dict]: Similarity observation result (most similar story info)
    """
    global _generation_memory

    if not _generation_memory:
        logger.info("[Phase2B][OBSERVE] 첫 번째 생성 - 비교 대상 없음")
        return None

    logger.info(f"[Phase2B][OBSERVE] 유사도 관측 시작 (기존 {len(_generation_memory)}개 스토리와 비교)")

    highest_similarity = 0.0
    most_similar_record: Optional[GenerationRecord] = None
    canonical_match_count = 0

    for record in _generation_memory:
        # Text similarity
        sim = compute_text_similarity(current_summary, record.semantic_summary)

        # Canonical key matching (bonus signal)
        key_matches = sum(
            1 for k, v in canonical_keys.items()
            if record.canonical_keys.get(k) == v
        )

        if sim > highest_similarity:
            highest_similarity = sim
            most_similar_record = record
            canonical_match_count = key_matches

    # Determine signal level (for observation only)
    if highest_similarity >= 0.5:
        signal = "HIGH"
    elif highest_similarity >= 0.3:
        signal = "MEDIUM"
    else:
        signal = "LOW"

    # Log observation (THIS IS THE KEY OUTPUT - observation only)
    if most_similar_record:
        logger.info(f"[Phase2B][OBSERVE] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        logger.info(f"[Phase2B][OBSERVE] 유사도 관측 결과:")
        logger.info(f"[Phase2B][OBSERVE]   현재: \"{current_title}\"")
        logger.info(f"[Phase2B][OBSERVE]   가장 유사: \"{most_similar_record.title}\" (ID: {most_similar_record.story_id})")
        logger.info(f"[Phase2B][OBSERVE]   텍스트 유사도: {highest_similarity:.2%}")
        logger.info(f"[Phase2B][OBSERVE]   정규화 키 일치: {canonical_match_count}/5")
        logger.info(f"[Phase2B][OBSERVE]   신호 수준: {signal}")
        logger.info(f"[Phase2B][OBSERVE] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        logger.info(f"[Phase2B][OBSERVE] ⚠️ 이 관측은 생성에 영향을 주지 않습니다")

        return {
            "closest_story_id": most_similar_record.story_id,
            "closest_title": most_similar_record.title,
            "text_similarity": round(highest_similarity, 3),
            "canonical_matches": canonical_match_count,
            "signal": signal
        }

    return None


def add_to_generation_memory(
    story_id: str,
    template_id: Optional[str],
    title: str,
    semantic_summary: str,
    canonical_keys: Dict[str, str]
) -> None:
    """
    Phase 2B: Add generated story to memory.

    This memory is deleted on process termination.
    Not saved to disk.

    Args:
        story_id: Unique story ID
        template_id: Template ID used
        title: Story title
        semantic_summary: Semantic summary
        canonical_keys: Canonical keys
    """
    global _generation_memory

    record = GenerationRecord(
        story_id=story_id,
        template_id=template_id,
        title=title,
        semantic_summary=semantic_summary,
        canonical_keys=canonical_keys,
        generated_at=datetime.now().isoformat()
    )

    _generation_memory.append(record)
    logger.info(f"[Phase2B][OBSERVE] 생성 메모리에 추가: {story_id} (총 {len(_generation_memory)}개)")


# =============================================================================
# Phase 2C: Dedup Control Functions (HIGH-only)
# =============================================================================

def load_past_stories_into_memory(records: List[Any]) -> int:
    """
    Phase 2C: Load past stories into in-memory generation memory.

    Converts records loaded from SQLite registry to Phase 2B memory structure.
    This connects Phase 2B (in-memory) and Phase 2C (persistent).

    Args:
        records: StoryRegistryRecord list (from story_registry.load_recent_accepted)

    Returns:
        int: Number of records loaded
    """
    global _generation_memory

    loaded = 0
    for record in records:
        # StoryRegistryRecord → GenerationRecord conversion
        gen_record = GenerationRecord(
            story_id=record.id,
            template_id=record.template_id,
            title=record.title or "Unknown",
            semantic_summary=record.semantic_summary,
            canonical_keys={},  # canonical_keys not stored in DB (outside Phase 2C scope)
            generated_at=record.created_at
        )
        _generation_memory.append(gen_record)
        loaded += 1

    logger.info(f"[Phase2C][CONTROL] 과거 스토리 {loaded}개를 in-memory에 로드")
    return loaded


def get_similarity_signal(observation: Optional[Dict[str, Any]]) -> str:
    """
    Phase 2C: Extract signal level from similarity observation result.

    Args:
        observation: Return value from observe_similarity()

    Returns:
        str: "LOW", "MEDIUM", or "HIGH" ("LOW" if no observation)
    """
    if observation is None:
        return "LOW"
    return observation.get("signal", "LOW")


def should_accept_story(signal: str) -> bool:
    """
    Phase 2C: Determine whether to accept the story.

    Policy: Only reject HIGH, accept LOW/MEDIUM

    Args:
        signal: Similarity signal ("LOW", "MEDIUM", "HIGH")

    Returns:
        bool: True if should accept, False if should reject/retry
    """
    # MEDIUM is NOT blocked - only HIGH triggers retry
    return signal != "HIGH"


def get_generation_memory_count() -> int:
    """Get the current count of items in generation memory."""
    global _generation_memory
    return len(_generation_memory)


def clear_generation_memory() -> None:
    """Clear the generation memory. Useful for testing."""
    global _generation_memory
    _generation_memory = []
    logger.info("[Phase2B][OBSERVE] 생성 메모리 초기화 완료")
