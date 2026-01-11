"""
호러 소설 생성기 - Claude API를 사용한 함수형 구현

이 모듈은 Claude API를 활용하여 한국어 호러 소설을 자동으로 생성합니다.
Astro + GraphQL 블로그에 최적화된 마크다운 포맷으로 출력합니다.

향후 API 서버로 확장 가능하도록 설계되었습니다.
"""

import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from dotenv import load_dotenv

# Extracted modules
from src.infra.logging_config import setup_logging, DailyRotatingFileHandler
from api_client import call_claude_api, generate_semantic_summary
from similarity import (
    GenerationRecord, observe_similarity, add_to_generation_memory,
    load_past_stories_into_memory, get_similarity_signal, should_accept_story
)
from template_loader import (
    load_template_skeletons, select_random_template,
    SYSTEMIC_INEVITABILITY_CLUSTER, PHASE3B_LOOKBACK_WINDOW
)

# Prompt builder module (extracted for modularity)
from prompt_builder import build_system_prompt, build_user_prompt

# Phase A: Research integration module
try:
    from research_integration import select_research_for_template, get_research_context_for_prompt
    RESEARCH_INTEGRATION_AVAILABLE = True
except ImportError:
    RESEARCH_INTEGRATION_AVAILABLE = False


# 초기 로거 생성 (환경 변수 로드 전 기본값)
logger = setup_logging()


def load_environment() -> Dict[str, Union[str, int, float]]:
    """
    환경 변수를 로드하고 필요한 설정을 반환합니다.

    .env 파일에서 API 키, 모델 설정, 출력 디렉토리, 로깅 레벨 등을 로드합니다.
    필수 환경 변수가 없을 경우 ValueError를 발생시킵니다.

    Returns:
        Dict[str, Union[str, int, float]]: API 키 및 모델 설정 정보
            - api_key (str): Anthropic API 키
            - model (str): Claude 모델 이름
            - max_tokens (int): 최대 토큰 수
            - temperature (float): 생성 온도 (0.0~1.0)
            - output_dir (str): 출력 디렉토리 경로
            - log_level (str): 로깅 레벨

    Raises:
        ValueError: ANTHROPIC_API_KEY가 설정되지 않은 경우

    Example:
        >>> config = load_environment()
        >>> print(config['model'])
        'claude-sonnet-4-5-20250929'
    """
    global logger
    load_dotenv()

    # 로깅 레벨 재설정
    log_level = os.getenv("LOG_LEVEL", "INFO")
    logger = setup_logging(log_level)

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        logger.error("ANTHROPIC_API_KEY가 .env 파일에 설정되지 않았습니다.")
        raise ValueError("ANTHROPIC_API_KEY가 .env 파일에 설정되지 않았습니다.")

    config = {
        "api_key": api_key,
        "model": os.getenv("CLAUDE_MODEL", "claude-sonnet-4-5-20250929"),
        "max_tokens": int(os.getenv("MAX_TOKENS", "8192")),
        "temperature": float(os.getenv("TEMPERATURE", "0.8")),
        "output_dir": os.getenv("OUTPUT_DIR", "./generated_stories"),
        "log_level": log_level
    }

    logger.info(f"환경 변수 로드 완료 - 모델: {config['model']}")
    return config


