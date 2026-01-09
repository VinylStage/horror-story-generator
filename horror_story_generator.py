"""
호러 소설 생성기 - Claude API를 사용한 함수형 구현

이 모듈은 Claude API를 활용하여 한국어 호러 소설을 자동으로 생성합니다.
Astro + GraphQL 블로그에 최적화된 마크다운 포맷으로 출력합니다.

향후 API 서버로 확장 가능하도록 설계되었습니다.
"""

import json
import logging
import os
import random
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from dotenv import load_dotenv
import anthropic

# Phase 2A: Template skeleton configuration
TEMPLATE_SKELETONS_PATH = Path(__file__).parent / "phase1_foundation" / "03_templates" / "template_skeletons_v1.json"

# Phase 2A: In-memory state for back-to-back prevention (process-scoped only, not persisted)
_last_template_id: Optional[str] = None

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
_generation_memory: List['GenerationRecord'] = []


# 로깅 설정 함수
def setup_logging(log_level: str = "INFO") -> logging.Logger:
    """
    로깅을 설정하고 logger 인스턴스를 반환합니다.

    실행할 때마다 별도의 타임스탬프 기반 로그 파일을 logs/ 디렉토리에 생성합니다.

    Args:
        log_level (str): 로깅 레벨 (DEBUG, INFO, WARNING, ERROR, CRITICAL)

    Returns:
        logging.Logger: 설정된 logger 인스턴스
    """
    # logs 디렉토리 생성
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    # 타임스탬프 기반 로그 파일명
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = log_dir / f"horror_story_{timestamp}.log"

    # 로깅 레벨 설정
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    # 로거 설정
    logger = logging.getLogger(__name__)
    logger.setLevel(numeric_level)

    # propagate를 False로 설정하여 root logger로 전파 방지 (중복 로그 방지)
    logger.propagate = False

    # 기존 핸들러 제거 (중복 방지)
    if logger.handlers:
        logger.handlers.clear()

    # 포맷터
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # 콘솔 핸들러
    console_handler = logging.StreamHandler()
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # 파일 핸들러
    file_handler = logging.FileHandler(log_filename, encoding='utf-8')
    file_handler.setLevel(numeric_level)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    logger.info(f"로깅 시작 - 레벨: {log_level}, 로그 파일: {log_filename}")

    return logger


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


# =============================================================================
# Phase 2A: Template Skeleton Functions
# =============================================================================

def load_template_skeletons() -> List[Dict[str, Any]]:
    """
    Phase 1에서 정의한 템플릿 스켈레톤을 로드합니다.

    Returns:
        List[Dict[str, Any]]: 15개의 템플릿 스켈레톤 리스트

    Raises:
        FileNotFoundError: 템플릿 파일이 존재하지 않는 경우
    """
    if not TEMPLATE_SKELETONS_PATH.exists():
        logger.warning(f"템플릿 스켈레톤 파일 없음: {TEMPLATE_SKELETONS_PATH}")
        return []

    with open(TEMPLATE_SKELETONS_PATH, 'r', encoding='utf-8') as f:
        skeletons = json.load(f)

    logger.debug(f"템플릿 스켈레톤 {len(skeletons)}개 로드 완료")
    return skeletons


def select_random_template() -> Optional[Dict[str, Any]]:
    """
    Phase 2A: 무작위로 템플릿 스켈레톤을 선택합니다.

    - 상태 없음 between process runs (stateless across restarts)
    - 메모리 없음 (no disk persistence)
    - 단순 무작위 선택 (simple random choice)
    - 동일 프로세스 내에서 연속 동일 템플릿 방지 (back-to-back prevention)

    Returns:
        Optional[Dict[str, Any]]: 선택된 템플릿 스켈레톤, 또는 None (파일 없을 시)
    """
    global _last_template_id

    skeletons = load_template_skeletons()
    if not skeletons:
        logger.info("사용 가능한 템플릿 없음 - 기본 프롬프트 사용")
        return None

    # Back-to-back prevention: exclude last used template if possible
    if _last_template_id and len(skeletons) > 1:
        candidates = [s for s in skeletons if s.get('template_id') != _last_template_id]
    else:
        candidates = skeletons

    selected = random.choice(candidates)
    _last_template_id = selected.get('template_id')

    logger.info(f"템플릿 선택: {selected.get('template_id')} - {selected.get('template_name')}")
    return selected


