"""
호러 소설 생성기 - 메인 실행 파일

이 파일은 horror_story_generator 모듈을 테스트하기 위한 간단한 실행 스크립트입니다.
향후 FastAPI 또는 Flask 기반 API 서버로 확장 시 참고용으로 사용됩니다.
"""

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
from dotenv import load_dotenv
from horror_story_generator import generate_horror_story, customize_template


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


def main() -> None:
    """
    메인 실행 함수.

    테스트 케이스를 실행하고 결과를 확인합니다.
    """
    logger.info("=" * 80)
    logger.info("호러 소설 생성기 테스트")
    logger.info("=" * 80)

    try:
        # 테스트 1: 기본 생성
        logger.info("\n[테스트 1] 기본 호러 소설 생성")
        result = run_basic_generation()

        # 결과 미리보기
        if result and "story" in result:
            preview_length = min(300, len(result["story"]))
            logger.info("\n생성된 소설 미리보기:")
            logger.info("-" * 80)
            logger.info(result["story"][:preview_length] + "...")
            logger.info("-" * 80)
            logger.info(f"전체 길이: {result['metadata']['word_count']}자")
            logger.info(f"저장 위치: {result.get('file_path', 'N/A')}")

        # 테스트 2: 커스텀 요청 (주석 처리 - 필요시 활성화)
        # logger.info("\n[테스트 2] 커스텀 요청으로 생성")
        # custom_result = run_custom_generation(
        #     "1980년대 한국 시골 마을을 배경으로, "
        #     "폐교된 초등학교에서 벌어지는 섬뜩한 사건을 다룬 호러 소설을 써주세요."
        # )

        # 테스트 3: 템플릿 커스터마이징 (주석 처리 - 향후 개발용)
        # logger.info("\n[테스트 3] 템플릿 커스터마이징")
        # template_result = run_template_customization_test()

    except Exception as e:
        logger.error(f"테스트 실행 중 오류 발생: {str(e)}", exc_info=True)
        raise

    logger.info("\n" + "=" * 80)
    logger.info("테스트 완료")
    logger.info("=" * 80)


if __name__ == "__main__":
    main()