def load_prompt_template(template_path: str = "horror_story_prompt_template.json") -> Dict[str, Any]:
    """
    JSON 형식의 프롬프트 템플릿을 로드합니다.

    템플릿 파일에는 장르, 분위기, 캐릭터, 플롯 구조 등
    호러 소설 생성에 필요한 모든 설정이 포함됩니다.

    Args:
        template_path (str): 템플릿 파일 경로. 기본값은 "horror_story_prompt_template.json"

    Returns:
        Dict[str, Any]: 프롬프트 템플릿 데이터
            - story_config: 기본 설정 (장르, 분위기 등)
            - story_elements: 스토리 요소 (설정, 캐릭터, 플롯)
            - writing_style: 글쓰기 스타일
            - additional_requirements: 추가 요구사항

    Raises:
        FileNotFoundError: 템플릿 파일이 존재하지 않는 경우

    Example:
        >>> template = load_prompt_template()
        >>> genre = template['story_config']['genre']
    """
    if not os.path.exists(template_path):
        logger.error(f"프롬프트 템플릿 파일을 찾을 수 없습니다: {template_path}")
        raise FileNotFoundError(f"프롬프트 템플릿 파일을 찾을 수 없습니다: {template_path}")

    with open(template_path, 'r', encoding='utf-8') as f:
        template = json.load(f)

    logger.info(f"프롬프트 템플릿 로드 완료: {template_path}")
    return template


def extract_title_from_story(story_text: str) -> str:
    """
    생성된 소설에서 제목을 추출합니다.

    마크다운 형식의 # 제목을 찾아 반환합니다.
    제목을 찾을 수 없으면 기본 제목을 반환합니다.

    Args:
        story_text (str): 생성된 소설 전체 텍스트

    Returns:
        str: 추출된 제목 또는 기본 제목

    Example:
        >>> title = extract_title_from_story("# 녹색 복도\\n\\n본문...")
        >>> print(title)
        '녹색 복도'
    """
    # 마크다운 제목 패턴 찾기 (# 제목)
    title_match = re.search(r'^#\s+(.+)$', story_text, re.MULTILINE)
    if title_match:
        title = title_match.group(1).strip()
        logger.debug(f"제목 추출 성공: {title}")
        return title

    logger.warning("제목을 찾을 수 없어 기본 제목 사용")
    return "무제"


def extract_tags_from_story(story_text: str, template: Dict[str, Any]) -> List[str]:
    """
    소설과 템플릿에서 태그를 추출합니다.

    소설 본문의 태그 섹션과 템플릿의 설정을 분석하여
    한영 혼용 태그 리스트를 생성합니다.

    Args:
        story_text (str): 생성된 소설 전체 텍스트
        template (Dict[str, Any]): 프롬프트 템플릿

    Returns:
        List[str]: 추출된 태그 리스트

    Example:
        >>> tags = extract_tags_from_story(story_text, template)
        >>> print(tags)
        ['호러', 'horror', '심리스릴러', 'psychological']
    """
    tags = ["호러", "horror"]

    # 템플릿에서 장르 태그 추가
    config = template.get("story_config", {})
    genre = config.get("genre", "")
    if genre and genre not in tags:
        tags.append(genre)

    # 템플릿에서 공포 타입 태그 추가
    elements = template.get("story_elements", {})
    horror_techniques = elements.get("horror_techniques", {})
    fear_types = horror_techniques.get("primary_fear_type", [])
    if isinstance(fear_types, list):
        tags.extend(fear_types[:2])  # 최대 2개만 추가

    # 소설 본문에서 태그 섹션 찾기 (## 태그)
    tag_section_match = re.search(r'##\s*태그\s*\n([\s\S]+?)(?=\n##|\Z)', story_text, re.MULTILINE)
    if tag_section_match:
        tag_content = tag_section_match.group(1)
        # - #태그명 또는 - 태그명 형식 추출
        found_tags = re.findall(r'-\s*#?(\w+)', tag_content)
        tags.extend(found_tags[:5])  # 최대 5개만 추가

    # 중복 제거 및 정리
    unique_tags = []
    seen = set()
    for tag in tags:
        tag_clean = tag.strip().lower()
        if tag_clean not in seen:
            seen.add(tag_clean)
            unique_tags.append(tag.strip())

    logger.debug(f"태그 추출 완료: {unique_tags}")
    return unique_tags[:10]  # 최대 10개


