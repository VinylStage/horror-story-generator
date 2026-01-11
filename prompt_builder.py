"""
Prompt Builder - System and User Prompt Construction

This module handles the construction of prompts for the horror story generator.
Extracted from horror_story_generator.py for modularity.

Phase B+: Supports both Research Context and Story Seed injection.
Both are READ-ONLY inspirational contexts - they guide but never block generation.
"""

import json
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


def _format_research_context(context: Dict[str, Any]) -> str:
    """
    Format research context for system prompt injection.

    Args:
        context: Research context dict with key_concepts and horror_applications

    Returns:
        Formatted string section for system prompt
    """
    if not context:
        return ""

    lines = [
        "",
        "## Research Context (from prior analysis)",
        "",
    ]

    concepts = context.get("key_concepts", [])
    if concepts:
        lines.append("**Relevant concepts to consider:**")
        for concept in concepts:
            lines.append(f"- {concept}")
        lines.append("")

    applications = context.get("horror_applications", [])
    if applications:
        lines.append("**Horror application ideas:**")
        for app in applications:
            lines.append(f"- {app}")
        lines.append("")

    # Add source cards reference
    source_cards = context.get("source_cards", [])
    if source_cards:
        lines.append(f"*Research sources: {', '.join(source_cards)}*")
        lines.append("")

    lines.append("*These are suggestions to inspire your writing. "
                 "You may incorporate, adapt, or disregard as creatively appropriate.*")

    return "\n".join(lines)


def _format_seed_context(context: Dict[str, Any]) -> str:
    """
    Format story seed context for system prompt injection.

    Phase B+: Story Seeds provide thematic inspiration derived from Research Cards.

    Args:
        context: Seed context dict with themes, atmosphere, hooks, cultural elements

    Returns:
        Formatted string section for system prompt
    """
    if not context:
        return ""

    lines = [
        "",
        "## Story Seed (thematic inspiration)",
        "",
    ]

    themes = context.get("key_themes", [])
    if themes:
        lines.append("**Core themes to explore:**")
        for theme in themes:
            lines.append(f"- {theme}")
        lines.append("")

    atmosphere = context.get("atmosphere_tags", [])
    if atmosphere:
        lines.append("**Atmosphere:**")
        lines.append(f"{', '.join(atmosphere)}")
        lines.append("")

    hooks = context.get("suggested_hooks", [])
    if hooks:
        lines.append("**Possible story hooks:**")
        for hook in hooks:
            lines.append(f"- {hook}")
        lines.append("")

    cultural = context.get("cultural_elements", [])
    if cultural:
        lines.append("**Cultural elements:**")
        for elem in cultural:
            lines.append(f"- {elem}")
        lines.append("")

    # Source reference
    seed_id = context.get("seed_id")
    if seed_id:
        lines.append(f"*Seed source: {seed_id}*")
        lines.append("")

    lines.append("*These are seeds to inspire your writing. "
                 "Develop them naturally into your horror narrative.*")

    return "\n".join(lines)


