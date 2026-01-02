# Contributing to Horror Story Generator

호러 소설 생성기 프로젝트에 기여해주셔서 감사합니다! 이 문서는 프로젝트에 기여하는 방법을 안내합니다.

## 목차

- [프로젝트 구조](#프로젝트-구조)
- [개발 환경 설정](#개발-환경-설정)
- [코딩 컨벤션](#코딩-컨벤션)
- [새 기능 추가하기](#새-기능-추가하기)
- [테스트 방법](#테스트-방법)
- [Pull Request 가이드라인](#pull-request-가이드라인)
- [커밋 메시지 규칙](#커밋-메시지-규칙)

---

## 프로젝트 구조

```
n8n-test/
├── horror_story_generator.py      # 핵심 모듈: 호러 소설 생성 로직
├── main.py                        # 테스트 실행 스크립트
├── horror_story_prompt_template.json  # 프롬프트 템플릿 설정
├── .env                           # 환경 변수 (API 키 등)
├── .env.example                   # 환경 변수 예시
├── requirements.txt               # Python 패키지 의존성
├── generated_stories/             # 생성된 소설 저장 디렉토리
│   ├── horror_story_*.md          # 마크다운 형식 소설
│   └── horror_story_*_metadata.json  # 메타데이터
├── logs/                          # 실행 로그 디렉토리
│   └── horror_story_*.log         # 타임스탬프 기반 로그 파일
└── CONTRIBUTING.md                # 이 문서
```

### 주요 파일 설명

- **`horror_story_generator.py`**: 소설 생성의 모든 로직이 포함된 핵심 모듈
  - 환경 변수 로드
  - 프롬프트 템플릿 처리
  - Claude API 호출
  - 마크다운 파일 생성 (Astro + GraphQL 블로그 포맷)

- **`main.py`**: 테스트 및 실행 스크립트
  - 기본 생성 테스트
  - 커스텀 요청 테스트
  - 향후 API 개발 참고 코드 포함

- **`horror_story_prompt_template.json`**: 소설 생성 설정
  - 장르, 분위기, 스토리 구조
  - 캐릭터, 플롯 요소
  - 글쓰기 스타일

---

## 개발 환경 설정

### 1. 저장소 클론

```bash
git clone <repository-url>
cd n8n-test
```

### 2. Python 가상환경 설정

Python 3.8 이상이 필요합니다.

```bash
# 가상환경 생성
python -m venv venv

# 가상환경 활성화
# macOS/Linux:
source venv/bin/activate

# Windows:
venv\Scripts\activate
```

### 3. 의존성 설치

```bash
pip install -r requirements.txt
```

### 4. 환경 변수 설정

`.env.example`을 복사하여 `.env` 파일을 만들고 필요한 값을 입력합니다.

```bash
cp .env.example .env
```

`.env` 파일 예시:

```env
ANTHROPIC_API_KEY=your_api_key_here
CLAUDE_MODEL=claude-sonnet-4-5-20250929
MAX_TOKENS=8192
TEMPERATURE=0.8
OUTPUT_DIR=./generated_stories
LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR, CRITICAL
```

### 5. 테스트 실행

```bash
python main.py
```

---

## 코딩 컨벤션

이 프로젝트는 Python 표준 스타일 가이드를 따릅니다.

### 일반 규칙

- **PEP 8** 스타일 가이드 준수
- **타입 힌트**: 모든 함수에 타입 힌트 필수
- **Docstring**: Google 스타일 docstring 사용
- **Logging**: `print` 대신 `logging` 모듈 사용

### 타입 힌트 예시

```python
from typing import Dict, List, Optional, Any

def my_function(param: str, optional_param: Optional[int] = None) -> Dict[str, Any]:
    """
    함수 설명.

    Args:
        param (str): 파라미터 설명
        optional_param (Optional[int]): 옵션 파라미터 설명

    Returns:
        Dict[str, Any]: 반환값 설명
    """
    return {"result": param}
```

### Docstring 스타일 (Google)

```python
def function_name(arg1: str, arg2: int) -> bool:
    """
    한 줄 요약.

    더 상세한 설명이 필요하면 여기에 작성합니다.

    Args:
        arg1 (str): 첫 번째 인자 설명
        arg2 (int): 두 번째 인자 설명

    Returns:
        bool: 반환값 설명

    Raises:
        ValueError: 발생할 수 있는 예외 설명

    Example:
        >>> result = function_name("test", 42)
        >>> print(result)
        True
    """
    pass
```

### Logging 사용

```python
import logging

logger = logging.getLogger(__name__)

# 사용 예시
logger.debug("디버그 메시지")
logger.info("정보 메시지")
logger.warning("경고 메시지")
logger.error("오류 메시지")
logger.critical("심각한 오류 메시지")
```

### 네이밍 컨벤션

- **함수/변수**: `snake_case`
- **클래스**: `PascalCase`
- **상수**: `UPPER_SNAKE_CASE`
- **Private 멤버**: `_leading_underscore`

---

## 새 기능 추가하기

### 1. 브랜치 생성

```bash
git checkout -b feature/your-feature-name
```

### 2. 기능 구현

#### 새 함수 추가 시

1. **타입 힌트** 추가
2. **Docstring** 작성 (Google 스타일)
3. **Logging** 적용
4. **에러 처리** 구현

```python
def new_feature(param: str) -> Dict[str, Any]:
    """
    새 기능 설명.

    Args:
        param (str): 파라미터 설명

    Returns:
        Dict[str, Any]: 결과

    Raises:
        ValueError: 유효하지 않은 입력
    """
    logger.info(f"새 기능 실행: {param}")

    try:
        # 로직 구현
        result = {"status": "success"}
        logger.info("새 기능 완료")
        return result
    except Exception as e:
        logger.error(f"오류 발생: {str(e)}")
        raise
```

#### 템플릿 수정 시

`horror_story_prompt_template.json`을 수정할 때는:

1. JSON 형식 유효성 검증
2. 기존 구조와 호환성 유지
3. 새 필드 추가 시 문서화

### 3. 테스트 작성

`main.py`에 테스트 케이스를 추가하거나, 별도의 테스트 함수를 작성합니다.

```python
def test_new_feature():
    """새 기능 테스트."""
    logger.info("새 기능 테스트 시작")

    try:
        result = new_feature("test_param")
        assert result["status"] == "success"
        logger.info("테스트 통과")
    except AssertionError:
        logger.error("테스트 실패")
        raise
```

---

## 테스트 방법

### 기본 테스트

```bash
# 기본 실행
python main.py
```

### 특정 기능 테스트

`main.py`에서 해당 테스트를 주석 해제하고 실행:

```python
# 테스트 2: 커스텀 요청
custom_result = run_custom_generation(
    "1980년대 한국 시골 마을을 배경으로, "
    "폐교된 초등학교에서 벌어지는 섬뜩한 사건을 다룬 호러 소설을 써주세요."
)
```

### 로그 확인

실행할 때마다 `logs/` 디렉토리에 타임스탬프 기반 로그 파일이 생성됩니다:

```bash
# 최신 로그 파일 확인
ls -lt logs/ | head -5

# 특정 로그 파일 내용 확인
cat logs/horror_story_20260102_155606.log

# 실시간 로그 모니터링
tail -f logs/horror_story_*.log
```

로그 파일에는 다음 정보가 포함됩니다:
- 환경 변수 로드 정보
- 프롬프트 생성 과정
- API 호출 상태
- **토큰 사용량** (Input, Output, Total)
- 파일 저장 경로
- 오류 및 경고 메시지

로깅 레벨 변경:

```bash
# .env 파일에서 LOG_LEVEL 수정
LOG_LEVEL=DEBUG  # 더 상세한 로그
LOG_LEVEL=WARNING  # 경고 이상만 표시
```

### 생성된 파일 확인

```bash
ls -la generated_stories/
cat generated_stories/horror_story_*.md
```

### 마크다운 포맷 검증

생성된 파일의 YAML frontmatter 확인:

```bash
head -20 generated_stories/horror_story_*.md
```

---

## Pull Request 가이드라인

### PR 체크리스트

PR을 제출하기 전에 다음 항목을 확인하세요:

- [ ] 코드에 **타입 힌트** 추가
- [ ] 모든 함수에 **Docstring** 작성
- [ ] `print` 대신 **logging** 사용
- [ ] **PEP 8** 스타일 가이드 준수
- [ ] 테스트 실행 및 통과 확인
- [ ] 로그 파일 확인 (오류 없음)
- [ ] 불필요한 파일 제외 (`.env`, `__pycache__`, `*.pyc` 등)
- [ ] 커밋 메시지 규칙 준수

### PR 템플릿

```markdown
## 변경 사항

- 추가한 기능 또는 수정한 내용 설명

## 관련 이슈

- Closes #이슈번호 (해당되는 경우)

## 테스트

- [ ] 로컬에서 테스트 완료
- [ ] 생성된 마크다운 파일 검증 완료

## 스크린샷 (선택사항)

필요시 스크린샷 첨부
```

### 리뷰 프로세스

1. PR 제출
2. 코드 리뷰 및 피드백
3. 수정 사항 반영
4. 승인 후 머지

---

## 커밋 메시지 규칙

### 기본 형식

```
<타입>: <제목>

<본문> (선택사항)

<푸터> (선택사항)
```

### 타입

- `feat`: 새로운 기능 추가
- `fix`: 버그 수정
- `docs`: 문서 수정
- `style`: 코드 포맷팅, 세미콜론 누락 등 (로직 변경 없음)
- `refactor`: 코드 리팩토링
- `test`: 테스트 코드 추가 또는 수정
- `chore`: 빌드 프로세스, 패키지 매니저 등 수정

### 예시

```bash
# 기능 추가
git commit -m "feat: 커스텀 템플릿 지원 추가"

# 버그 수정
git commit -m "fix: YAML frontmatter 생성 시 인코딩 오류 수정"

# 문서 수정
git commit -m "docs: CONTRIBUTING.md에 코딩 컨벤션 추가"

# 리팩토링
git commit -m "refactor: save_story 함수 타입 힌트 개선"
```

---

## 향후 개발 계획

### API 서버 구현

- FastAPI 기반 REST API
- GraphQL API (Strawberry)
- 인증/인가 시스템
- Rate limiting

### 기능 개선

- 다양한 장르 지원
- 템플릿 커스터마이징 UI
- 소설 스타일 분석 및 추천
- 다국어 지원

### 인프라

- Docker 컨테이너화
- CI/CD 파이프라인
- 자동 배포
- 모니터링 및 로깅

---

## 질문 및 문의

- **이슈**: GitHub Issues에 등록
- **토론**: GitHub Discussions 활용
- **긴급**: 프로젝트 관리자에게 연락

---

## 라이선스

이 프로젝트는 MIT 라이선스를 따릅니다.
