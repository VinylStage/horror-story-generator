"""
호러 소설 생성기 - 메인 실행 파일

이 파일은 horror_story_generator 모듈을 테스트하기 위한 간단한 실행 스크립트입니다.
향후 FastAPI 또는 Flask 기반 API 서버로 확장 시 참고용으로 사용됩니다.

Phase 1: 24h background operation support added
Phase 2C: SQLite story registry + HIGH-only dedup control
"""

import argparse
import json
import logging
import os
import signal
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
from dotenv import load_dotenv
from src.story.generator import (
    generate_horror_story, customize_template,
    generate_with_dedup_control
)
from src.infra.logging_config import setup_logging
from src.dedup.similarity import load_past_stories_into_memory
from src.registry.story_registry import init_registry, get_registry, close_registry


# Phase 1: Graceful shutdown support
shutdown_requested = False


# 환경 변수 로드
load_dotenv()

# =============================================================================
# Logging Configuration (reuse horror_story_generator.setup_logging)
# =============================================================================
log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logger = setup_logging(log_level)
logger.info("메인 스크립트 시작")


def signal_handler(signum, frame):
    """
    SIGINT / SIGTERM 핸들러 - 현재 생성 완료 후 종료
    """
    global shutdown_requested
    signal_name = "SIGINT" if signum == signal.SIGINT else "SIGTERM"
    logger.info(f"\n{'=' * 80}")
    logger.info(f"{signal_name} 수신 - 현재 작업 완료 후 종료합니다")
    logger.info(f"{'=' * 80}")
    shutdown_requested = True


def run_basic_generation(model_spec: Optional[str] = None) -> Dict[str, Any]:
    """
    기본 호러 소설 생성 테스트.

    템플릿을 그대로 사용하여 소설을 생성하고 결과를 반환합니다.

    Args:
        model_spec: 모델 선택. None이면 기본 Claude 모델 사용.

    Returns:
        Dict[str, Any]: 생성 결과 (story, metadata, file_path 포함)
    """
    logger.info("기본 호러 소설 생성 테스트 시작")
    if model_spec:
        logger.info(f"사용 모델: {model_spec}")
    result = generate_horror_story(model_spec=model_spec)
    logger.info(f"생성 완료 - 파일: {result.get('file_path', 'N/A')}")
    return result


def run_custom_generation(custom_request: str) -> Dict[str, Any]:
    """
    커스텀 요청으로 호러 소설 생성 테스트.

    Args:
        custom_request (str): 사용자 커스텀 요청사항

    Returns:
        Dict[str, Any]: 생성 결과
    """
    logger.info(f"커스텀 호러 소설 생성 테스트 시작: {custom_request[:50]}...")
    result = generate_horror_story(custom_request=custom_request)
    logger.info(f"생성 완료 - 파일: {result.get('file_path', 'N/A')}")
    return result


def run_template_customization_test() -> Dict[str, Any]:
    """
    템플릿 커스터마이징 테스트.

    템플릿의 일부 값을 변경하여 소설을 생성합니다.

    Returns:
        Dict[str, Any]: 생성 결과
    """
    logger.info("템플릿 커스터마이징 테스트 시작")

    # 템플릿 커스터마이징 예시
    custom_template = customize_template(
        genre="gothic_horror",
        atmosphere="oppressive"
    )

    # 커스텀 템플릿은 아직 generate_horror_story에서 직접 사용할 수 없으므로
    # 이 부분은 향후 개선 필요
    logger.info("템플릿 커스터마이징 완료 (향후 API에서 활용 예정)")

    return {"status": "template_customized", "template": custom_template}