def build_system_prompt(
    template: Optional[Dict[str, Any]] = None,
    skeleton: Optional[Dict[str, Any]] = None,
    research_context: Optional[Dict[str, Any]] = None,
    seed_context: Optional[Dict[str, Any]] = None
) -> str:
    """
    시스템 프롬프트를 생성합니다.

    템플릿이 제공되지 않으면 기본 심리 공포 프롬프트를 사용합니다.
    템플릿이 제공되면 기존 로직을 따릅니다 (하위 호환성).
    Phase 2A: skeleton이 제공되면 스토리 구조가 추가됩니다.
    Phase A: research_context가 제공되면 연구 컨텍스트가 추가됩니다.
    Phase B+: seed_context가 제공되면 스토리 시드 컨텍스트가 추가됩니다.

    Args:
        template (Optional[Dict[str, Any]]): 프롬프트 템플릿 데이터 (legacy format)
        skeleton (Optional[Dict[str, Any]]): Phase 2A 템플릿 스켈레톤
        research_context (Optional[Dict[str, Any]]): Research context for injection
        seed_context (Optional[Dict[str, Any]]): Story seed context for injection

    Returns:
        str: 완성된 시스템 프롬프트 문자열

    Example:
        >>> system_prompt = build_system_prompt()  # 기본 프롬프트 사용
        >>> system_prompt = build_system_prompt(template=old_template)  # 레거시 템플릿 기반
        >>> system_prompt = build_system_prompt(skeleton=selected_skeleton)  # Phase 2A 스켈레톤 기반
        >>> system_prompt = build_system_prompt(skeleton=skel, research_context=ctx)  # with research
        >>> system_prompt = build_system_prompt(skeleton=skel, seed_context=seed)  # with seed
    """
    logger.debug("시스템 프롬프트 생성 시작")

    # 템플릿이 없으면 새로운 기본 프롬프트 사용
    if template is None:
        system_prompt = """You are a specialist in quiet psychological horror rooted in ordinary daily life.
Your stories make readers feel that the same thing could happen in their own mundane reality.

## Core Principles

### 1. Everyday Psychological Horror
- Setting: Ordinary spaces (apartment, office, subway, convenience store, etc.)
- Source of horror: NOT supernatural beings, but system malfunction, abnormal behavior of others, cracks in reality
- Protagonist: An ordinary person with no special abilities or background

### 2. Horror Intensity: LEVEL 4 (Moderate-High)
- Anxiety and fear escalate gradually
- Begin from the moment the reader senses "something is going wrong"
- Minimize explicit violence; maximize psychological pressure
- Sustain tension until the very end

### 3. Ending Rules (CRITICAL)
**Mandatory ending guard constraints:**
- ❌ FORBIDDEN: "But I survived," "It will be okay now," "It's all over"
- ❌ FORBIDDEN: Ending with sadness, resignation, giving up, or acceptance
- ✅ REQUIRED: Imply the threat still exists
- ✅ REQUIRED: Suggest the protagonist may face the same situation again
- ✅ REQUIRED: Leave the reader feeling "it's not over yet"

**Ending examples (MUST follow this direction):**
- "And today, too, I heard that door opening again."
- "The phone rang again. This time, from my own number."
- "On my commute, I saw that person again from yesterday."
- "Since that day, I receive that message every single day."

### 4. Narrative Constraints
- **First-person POV is MANDATORY**
- **NO over-explanation**: Do not directly explain the cause of horror
  - ❌ Wrong: "It was an entity from a dimensional rift"
  - ✅ Correct: "I don't know what it is, but it's getting closer"
- Use short, intuitive sentences
- Let readers infer for themselves

### 5. Structure
- **Opening**: Ordinary day, subtle wrongness (10%)
- **Development**: Accumulating anomalies, protagonist's rising anxiety (40%)
- **Climax**: Peak of horror, protagonist's failed response or helplessness (30%)
- **Ending**: Unresolved threat, cyclical implication (20%)

### 6. Target Length
- 3,000–4,000 characters (Korean text)
- Short story format

## Pre-Ending Checklist
Before writing the final sentence, verify:
1. Does it feel like "the threat is resolved"? → If YES, rewrite
2. Does it feel like "sad but over"? → If YES, rewrite
3. Does it leave the reader in an anxious state? → If NO, rewrite
4. Does it suggest the same thing will repeat or continue? → If NO, rewrite

Leave readers with lingering unease that "it's not over yet" even after they close the book.

## OUTPUT LANGUAGE
**Write the entire story in Korean.**
Use natural, modern Korean prose suitable for literary horror fiction.
"""
        # Phase 2A: 스켈레톤 템플릿이 있으면 구조 추가
        if skeleton:
            canonical = skeleton.get("canonical_core", {})
            story_skel = skeleton.get("story_skeleton", {})
            template_name = skeleton.get("template_name", "Unknown")

            system_prompt += f"""

## THIS SESSION'S STORY DIRECTION (Template: {template_name})

### Thematic Framework
- Setting Type: {canonical.get('setting', 'unspecified')}
- Primary Fear: {canonical.get('primary_fear', 'unspecified')}
- Antagonist Type: {canonical.get('antagonist', 'unspecified')}
- Horror Mechanism: {canonical.get('mechanism', 'unspecified')}
- Twist Pattern: {canonical.get('twist', 'unspecified')}

### Narrative Arc
- **Act 1 (Setup):** {story_skel.get('act_1', 'Establish normalcy and subtle wrongness')}
- **Act 2 (Escalation):** {story_skel.get('act_2', 'Build tension through accumulating anomalies')}
- **Act 3 (Resolution):** {story_skel.get('act_3', 'Deliver unresolved horror with cyclical implication')}

Use this framework to guide the story's direction while maintaining creative freedom in specific details.
"""
            logger.debug(f"스켈레톤 템플릿 적용: {template_name}")

        # Phase A: Research context injection
        if research_context:
            system_prompt += _format_research_context(research_context)
            logger.debug(f"[ResearchInject] Context injected: {len(research_context.get('key_concepts', []))} concepts")

        # Phase B+: Story seed context injection
        if seed_context:
            system_prompt += _format_seed_context(seed_context)
            logger.debug(f"[SeedInject] Context injected: {len(seed_context.get('key_themes', []))} themes")

        logger.debug("기본 심리 공포 프롬프트 사용")
        return system_prompt

    # 기존 템플릿 기반 로직 (하위 호환성)
    logger.debug("템플릿 기반 프롬프트 생성")

    system_prompt = """You are a master horror fiction writer. You specialize in creating stories that unsettle readers and evoke deep psychological fear.

Follow the guidelines below to craft your horror story:

"""

    # 장르 및 분위기 설정
    config = template.get("story_config", {})
    system_prompt += f"""
## Base Configuration
- Genre: {config.get('genre', 'horror')}
- Atmosphere: {config.get('atmosphere', 'dark')}
- Length: {config.get('length', 'medium')}
- Target audience: {config.get('target_audience', 'adult')}
"""

    # 스토리 요소
    elements = template.get("story_elements", {})
    if elements:
        system_prompt += "\n## Story Elements\n"
        system_prompt += f"Story structure: {json.dumps(elements, ensure_ascii=False, indent=2)}\n"

    # 글쓰기 스타일
    style = template.get("writing_style", {})
    if style:
        system_prompt += "\n## Writing Style\n"
        system_prompt += f"- Perspective: {style.get('narrative_perspective', '1인칭')}\n"
        system_prompt += f"- Tense: {style.get('tense', '과거형')}\n"
        system_prompt += f"- Tone: {', '.join(style.get('tone', []))}\n"

        lang_style = style.get("language_style", {})
        if lang_style:
            system_prompt += f"- Vocabulary: {lang_style.get('vocabulary', '풍부하고 감각적')}\n"
            system_prompt += f"- Korean style: {lang_style.get('korean_style', '현대 한국어')}\n"

    # 추가 요구사항
    requirements = template.get("additional_requirements", {})
    if requirements:
        system_prompt += "\n## Additional Requirements\n"
        system_prompt += f"- Target word count: {requirements.get('word_count', 3000)} characters\n"
        system_prompt += f"- Structure: {requirements.get('chapter_structure', '단편')}\n"

        if "avoid" in requirements:
            system_prompt += f"- Elements to avoid: {', '.join(requirements['avoid'])}\n"

        if "emphasize" in requirements:
            system_prompt += f"- Elements to emphasize: {', '.join(requirements['emphasize'])}\n"

    system_prompt += """

Keep readers on edge until the very last sentence.
Leave a haunting aftertaste that lingers long after the story ends.

## OUTPUT LANGUAGE
**Write the entire story in Korean.**
Use natural, modern Korean prose suitable for literary horror fiction.
"""

    logger.debug("시스템 프롬프트 생성 완료")
    return system_prompt