def generate_description(story_text: str) -> str:
    """
    소설의 첫 부분에서 간단한 설명을 생성합니다.

    첫 문단 또는 첫 200자를 추출하여 설명으로 사용합니다.

    Args:
        story_text (str): 생성된 소설 전체 텍스트

    Returns:
        str: 생성된 설명 (최대 200자)

    Example:
        >>> desc = generate_description(story_text)
    """
    # 첫 번째 # 제목 이후의 텍스트 추출
    content_start = re.search(r'^#\s+.+$', story_text, re.MULTILINE)
    if content_start:
        content = story_text[content_start.end():].strip()
    else:
        content = story_text.strip()

    # 첫 문단 또는 200자 추출
    first_para = content.split('\n\n')[0] if content else ""
    # ## 제목 제거
    first_para = re.sub(r'^##\s+.+$', '', first_para, flags=re.MULTILINE).strip()

    description = first_para[:200].strip()
    if len(first_para) > 200:
        description += "..."

    logger.debug(f"설명 생성 완료: {description[:50]}...")
    return description


def save_story(
    story_text: str,
    output_dir: str,
    metadata: Optional[Dict[str, Any]] = None,
    template: Optional[Dict[str, Any]] = None
) -> str:
    """
    생성된 소설을 Astro + GraphQL 블로그용 마크다운 파일로 저장합니다.

    YAML frontmatter를 포함한 마크다운 파일을 생성하고,
    별도로 메타데이터 JSON 파일도 저장합니다.

    Args:
        story_text (str): 생성된 소설 내용
        output_dir (str): 출력 디렉토리 경로
        metadata (Optional[Dict[str, Any]]): 저장할 메타데이터
        template (Optional[Dict[str, Any]]): 프롬프트 템플릿 (태그 추출용)

    Returns:
        str: 저장된 마크다운 파일 경로

    Example:
        >>> file_path = save_story(story_text, "./output", metadata, template)
        >>> print(file_path)
        './output/horror_story_20260102_150000.md'
    """
    logger.info("파일 저장 시작...")

    # 출력 디렉토리 생성
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    # 타임스탬프 기반 파일명 생성
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    story_filename = f"horror_story_{timestamp}.md"
    story_path = os.path.join(output_dir, story_filename)

    # 제목, 태그, 설명 추출
    title = extract_title_from_story(story_text)
    tags = extract_tags_from_story(story_text, template) if template else ["호러", "horror"]
    description = generate_description(story_text)

    # YAML frontmatter 생성
    date_str = datetime.now().strftime("%Y-%m-%d")
    frontmatter = f"""---
title: "{title}"
date: {date_str}
description: "{description}"
tags: {json.dumps(tags, ensure_ascii=False)}
genre: "호러"
wordCount: {len(story_text)}
"""

    if metadata:
        frontmatter += f"""model: "{metadata.get('model', 'unknown')}"
temperature: {metadata.get('config', {}).get('temperature', 0.8)}
"""

    frontmatter += """draft: false
---

"""

    # 마크다운 파일 저장
    with open(story_path, 'w', encoding='utf-8') as f:
        f.write(frontmatter)
        f.write(story_text)

    logger.info(f"마크다운 파일 저장 완료: {story_path}")

    # 메타데이터 JSON 파일 저장
    if metadata:
        metadata_filename = f"horror_story_{timestamp}_metadata.json"
        metadata_path = os.path.join(output_dir, metadata_filename)

        # 메타데이터에 추출된 정보 추가
        metadata["title"] = title
        metadata["tags"] = tags
        metadata["description"] = description

        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

        logger.info(f"메타데이터 파일 저장 완료: {metadata_path}")

    return story_path


