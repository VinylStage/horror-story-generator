"""
호러 소설 생성기 - 메인 실행 파일

이 파일은 horror_story_generator 모듈을 테스트하기 위한 간단한 실행 스크립트입니다.
향후 FastAPI 또는 Flask 기반 API 서버로 확장 시 참고용으로 사용됩니다.

Phase 1: 24h background operation support added
"""

import argparse
import logging
import os
import signal
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
from dotenv import load_dotenv
from horror_story_generator import generate_horror_story, customize_template


# Phase 1: Graceful shutdown support
shutdown_requested = False

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


# 환경 변수 로드
load_dotenv()

# 로깅 설정 (horror_story_generator와 동일한 방식)
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
log_filename = log_dir / f"horror_story_{timestamp}.log"
log_level = os.getenv("LOG_LEVEL", "INFO").upper()

logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(log_filename, encoding='utf-8')
    ]
)

logger = logging.getLogger(__name__)
logger.info(f"메인 스크립트 시작 - 로그 파일: {log_filename}")


def run_basic_generation() -> Dict[str, Any]:
    """
    기본 호러 소설 생성 테스트.

    템플릿을 그대로 사용하여 소설을 생성하고 결과를 반환합니다.

    Returns:
        Dict[str, Any]: 생성 결과 (story, metadata, file_path 포함)
    """
    logger.info("기본 호러 소설 생성 테스트 시작")
    result = generate_horror_story()
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
    """
    parser = argparse.ArgumentParser(
        description="호러 소설 생성기 - 24h 연속 실행 지원",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  # 단일 실행 (기존 동작)
  python main.py

  # 24시간 연속 실행, 30분 간격
  python main.py --duration-seconds 86400 --interval-seconds 1800

  # 최대 10개 생성, 1시간 간격
  python main.py --max-stories 10 --interval-seconds 3600

  # 무제한 실행, 10분 간격 (Ctrl+C로 종료)
  python main.py --interval-seconds 600
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
    return parser.parse_args()


def main() -> None:
    """
    메인 실행 함수.

    Phase 1: 24h 연속 실행 지원 추가
    - CLI 인자: --duration-seconds, --max-stories, --interval-seconds
    - Graceful shutdown: SIGINT/SIGTERM 처리
    - 통계 로깅: 생성 개수, 토큰 사용량, 실행 시간
    """
    global shutdown_requested

    # CLI 인자 파싱
    args = parse_args()

    # 신호 핸들러 등록
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # 실행 시작
    logger.info("=" * 80)
    logger.info("호러 소설 생성기 시작 (Phase 1: 24h operation support)")
    logger.info("=" * 80)
    logger.info(f"설정:")
    logger.info(f"  - 최대 실행 시간: {args.duration_seconds}초 ({args.duration_seconds / 3600:.1f}시간)" if args.duration_seconds else "  - 최대 실행 시간: 무제한")
    logger.info(f"  - 최대 생성 개수: {args.max_stories}개" if args.max_stories else "  - 최대 생성 개수: 무제한")
    logger.info(f"  - 생성 간격: {args.interval_seconds}초")
    logger.info("=" * 80)

    # 통계 추적
    start_time = time.time()
    stories_generated = 0
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

            result = run_basic_generation()

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
        if stories_generated > 0:
            logger.info(f"평균 생성 시간: {total_duration / stories_generated:.1f}초/개")
        logger.info(f"총 토큰 사용량:")
        logger.info(f"  - Input tokens: {total_input_tokens:,}")
        logger.info(f"  - Output tokens: {total_output_tokens:,}")
        logger.info(f"  - Total tokens: {total_tokens:,}")
        if stories_generated > 0:
            logger.info(f"평균 토큰 사용량: {total_tokens / stories_generated:.0f} tokens/story")
        logger.info("=" * 80)


if __name__ == "__main__":
    main()