def build_user_prompt(custom_request: Optional[str] = None, template: Optional[Dict[str, Any]] = None) -> str:
    """
    사용자 요청을 기반으로 user 프롬프트를 생성합니다.

    커스텀 요청이 있으면 그대로 사용하고, 없으면 템플릿 기반으로
    기본 요청 프롬프트를 생성합니다.

    Args:
        custom_request (Optional[str]): 사용자의 커스텀 요청사항. None이면 기본 프롬프트 사용
        template (Optional[Dict[str, Any]]): 프롬프트 템플릿 (추가 컨텍스트용)

    Returns:
        str: 완성된 user 프롬프트 문자열

    Example:
        >>> user_prompt = build_user_prompt("1980년대 시골 마을 배경의 귀신 이야기")
    """
    if custom_request:
        logger.debug(f"커스텀 요청 프롬프트 사용: {custom_request[:50]}...")
        return custom_request

    # 기본 요청
    user_prompt = "Following the guidelines above, write an original and unsettling horror story."

    if template:
        elements = template.get("story_elements", {})
        setting = elements.get("setting", {})

        if setting:
            user_prompt += f"\n\nSetting: {setting.get('location', 'TBD')} - {setting.get('time_period', 'present day')}"

        plot = elements.get("plot_structure", {})
        if plot and "act_1" in plot:
            user_prompt += f"\nOpening hook: {plot['act_1'].get('hook', '')}"

    logger.debug("기본 프롬프트 생성 완료")
    return user_prompt