# ============================================================================
# 향후 API 개발 시 참고사항
# ============================================================================
"""
FastAPI 기반 REST API 구현 예시:

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="Horror Story Generator API")

class StoryRequest(BaseModel):
    custom_request: Optional[str] = None
    template_path: str = "horror_story_prompt_template.json"
    save_output: bool = True

class StoryResponse(BaseModel):
    story: str
    metadata: Dict[str, Any]
    file_path: Optional[str] = None

@app.post("/generate", response_model=StoryResponse)
async def generate_story(request: StoryRequest):
    try:
        result = generate_horror_story(
            template_path=request.template_path,
            custom_request=request.custom_request,
            save_output=request.save_output
        )
        return result
    except Exception as e:
        logger.error(f"API 오류: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

GraphQL 구현 예시 (Strawberry 사용):

import strawberry
from typing import Optional

@strawberry.type
class StoryMetadata:
    generated_at: str
    model: str
    word_count: int
    temperature: float

@strawberry.type
class GeneratedStory:
    story: str
    metadata: StoryMetadata
    file_path: Optional[str]

@strawberry.type
class Query:
    @strawberry.field
    def hello(self) -> str:
        return "Horror Story Generator API"

@strawberry.type
class Mutation:
    @strawberry.mutation
    def generate_story(
        self,
        custom_request: Optional[str] = None
    ) -> GeneratedStory:
        result = generate_horror_story(custom_request=custom_request)
        return GeneratedStory(
            story=result["story"],
            metadata=StoryMetadata(**result["metadata"]),
            file_path=result.get("file_path")
        )

schema = strawberry.Schema(query=Query, mutation=Mutation)
"""