def generate_horror_story(
    template_path: Optional[str] = None,
    custom_request: Optional[str] = None,
    save_output: bool = True
) -> Dict[str, Any]:
    """
    호러 소설 생성의 전체 파이프라인을 실행합니다.

    환경 설정 로드부터 API 호출, 파일 저장까지 전체 프로세스를 관리합니다.
    각 단계의 진행 상황을 로그로 기록합니다.

    Args:
        template_path (Optional[str]): 프롬프트 템플릿 파일 경로. None이면 기본 심리 공포 프롬프트 사용
        custom_request (Optional[str]): 사용자 커스텀 요청. None이면 기본 프롬프트 사용
        save_output (bool): 결과를 파일로 저장할지 여부. 기본값 True

    Returns:
        Dict[str, Any]: 생성 결과 및 메타데이터
            - story (str): 생성된 소설 텍스트
            - metadata (Dict): 생성 메타데이터
            - file_path (str): 저장된 파일 경로 (save_output=True인 경우)

    Raises:
        ValueError: 환경 변수 설정 오류
        FileNotFoundError: 템플릿 파일 없음 (template_path 지정 시)
        Exception: API 호출 또는 파일 저장 실패

    Example:
        >>> result = generate_horror_story()  # 기본 심리 공포 프롬프트 사용
        >>> print(result['story'][:100])
        >>> print(result['file_path'])

        >>> result = generate_horror_story(
        ...     custom_request="1980년대 시골 마을 배경의 귀신 이야기",
        ...     save_output=True
        ... )
    """
    logger.info("=" * 80)
    logger.info("호러 소설 생성기 시작")
    logger.info("=" * 80)

    # 1. 환경 변수 로드
    config = load_environment()
    logger.info(f"설정 - Max Tokens: {config['max_tokens']}, Temperature: {config['temperature']}")

    # 2. 프롬프트 템플릿 로드 (optional)
    template = None
    skeleton = None  # Phase 2A: template skeleton

    if template_path:
        logger.info(f"템플릿 파일 로드: {template_path}")
        template = load_prompt_template(template_path)
    else:
        # Phase 2A: 템플릿 스켈레톤 무작위 선택
        skeleton = select_random_template()
        if skeleton:
            logger.info(f"Phase 2A 템플릿 사용: {skeleton.get('template_id')} - {skeleton.get('template_name')}")
        else:
            logger.info("기본 심리 공포 프롬프트 사용 (템플릿 없음)")

    # Phase A: Research context selection (if skeleton available)
    research_context = None
    if skeleton and RESEARCH_INTEGRATION_AVAILABLE:
        try:
            research_selection = select_research_for_template(skeleton)
            if research_selection.has_matches:
                research_context = get_research_context_for_prompt(research_selection)
                logger.info(f"[ResearchInject] {research_selection.reason}")
            else:
                logger.info("[ResearchInject] No matching research cards")
        except Exception as e:
            logger.warning(f"[ResearchInject] Research selection failed: {e}")

    # 3. 프롬프트 빌드
    logger.info("프롬프트 생성 중...")
    system_prompt = build_system_prompt(template, skeleton=skeleton, research_context=research_context)
    user_prompt = build_user_prompt(custom_request, template)
    logger.info("프롬프트 생성 완료")

    # 4. API 호출
    api_result = call_claude_api(system_prompt, user_prompt, config)
    story_text = api_result["story_text"]
    usage = api_result["usage"]

    # 5. 결과 구성
    # Phase 2A: Include skeleton template info in metadata
    skeleton_info = None
    if skeleton:
        skeleton_info = {
            "template_id": skeleton.get("template_id"),
            "template_name": skeleton.get("template_name"),
            "canonical_core": skeleton.get("canonical_core")
        }

    result = {
        "story": story_text,
        "metadata": {
            "generated_at": datetime.now().isoformat(),
            "model": config["model"],
            "template_used": template_path,
            "skeleton_template": skeleton_info,  # Phase 2A
            "custom_request": custom_request,
            "config": {
                "max_tokens": config["max_tokens"],
                "temperature": config["temperature"]
            },
            "word_count": len(story_text),
            "usage": usage
        }
    }

    # ==========================================================================
    # Phase 2B: Generation Memory & Similarity Observation (AFTER generation)
    # ==========================================================================
    # This section OBSERVES ONLY - it does NOT prevent or alter generation
    # Memory resets on process restart - no disk persistence
    # ==========================================================================

    # Extract title for observation
    title = extract_title_from_story(story_text)

    # Generate story ID (timestamp-based, consistent with file naming)
    story_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Extract canonical keys from skeleton (if available)
    canonical_keys = {}
    if skeleton and skeleton.get("canonical_core"):
        canonical_keys = skeleton.get("canonical_core", {})

    # Generate semantic summary (AFTER generation, for observation only)
    semantic_summary = generate_semantic_summary(story_text, title, config)

    # Observe similarity against previous generations (LOGGING ONLY)
    similarity_observation = observe_similarity(
        current_summary=semantic_summary,
        current_title=title,
        canonical_keys=canonical_keys
    )

    # Add to generation memory (in-process only, resets on restart)
    add_to_generation_memory(
        story_id=story_id,
        template_id=skeleton.get("template_id") if skeleton else None,
        title=title,
        semantic_summary=semantic_summary,
        canonical_keys=canonical_keys
    )

    # Optionally include observation in metadata (non-intrusive)
    if similarity_observation:
        result["metadata"]["similarity_observation"] = similarity_observation

    # ==========================================================================
    # End Phase 2B
    # ==========================================================================

    # 6. 파일 저장
    if save_output:
        file_path = save_story(
            story_text,
            config["output_dir"],
            result["metadata"],
            template
        )
        result["file_path"] = file_path
        logger.info(f"저장 완료: {file_path}")

    logger.info("=" * 80)
    logger.info("호러 소설 생성 완료")
    logger.info("=" * 80)

    return result


