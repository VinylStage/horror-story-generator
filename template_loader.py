"""
Template skeleton loading and selection module.

Phase 2A: Template skeleton loading and back-to-back prevention.
Phase 3B: Weighted template selection based on registry history.
"""

import json
import logging
import random
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("horror_story_generator")

# Phase 2A: Template skeleton configuration
TEMPLATE_SKELETONS_PATH = Path(__file__).parent / "phase1_foundation" / "03_templates" / "template_skeletons_v1.json"

# Phase 2A: In-memory state for back-to-back prevention (process-scoped only, not persisted)
_last_template_id: Optional[str] = None


# =============================================================================
# Phase 3B-B1: Pre-generation Weighted Template Selection
# =============================================================================
# Soft control for "Systemic Inevitability" cluster before generation.
# Does NOT alter Phase 2C post-generation dedup control.
# =============================================================================

# Cluster definition: antagonist=system AND twist=inevitability
# Templates matching this pattern (from template_skeletons_v1.json):
SYSTEMIC_INEVITABILITY_CLUSTER = frozenset({
    "T-SYS-001",  # Systemic Erosion
    "T-APT-001",  # Apartment Social Surveillance
    "T-INF-001",  # Infrastructure Isolation
    "T-ECO-001",  # Economic Annihilation
})

# Phase 3B configuration
PHASE3B_LOOKBACK_WINDOW = 10  # Last N accepted stories
PHASE3B_WEIGHT_PENALTIES = {
    # occurrence_threshold: weight_multiplier
    4: 0.50,   # ≥4 → -50% weight
    6: 0.20,   # ≥6 → -80% weight
    8: 0.05,   # ≥8 → -95% weight (never 0)
}


def load_template_skeletons() -> List[Dict[str, Any]]:
    """
    Load template skeletons defined in Phase 1.

    Returns:
        List[Dict[str, Any]]: List of 15 template skeletons

    Raises:
        FileNotFoundError: If template file doesn't exist
    """
    if not TEMPLATE_SKELETONS_PATH.exists():
        logger.warning(f"템플릿 스켈레톤 파일 없음: {TEMPLATE_SKELETONS_PATH}")
        return []

    with open(TEMPLATE_SKELETONS_PATH, 'r', encoding='utf-8') as f:
        skeletons = json.load(f)

    logger.debug(f"템플릿 스켈레톤 {len(skeletons)}개 로드 완료")
    return skeletons


def count_cluster_occurrences_in_registry(
    registry: Any,
    lookback: int = PHASE3B_LOOKBACK_WINDOW
) -> int:
    """
    Phase 3B-B1: Count Systemic Inevitability cluster occurrences in recent registry.

    Args:
        registry: StoryRegistry instance (from story_registry.py)
        lookback: Number of recent accepted stories to check

    Returns:
        int: Count of stories using cluster templates
    """
    if registry is None:
        return 0

    try:
        recent = registry.load_recent_accepted(limit=lookback)
    except Exception as e:
        logger.warning(f"[Phase3B][PRE] Registry 조회 실패: {e}")
        return 0

    count = sum(
        1 for r in recent
        if r.template_id in SYSTEMIC_INEVITABILITY_CLUSTER
    )

    return count


def compute_template_weights(
    skeletons: List[Dict[str, Any]],
    cluster_count: int
) -> List[float]:
    """
    Phase 3B-B1: Compute selection weights for templates.

    Applies penalty to Systemic Inevitability cluster based on recent usage.
    Never reduces weight to 0 (soft control, not hard block).

    Args:
        skeletons: List of template dictionaries
        cluster_count: Number of cluster templates in recent registry

    Returns:
        List[float]: Weight for each template (same order as input)
    """
    # Determine penalty multiplier based on count thresholds
    penalty_multiplier = 1.0
    for threshold in sorted(PHASE3B_WEIGHT_PENALTIES.keys()):
        if cluster_count >= threshold:
            penalty_multiplier = PHASE3B_WEIGHT_PENALTIES[threshold]

    weights = []
    for skeleton in skeletons:
        template_id = skeleton.get("template_id", "")
        if template_id in SYSTEMIC_INEVITABILITY_CLUSTER:
            weights.append(penalty_multiplier)
        else:
            weights.append(1.0)

    return weights


def select_random_template(
    exclude_template_ids: Optional[set] = None,
    registry: Any = None
) -> Optional[Dict[str, Any]]:
    """
    Phase 2A + Phase 3B: Select a template skeleton.

    Phase 2A features:
    - No state between process runs (stateless across restarts)
    - Back-to-back prevention within same process

    Phase 3B-B1 features (when registry provided):
    - Systemic Inevitability cluster weight penalty
    - Soft control based on recent story usage

    Args:
        exclude_template_ids: Phase 2C - Optional set of template IDs to exclude
                              (used for forced template change on Attempt 2)
        registry: Phase 3B - Optional StoryRegistry for weighted selection

    Returns:
        Optional[Dict[str, Any]]: Selected template skeleton, or None if no file
    """
    global _last_template_id

    skeletons = load_template_skeletons()
    if not skeletons:
        logger.info("사용 가능한 템플릿 없음 - 기본 프롬프트 사용")
        return None

    # Start with all templates
    candidates = skeletons

    # Back-to-back prevention: exclude last used template if possible
    if _last_template_id and len(candidates) > 1:
        candidates = [s for s in candidates if s.get('template_id') != _last_template_id]

    # Phase 2C: Additional exclusion for forced template change
    if exclude_template_ids and len(candidates) > 1:
        filtered = [s for s in candidates if s.get('template_id') not in exclude_template_ids]
        if filtered:  # Only apply if we still have candidates
            candidates = filtered
            logger.info(f"[Phase2C][CONTROL] 템플릿 강제 제외: {exclude_template_ids}")

    # Phase 3B-B1: Weighted selection based on registry history
    if registry is not None:
        cluster_count = count_cluster_occurrences_in_registry(registry)
        logger.info(f"[Phase3B][PRE] Systemic cluster count (last {PHASE3B_LOOKBACK_WINDOW}): {cluster_count}")

        if cluster_count >= 4:
            # Compute weights for candidates
            weights = compute_template_weights(candidates, cluster_count)

            # Log penalty application
            penalty_pct = int((1 - min(weights)) * 100)
            if penalty_pct > 0:
                logger.info(f"[Phase3B][PRE] Applying weight penalty: -{penalty_pct}%")

            # Use weighted random selection
            selected = random.choices(candidates, weights=weights, k=1)[0]
        else:
            # No penalty needed, use uniform selection
            selected = random.choice(candidates)
    else:
        # No registry, use uniform selection (Phase 2A behavior)
        selected = random.choice(candidates)

    _last_template_id = selected.get('template_id')

    logger.info(f"[Phase3B][PRE] Selected template: {selected.get('template_id')} - {selected.get('template_name')}")
    return selected


def reset_last_template_id() -> None:
    """Reset the last template ID. Useful for testing."""
    global _last_template_id
    _last_template_id = None
    logger.debug("Last template ID reset")