def parse_args():
    """
    Phase 1: CLI 인자 파싱
    Phase 2C: 중복 제어 옵션 추가
    """
    parser = argparse.ArgumentParser(
        description="호러 소설 생성기 - 24h 연속 실행 지원 + Phase 2C 중복 제어",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  # 단일 실행 (기존 동작, 중복 제어 없음)
  python main.py

  # Phase 2C 중복 제어 활성화
  python main.py --enable-dedup --max-stories 10

  # 24시간 연속 실행, 30분 간격, 중복 제어
  python main.py --enable-dedup --duration-seconds 86400 --interval-seconds 1800

  # 연구 스텁 실행 (테스트용)
  python main.py --run-research-stub
        """
    )
    parser.add_argument(
        "--duration-seconds",
        type=int,
        default=None,
        help="실행 지속 시간(초). 지정하지 않으면 --max-stories 또는 수동 종료까지 실행"
    )
    parser.add_argument(
        "--max-stories",
        type=int,
        default=1,
        help="생성할 최대 소설 개수. 기본값=1 (단일 실행)"
    )
    parser.add_argument(
        "--interval-seconds",
        type=int,
        default=0,
        help="소설 생성 간 대기 시간(초). 기본값=0 (대기 없음)"
    )
    # Phase 2C: Dedup control
    parser.add_argument(
        "--enable-dedup",
        action="store_true",
        default=False,
        help="Phase 2C: HIGH-only 중복 제어 활성화. SQLite registry 사용."
    )
    parser.add_argument(
        "--db-path",
        type=str,
        default=None,
        help="Phase 2C: SQLite registry 경로. 기본값=./data/story_registry.db"
    )
    parser.add_argument(
        "--load-history",
        type=int,
        default=200,
        help="Phase 2C: 시작 시 로드할 과거 스토리 수. 기본값=200"
    )
    # Phase 2C: Research stub
    parser.add_argument(
        "--run-research-stub",
        action="store_true",
        default=False,
        help="Phase 2C: 연구 카드 스텁 생성 (테스트용)"
    )
    # Model selection
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="모델 선택. 기본=Claude Sonnet. 형식: 'ollama:llama3', 'ollama:qwen', 또는 Claude 모델명"
    )
    return parser.parse_args()


def run_research_stub() -> None:
    """
    Phase 2C: 연구 카드 스텁 생성 (테스트용).

    실제 웹 요청 없이 플레이스홀더 카드를 생성합니다.
    ./data/research_cards.jsonl에 추가합니다.
    """
    research_dir = Path("./data")
    research_dir.mkdir(parents=True, exist_ok=True)

    research_file = research_dir / "research_cards.jsonl"

    stub_card = {
        "card_id": f"STUB-{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        "title": "[STUB] Placeholder Research Card",
        "summary": "This is a stub card for testing the research pipeline. No real web request was made.",
        "tags": ["stub", "test", "placeholder"],
        "source": "local_stub",
        "created_at": datetime.now().isoformat(),
        "used_count": 0,
        "last_used_at": None
    }

    with open(research_file, 'a', encoding='utf-8') as f:
        f.write(json.dumps(stub_card, ensure_ascii=False) + '\n')

    logger.info(f"[Phase2C] 연구 카드 스텁 생성 완료: {stub_card['card_id']}")
    logger.info(f"[Phase2C] 저장 위치: {research_file}")


def main() -> None:
    """
    메인 실행 함수.

    Phase 1: 24h 연속 실행 지원 추가
    - CLI 인자: --duration-seconds, --max-stories, --interval-seconds
    - Graceful shutdown: SIGINT/SIGTERM 처리
    - 통계 로깅: 생성 개수, 토큰 사용량, 실행 시간

    Phase 2C: HIGH-only 중복 제어 추가
    - --enable-dedup: SQLite registry 사용
    - --db-path: 커스텀 DB 경로
    - --load-history: 시작 시 로드할 과거 스토리 수
    """
    global shutdown_requested

    # CLI 인자 파싱
    args = parse_args()

    # Phase 2C: 연구 스텁 명령 처리
    if args.run_research_stub:
        run_research_stub()
        return

    # 신호 핸들러 등록
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Phase 2C: Story Registry 초기화
    registry = None
    if args.enable_dedup:
        logger.info("[Phase2C][CONTROL] 중복 제어 모드 활성화")
        registry = init_registry(db_path=args.db_path)

        # 과거 스토리 로드
        past_stories = registry.load_recent_accepted(limit=args.load_history)
        if past_stories:
            load_past_stories_into_memory(past_stories)

        counts = registry.get_total_count()
        logger.info(f"[Phase2C][CONTROL] Registry 상태: 수락={counts['accepted']}, 스킵={counts['skipped']}")

    # 실행 시작
    logger.info("=" * 80)
    logger.info("호러 소설 생성기 시작 (Phase 1: 24h + Phase 2C: Dedup Control)")
    logger.info("=" * 80)
    logger.info(f"설정:")
    logger.info(f"  - 최대 실행 시간: {args.duration_seconds}초 ({args.duration_seconds / 3600:.1f}시간)" if args.duration_seconds else "  - 최대 실행 시간: 무제한")
    logger.info(f"  - 최대 생성 개수: {args.max_stories}개" if args.max_stories else "  - 최대 생성 개수: 무제한")
    logger.info(f"  - 생성 간격: {args.interval_seconds}초")
    logger.info(f"  - 중복 제어: {'활성화 (HIGH만 거부)' if args.enable_dedup else '비활성화'}")
    logger.info(f"  - 모델: {args.model or '기본 Claude Sonnet'}")
    logger.info("=" * 80)

    # 통계 추적
    start_time = time.time()
    stories_generated = 0
    stories_skipped = 0  # Phase 2C
    total_input_tokens = 0
    total_output_tokens = 0
    total_tokens = 0

    try:
        while True:
            # 종료 조건 체크
            if shutdown_requested:
                logger.info("종료 신호 수신 - 루프 종료")
                break

            # 시간 제한 체크
            if args.duration_seconds:
                elapsed = time.time() - start_time
                if elapsed >= args.duration_seconds:
                    logger.info(f"실행 시간 제한 도달 ({elapsed:.1f}초) - 루프 종료")
                    break

            # 생성 개수 제한 체크
            if args.max_stories and stories_generated >= args.max_stories:
                logger.info(f"생성 개수 제한 도달 ({stories_generated}개) - 루프 종료")
                break

            # 소설 생성
            iteration_start = time.time()
            logger.info("\n" + "=" * 80)
            logger.info(f"[{stories_generated + 1}] 소설 생성 시작")
            logger.info("=" * 80)

            # Phase 2C: 중복 제어 모드에 따른 생성
            if args.enable_dedup and registry:
                result = generate_with_dedup_control(registry=registry, model_spec=args.model)
                if result is None:
                    # SKIP - story was too similar after all attempts
                    stories_skipped += 1
                    logger.info(f"⚠ SKIP (HIGH 유사도) - 스킵 누적: {stories_skipped}개")
                    iteration_duration = time.time() - iteration_start
                    logger.info(f"✓ 소요 시간: {iteration_duration:.1f}초")
                    continue  # Move to next iteration without counting as generated
            else:
                result = run_basic_generation(model_spec=args.model)

            # 통계 업데이트
            stories_generated += 1
            if result and "metadata" in result:
                usage = result["metadata"].get("usage")
                if usage:
                    total_input_tokens += usage.get("input_tokens", 0)
                    total_output_tokens += usage.get("output_tokens", 0)
                    total_tokens += usage.get("total_tokens", 0)

            # 결과 요약
            if result and "story" in result:
                logger.info(f"✓ 생성 완료 - 길이: {result['metadata']['word_count']}자")
                logger.info(f"✓ 저장 위치: {result.get('file_path', 'N/A')}")
                if result["metadata"].get("usage"):
                    usage = result["metadata"]["usage"]
                    logger.info(f"✓ 토큰 사용: Input={usage['input_tokens']}, Output={usage['output_tokens']}, Total={usage['total_tokens']}")
                else:
                    logger.warning("⚠ 토큰 사용량 정보 없음")

                # Phase 2C: Show dedup decision if available
                if result["metadata"].get("phase2c_signal"):
                    logger.info(f"✓ Phase2C: 신호={result['metadata']['phase2c_signal']}, 시도={result['metadata']['phase2c_attempt']}")

            iteration_duration = time.time() - iteration_start
            logger.info(f"✓ 소요 시간: {iteration_duration:.1f}초")

            # 종료 조건 재확인 (현재 생성 완료 후)
            if shutdown_requested:
                logger.info("종료 신호 수신 - 현재 생성 완료, 루프 종료")
                break

            # 다음 생성까지 대기 (마지막 생성이 아닌 경우)
            if args.max_stories is None or stories_generated < args.max_stories:
                if args.interval_seconds > 0:
                    logger.info(f"다음 생성까지 {args.interval_seconds}초 대기 중...")
                    # 대기 중에도 종료 신호 확인 (1초 단위)
                    for _ in range(args.interval_seconds):
                        if shutdown_requested:
                            logger.info("대기 중 종료 신호 수신 - 루프 종료")
                            break
                        time.sleep(1)
                    if shutdown_requested:
                        break

    except KeyboardInterrupt:
        logger.info("\nKeyboardInterrupt 수신 - 종료 처리")
    except Exception as e:
        logger.error(f"실행 중 오류 발생: {str(e)}", exc_info=True)
        raise
    finally:
        # 최종 통계 출력
        end_time = time.time()
        total_duration = end_time - start_time

        logger.info("\n" + "=" * 80)
        logger.info("실행 완료 - 최종 통계")
        logger.info("=" * 80)
        logger.info(f"총 실행 시간: {total_duration:.1f}초 ({total_duration / 3600:.2f}시간)")
        logger.info(f"생성된 소설: {stories_generated}개")
        if args.enable_dedup:
            logger.info(f"스킵된 소설: {stories_skipped}개 (HIGH 유사도)")
        if stories_generated > 0:
            logger.info(f"평균 생성 시간: {total_duration / stories_generated:.1f}초/개")
        logger.info(f"총 토큰 사용량:")
        logger.info(f"  - Input tokens: {total_input_tokens:,}")
        logger.info(f"  - Output tokens: {total_output_tokens:,}")
        logger.info(f"  - Total tokens: {total_tokens:,}")
        if stories_generated > 0:
            logger.info(f"평균 토큰 사용량: {total_tokens / stories_generated:.0f} tokens/story")
        logger.info("=" * 80)

        # Phase 2C: Registry 정리
        if registry:
            close_registry()
            logger.info("[Phase2C][CONTROL] Registry 연결 종료")


if __name__ == "__main__":
    main()