# =============================================================================
# Phase 2C: Controlled Generation with HIGH-only Dedup
# =============================================================================

def generate_with_dedup_control(
    registry: Any,  # StoryRegistry instance
    max_attempts: int = 3,
    save_output: bool = True
) -> Optional[Dict[str, Any]]:
    """
    Phase 2C: HIGH-only 중복 제어가 적용된 스토리 생성.

    정책:
    - LOW/MEDIUM 신호: 즉시 수락
    - HIGH 신호: 최대 2회 재생성 시도
      - Attempt 1: 일반 재생성 (같은 템플릿 선택 규칙)
      - Attempt 2: 강제 템플릿 변경 후 재생성
      - 모두 실패 시: SKIP (파일 저장 안함, registry에 기록)

    Args:
        registry: StoryRegistry 인스턴스 (persistent storage)
        max_attempts: 최대 시도 횟수 (기본 3: 초기 + 2회 재생성)
        save_output: 파일 저장 여부

    Returns:
        Optional[Dict]: 수락된 스토리 결과, SKIP 시 None
    """
    logger.info("[Phase2C][CONTROL] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    logger.info("[Phase2C][CONTROL] 중복 제어 생성 시작")
    logger.info("[Phase2C][CONTROL] 정책: HIGH만 거부, LOW/MEDIUM 수락")
    logger.info("[Phase2C][CONTROL] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    config = load_environment()
    used_template_ids: set = set()

    for attempt in range(max_attempts):
        logger.info(f"[Phase2C][CONTROL] Attempt {attempt}/{max_attempts - 1}")

        # Template selection (Phase 3B: pass registry for weighted selection)
        if attempt == 0:
            # Normal selection with Phase 3B weighting
            skeleton = select_random_template(registry=registry)
        elif attempt == 1:
            # Still normal selection (same rules)
            skeleton = select_random_template(registry=registry)
        else:
            # Attempt 2: Forced template change
            skeleton = select_random_template(exclude_template_ids=used_template_ids, registry=registry)

        template_id = skeleton.get("template_id") if skeleton else None
        template_name = skeleton.get("template_name") if skeleton else None
        if template_id:
            used_template_ids.add(template_id)

        logger.info(f"[Phase2C][CONTROL]   템플릿: {template_id} - {template_name}")

        # Phase A: Research context selection
        research_context = None
        if skeleton and RESEARCH_INTEGRATION_AVAILABLE:
            try:
                research_selection = select_research_for_template(skeleton)
                if research_selection.has_matches:
                    research_context = get_research_context_for_prompt(research_selection)
                    logger.info(f"[ResearchInject] {research_selection.reason}")
                else:
                    logger.info("[ResearchInject] No matching research cards")
            except Exception as e:
                logger.warning(f"[ResearchInject] Research selection failed: {e}")

        # Build prompts
        system_prompt = build_system_prompt(template=None, skeleton=skeleton, research_context=research_context)
        user_prompt = build_user_prompt(custom_request=None, template=None)

        # Call API
        api_result = call_claude_api(system_prompt, user_prompt, config)
        story_text = api_result["story_text"]
        usage = api_result["usage"]

        # Extract metadata
        title = extract_title_from_story(story_text)
        story_id = datetime.now().strftime("%Y%m%d_%H%M%S")

        canonical_keys = {}
        if skeleton and skeleton.get("canonical_core"):
            canonical_keys = skeleton.get("canonical_core", {})

        # Phase 2B: Generate summary and observe similarity
        semantic_summary = generate_semantic_summary(story_text, title, config)
        similarity_observation = observe_similarity(
            current_summary=semantic_summary,
            current_title=title,
            canonical_keys=canonical_keys
        )

        # Phase 2C: Determine signal and decision
        signal = get_similarity_signal(similarity_observation)
        logger.info(f"[Phase2C][CONTROL]   신호: {signal}")
        logger.info(f"[DedupSignal] Signal={signal}, Template={template_id}")

        if should_accept_story(signal):
            # ACCEPT
            logger.info(f"[Phase2C][CONTROL]   결정: ACCEPT")
            logger.info(f"[DedupSignal] Decision=ACCEPT")

            # Add to in-memory
            add_to_generation_memory(
                story_id=story_id,
                template_id=template_id,
                title=title,
                semantic_summary=semantic_summary,
                canonical_keys=canonical_keys
            )

            # Build result
            skeleton_info = None
            if skeleton:
                skeleton_info = {
                    "template_id": template_id,
                    "template_name": template_name,
                    "canonical_core": skeleton.get("canonical_core")
                }

            result = {
                "story": story_text,
                "metadata": {
                    "generated_at": datetime.now().isoformat(),
                    "model": config["model"],
                    "template_used": None,
                    "skeleton_template": skeleton_info,
                    "custom_request": None,
                    "config": {
                        "max_tokens": config["max_tokens"],
                        "temperature": config["temperature"]
                    },
                    "word_count": len(story_text),
                    "usage": usage,
                    "phase2c_attempt": attempt,
                    "phase2c_signal": signal,
                    "phase2c_decision": "accepted"
                }
            }

            if similarity_observation:
                result["metadata"]["similarity_observation"] = similarity_observation

            # Save story
            if save_output:
                file_path = save_story(
                    story_text,
                    config["output_dir"],
                    result["metadata"],
                    None  # template
                )
                result["file_path"] = file_path
                logger.info(f"[Phase2C][CONTROL] 저장 완료: {file_path}")

            # Persist to registry
            registry.add_story(
                story_id=story_id,
                title=title,
                template_id=template_id,
                template_name=template_name,
                semantic_summary=semantic_summary,
                accepted=True,
                decision_reason="accepted"
            )

            # Record similarity edge if available
            if similarity_observation:
                registry.add_similarity_edge(
                    story_id=story_id,
                    compared_story_id=similarity_observation.get("closest_story_id", ""),
                    similarity_score=similarity_observation.get("text_similarity", 0.0),
                    signal=signal
                )

            logger.info("[Phase2C][CONTROL] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            return result

        else:
            # HIGH - need to retry
            logger.info(f"[Phase2C][CONTROL]   결정: RETRY (HIGH 감지)")
            logger.info(f"[DedupSignal] Decision=RETRY, Attempt={attempt}")
            if attempt < max_attempts - 1:
                logger.info(f"[Phase2C][CONTROL]   다음 시도로 진행...")
            continue

    # All attempts exhausted - SKIP
    logger.info("[Phase2C][CONTROL] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    logger.info("[Phase2C][CONTROL] 모든 시도 실패 - SKIP")
    logger.info("[Phase2C][CONTROL] 파일 저장 안함, 루프 계속")
    logger.info("[DedupSignal] Decision=SKIP, Reason=AllAttemptsExhausted")
    logger.info("[Phase2C][CONTROL] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    # Record skip in registry
    registry.add_story(
        story_id=story_id,
        title=title,
        template_id=template_id,
        template_name=template_name,
        semantic_summary=semantic_summary,
        accepted=False,
        decision_reason="skipped_high_dup_after_2_attempts"
    )

    return None


def customize_template(
    template_path: str = "horror_story_prompt_template.json",
    **kwargs: Any
) -> Dict[str, Any]:
    """
    템플릿의 특정 값을 커스터마이즈합니다.

    kwargs로 전달된 키-값 쌍을 템플릿에 적용하여
    커스터마이즈된 템플릿을 반환합니다.

    Args:
        template_path (str): 원본 템플릿 경로
        **kwargs: 수정할 필드와 값
            - genre: 장르 변경
            - location: 배경 장소 변경
            - atmosphere: 분위기 변경
            - 기타 템플릿 내 필드명 사용 가능

    Returns:
        Dict[str, Any]: 커스터마이즈된 템플릿

    Example:
        >>> custom = customize_template(
        ...     genre="gothic_horror",
        ...     location="old_mansion",
        ...     atmosphere="oppressive"
        ... )
        >>> result = generate_horror_story_with_template(custom)
    """
    logger.info(f"템플릿 커스터마이즈 시작: {len(kwargs)}개 항목")
    template = load_prompt_template(template_path)

    # kwargs로 전달된 값들을 템플릿에 적용
    for key, value in kwargs.items():
        # nested dictionary 업데이트를 위한 dot notation 지원
        if '.' in key:
            keys = key.split('.')
            current = template
            for k in keys[:-1]:
                if k not in current:
                    current[k] = {}
                current = current[k]
            current[keys[-1]] = value
            logger.debug(f"템플릿 업데이트: {key} = {value}")
        else:
            # 일반적인 필드 찾기 및 업데이트
            if key in template.get("story_config", {}):
                template["story_config"][key] = value
                logger.debug(f"story_config 업데이트: {key} = {value}")
            elif "setting" in template.get("story_elements", {}) and \
                 key in template["story_elements"]["setting"]:
                template["story_elements"]["setting"][key] = value
                logger.debug(f"setting 업데이트: {key} = {value}")

    logger.info("템플릿 커스터마이즈 완료")
    return template


def main() -> None:
    """
    메인 실행 함수.

    호러 소설 생성기를 실행하고 결과를 출력합니다.
    향후 API 서버로 확장 시 이 함수는 테스트 용도로만 사용됩니다.

    Raises:
        Exception: 생성 프로세스 중 오류 발생 시
    """
    try:
        # 기본 실행: 템플릿 그대로 사용
        result = generate_horror_story()

        logger.info(f"생성 완료 - 단어 수: {result['metadata']['word_count']}자")

        if "file_path" in result:
            logger.info(f"저장 위치: {result['file_path']}")

        # 미리보기 출력
        preview_length = min(500, len(result["story"]))
        logger.info("=" * 80)
        logger.info("생성된 소설 미리보기:")
        logger.info("=" * 80)
        logger.info(result["story"][:preview_length] + "...")

    except Exception as e:
        logger.error(f"오류 발생: {str(e)}", exc_info=True)
        raise


if __name__ == "__main__":
    main()