# =============================================================================
# Phase 2B: Generation Memory Functions (Observation Only)
# =============================================================================

def generate_semantic_summary(
    story_text: str,
    title: str,
    config: Dict[str, Any]
) -> str:
    """
    Phase 2B: 스토리의 의미적 요약을 생성합니다 (관측용).

    LLM을 사용하여 1-3문장의 짧은 요약을 생성합니다.
    이 요약은 유사도 관측에만 사용되며, 생성에 영향을 주지 않습니다.

    Args:
        story_text: 생성된 스토리 전문
        title: 스토리 제목
        config: API 설정

    Returns:
        str: 1-3문장 요약
    """
    logger.info("[Phase2B][OBSERVE] 의미적 요약 생성 시작")

    try:
        client = anthropic.Anthropic(api_key=config["api_key"])

        # Use a fast, cheap call for summarization
        message = client.messages.create(
            model=config["model"],
            max_tokens=200,
            temperature=0.0,  # Deterministic for consistency
            system="You are a story summarizer. Generate a 1-3 sentence summary focusing on: setting, protagonist situation, type of horror, and ending pattern. Be concise and factual.",
            messages=[
                {
                    "role": "user",
                    "content": f"Summarize this horror story in 1-3 sentences (Korean):\n\nTitle: {title}\n\n{story_text[:2000]}"  # Limit input
                }
            ]
        )

        summary = message.content[0].text.strip()
        logger.info(f"[Phase2B][OBSERVE] 의미적 요약 생성 완료: {summary[:100]}...")
        return summary

    except Exception as e:
        logger.warning(f"[Phase2B][OBSERVE] 요약 생성 실패, 폴백 사용: {e}")
        # Fallback: use first 200 chars of story
        return story_text[:200].strip()


def compute_text_similarity(text1: str, text2: str) -> float:
    """
    Phase 2B: 두 텍스트 간의 간단한 유사도를 계산합니다.

    외부 라이브러리 없이 단어 집합 기반 Jaccard 유사도를 사용합니다.
    이는 관측용이며, 생성 결정에 사용되지 않습니다.

    Args:
        text1: 첫 번째 텍스트
        text2: 두 번째 텍스트

    Returns:
        float: 0.0 ~ 1.0 사이의 유사도 점수
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
    Phase 2B: 현재 스토리와 기존 스토리들의 유사도를 관측합니다.

    ⚠️ 이 함수는 관측만 수행합니다.
    ⚠️ 생성을 차단하거나 변경하지 않습니다.
    ⚠️ 결과는 로그에만 기록됩니다.

    Args:
        current_summary: 현재 스토리의 의미적 요약
        current_title: 현재 스토리 제목
        canonical_keys: 현재 스토리의 정규화 키 (setting, primary_fear, etc.)

    Returns:
        Optional[Dict]: 유사도 관측 결과 (가장 유사한 스토리 정보)
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
    Phase 2B: 생성된 스토리를 메모리에 추가합니다.

    이 메모리는 프로세스 종료 시 삭제됩니다.
    디스크에 저장되지 않습니다.

    Args:
        story_id: 스토리 고유 ID
        template_id: 사용된 템플릿 ID
        title: 스토리 제목
        semantic_summary: 의미적 요약
        canonical_keys: 정규화 키들
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


def build_system_prompt(
    template: Optional[Dict[str, Any]] = None,
    skeleton: Optional[Dict[str, Any]] = None
) -> str:
    """
    시스템 프롬프트를 생성합니다.

    템플릿이 제공되지 않으면 기본 심리 공포 프롬프트를 사용합니다.
    템플릿이 제공되면 기존 로직을 따릅니다 (하위 호환성).
    Phase 2A: skeleton이 제공되면 스토리 구조가 추가됩니다.

    Args:
        template (Optional[Dict[str, Any]]): 프롬프트 템플릿 데이터 (legacy format)
        skeleton (Optional[Dict[str, Any]]): Phase 2A 템플릿 스켈레톤

    Returns:
        str: 완성된 시스템 프롬프트 문자열

    Example:
        >>> system_prompt = build_system_prompt()  # 기본 프롬프트 사용
        >>> system_prompt = build_system_prompt(template=old_template)  # 레거시 템플릿 기반
        >>> system_prompt = build_system_prompt(skeleton=selected_skeleton)  # Phase 2A 스켈레톤 기반
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


def call_claude_api(
    system_prompt: str,
    user_prompt: str,
    config: Dict[str, Union[str, int, float]]
) -> Dict[str, Any]:
    """
    Claude API를 호출하여 호러 소설을 생성합니다.

    Anthropic Messages API를 사용하여 시스템 및 사용자 프롬프트를 전달하고
    생성된 텍스트와 토큰 사용량을 반환합니다.

    Args:
        system_prompt (str): 시스템 프롬프트 (작가 역할 및 가이드라인)
        user_prompt (str): 사용자 프롬프트 (구체적 요청사항)
        config (Dict[str, Union[str, int, float]]): API 설정 정보
            - api_key: API 키
            - model: 모델 이름
            - max_tokens: 최대 토큰 수
            - temperature: 생성 온도

    Returns:
        Dict[str, Any]: 생성 결과
            - story_text (str): 생성된 호러 소설 텍스트
            - usage (Dict): 토큰 사용량 정보
                - input_tokens (int): 입력 토큰 수
                - output_tokens (int): 출력 토큰 수

    Raises:
        Exception: API 호출 실패 시 (네트워크 오류, 인증 실패 등)

    Example:
        >>> result = call_claude_api(system_prompt, user_prompt, config)
        >>> print(result['story_text'][:100])
        >>> print(f"Used {result['usage']['input_tokens']} input tokens")
    """
    logger.info("Claude API 호출 시작...")
    client = anthropic.Anthropic(api_key=config["api_key"])

    try:
        message = client.messages.create(
            model=config["model"],
            max_tokens=int(config["max_tokens"]),
            temperature=float(config["temperature"]),
            system=system_prompt,
            messages=[
                {
                    "role": "user",
                    "content": user_prompt
                }
            ]
        )

        story_text = message.content[0].text

        # Phase 1: Defensive usage extraction - handle missing usage gracefully
        if hasattr(message, 'usage') and message.usage:
            try:
                usage = {
                    "input_tokens": message.usage.input_tokens,
                    "output_tokens": message.usage.output_tokens,
                    "total_tokens": message.usage.input_tokens + message.usage.output_tokens
                }
                logger.info(f"소설 생성 완료 - 길이: {len(story_text)}자")
                logger.info(f"토큰 사용량 - Input: {usage['input_tokens']}, Output: {usage['output_tokens']}, Total: {usage['total_tokens']}")
            except (AttributeError, TypeError) as e:
                logger.warning(f"토큰 사용량 추출 실패 (usage 구조 이상): {e}")
                usage = None
        else:
            logger.warning("토큰 사용량 정보 없음 (message.usage missing)")
            usage = None

        return {
            "story_text": story_text,
            "usage": usage
        }

    except Exception as e:
        logger.error(f"Claude API 호출 중 오류 발생: {str(e)}", exc_info=True)
        raise Exception(f"Claude API 호출 중 오류 발생: {str(e)}")


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
        ...     template_path="templates/horror_story_prompt_template.json",
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

    # 3. 프롬프트 빌드
    logger.info("프롬프트 생성 중...")
    system_prompt = build_system_prompt(template, skeleton=skeleton)
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
    # ⚠️ This section OBSERVES ONLY - it does NOT prevent or alter generation
    # ⚠️ Memory resets on process restart - no disk persistence
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
