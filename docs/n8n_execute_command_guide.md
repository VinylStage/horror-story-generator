# n8n Execute Command 방식 기본 연동 가이드

## 개요

이 문서는 n8n의 **Execute Command 노드**를 사용하여 기존 Python 호러 소설 생성기를 호출하는 방법을 설명합니다.

**핵심 원칙:**
- 기존 Python 코드는 수정하지 않음
- `python main.py` 또는 `python horror_story_generator.py` 명령을 그대로 실행
- n8n 워크플로에서 실행 환경만 설정

---

## 템플릿 구조 이해

### templates 디렉토리

프로젝트는 **여러 개의 프롬프트 템플릿**을 사용할 수 있도록 설계되어 있습니다.

**디렉토리 구조:**
```
n8n-test/
├── templates/
│   ├── horror_story_prompt_template.json  # 기본 템플릿
│   ├── sample.json                         # 샘플 템플릿
│   └── (추가 템플릿 파일들...)
├── horror_story_generator.py
└── main.py
```

### 템플릿 선택 방식

**기본 동작 (템플릿 지정 없음):**
- `main.py` 실행 시 기본 템플릿 사용
- 기본 템플릿: `horror_story_prompt_template.json`

**특정 템플릿 선택:**
- `generate_horror_story()` 함수에 `template_path` 파라미터 전달
- 예: `generate_horror_story(template_path='templates/sample.json')`

**템플릿별 차이점:**
- 각 템플릿은 장르, 분위기, 플롯 구조 등이 다를 수 있음
- 출력 길이 및 스타일이 템플릿에 따라 달라짐
- n8n에서는 상황에 맞는 템플릿을 선택하여 실행 가능

---

## 전제 조건

### 1. n8n 실행 환경 확인

**로컬 n8n (권장):**
```bash
# n8n 설치 확인
npx n8n --version

# 또는 Docker
docker run -it --rm --name n8n -p 5678:5678 n8nio/n8n
```

### 2. Python 환경 확인

**호러 소설 생성기가 있는 서버/로컬 환경에서:**
```bash
# Python 버전 확인 (3.14 이상 필요)
python --version
# 또는
python3 --version

# 프로젝트 디렉토리로 이동
cd /Users/vinyl/vinylstudio/n8n-test

# Poetry 가상환경 확인
poetry env info

# 수동 실행 테스트
poetry run python3 main.py
```

**중요:** n8n Execute Command는 n8n이 실행되는 서버/환경에서 명령을 실행합니다.
- n8n이 로컬에서 실행 → 로컬 Python 환경 사용
- n8n이 Docker → Docker 컨테이너 내부 Python 환경 사용
- n8n.cloud → Execute Command 사용 불가 (HTTP API 방식 필요)

---

## Execute Command 노드 기본 설정

### 1. 노드 추가

1. n8n 워크플로 편집 화면에서 `+` 버튼 클릭
2. 검색창에 "Execute Command" 입력
3. "Execute Command" 노드 선택

### 2. 필수 설정 항목

#### **Command (명령어)**

**패턴 1: 기본 템플릿 사용 (main.py 실행)**
```bash
cd /Users/vinyl/vinylstudio/n8n-test && poetry run python3 main.py
```

**패턴 2: 특정 템플릿 선택 (Python -c 사용)**
```bash
cd /Users/vinyl/vinylstudio/n8n-test && poetry run python3 -c "from horror_story_generator import generate_horror_story; generate_horror_story(template_path='templates/horror_story_prompt_template.json')"
```

**패턴 3: 템플릿을 변수로 받기 (n8n 변수 활용)**
```bash
cd /Users/vinyl/vinylstudio/n8n-test && poetry run python3 -c "from horror_story_generator import generate_horror_story; generate_horror_story(template_path='{{ $json.template_path }}')"
```
- `{{ $json.template_path }}`는 이전 노드에서 전달된 변수
- 예: `templates/horror_story_prompt_psychological.json`

**패턴 4: 가상환경 직접 활성화**
```bash
cd /Users/vinyl/vinylstudio/n8n-test && source .venv/bin/activate && python -c "from horror_story_generator import generate_horror_story; generate_horror_story(template_path='templates/sample.json')"
```

**주의사항:**
- `cd` 명령과 `&&`로 연결하여 작업 디렉토리 먼저 이동
- 절대 경로 사용 권장 (상대 경로는 n8n 실행 위치에 따라 달라짐)
- `poetry run`을 사용하면 자동으로 가상환경 활성화
- 템플릿 파일 경로는 `templates/` 디렉토리 기준 상대 경로 사용

#### **Execute Once (실행 횟수)**
- ✅ 체크: 입력 데이터와 무관하게 1회만 실행 (권장)
- ❌ 체크 해제: 입력 데이터 항목마다 실행 (배치 처리 시)

기본값: ✅ 체크

#### **Timeout (타임아웃)**
```
180000
```
- 단위: 밀리초(ms)
- 180000ms = 3분
- Claude API 호출 시간 고려 (평균 2~3분)

---

## 환경 변수 설정 방법

### 방법 1: .env 파일 사용 (권장)

프로젝트 디렉토리의 `.env` 파일이 자동으로 로드됩니다.

**`.env` 파일 위치:**
```
/Users/vinyl/vinylstudio/n8n-test/.env
```

**`.env` 내용 예시:**
```env
ANTHROPIC_API_KEY=sk-ant-xxxxx
CLAUDE_MODEL=claude-sonnet-4-5-20250929
MAX_TOKENS=8192
TEMPERATURE=0.8
OUTPUT_DIR=./generated_stories
LOG_LEVEL=INFO
```

**확인 방법:**
```bash
cd /Users/vinyl/vinylstudio/n8n-test
cat .env
```

### 방법 2: Execute Command에서 환경 변수 주입

**노드 설정:**

"Add Option" → "Environment Variables" 선택

**환경 변수 입력 예시:**
| Name | Value |
|------|-------|
| `ANTHROPIC_API_KEY` | `sk-ant-xxxxx` |
| `CLAUDE_MODEL` | `claude-sonnet-4-5-20250929` |
| `OUTPUT_DIR` | `/Users/vinyl/vinylstudio/n8n-test/generated_stories` |

**주의:**
- 이 방식은 .env 파일을 오버라이드함
- API 키 같은 민감 정보는 n8n Credentials 사용 권장 (Task 4 참고)

---

## stdout/stderr 처리

### Execute Command 출력 구조

노드 실행 후 출력 데이터:

```json
{
  "stdout": "생성된 소설 미리보기...\n저장 위치: ./generated_stories/horror_story_20260102_155854.md",
  "stderr": "",
  "exitCode": 0
}
```

### 성공/실패 판단

**성공:**
- `exitCode` = 0
- `stderr` 비어있거나 경고만 포함

**실패:**
- `exitCode` ≠ 0
- `stderr`에 에러 메시지 포함

### 출력에서 파일 경로 추출

**다음 노드 추가:** Code 노드 (JavaScript)

```javascript
// Execute Command 노드의 출력에서 파일 경로 추출
const stdout = $input.item.json.stdout;

// 정규식으로 파일 경로 추출
const pathMatch = stdout.match(/저장 위치: (.+\.md)/);

if (pathMatch) {
  return {
    json: {
      file_path: pathMatch[1],
      full_output: stdout
    }
  };
} else {
  throw new Error('파일 경로를 찾을 수 없습니다');
}
```

---

## 경로 관련 주의사항

### 절대 경로 vs 상대 경로

**❌ 상대 경로 (비권장):**
```bash
cd n8n-test && poetry run python3 main.py
```
- n8n 실행 위치에 따라 실패 가능
- Docker 환경에서 특히 문제 발생

**✅ 절대 경로 (권장):**
```bash
cd /Users/vinyl/vinylstudio/n8n-test && poetry run python3 main.py
```

### 출력 디렉토리 확인

**기존 코드는 상대 경로 사용:**
```python
OUTPUT_DIR=./generated_stories  # .env 파일
```

**실제 저장 위치:**
```
/Users/vinyl/vinylstudio/n8n-test/generated_stories/
```

**n8n에서 파일 읽을 때:**
- Read Binary File 노드에서 절대 경로 사용
- 예: `/Users/vinyl/vinylstudio/n8n-test/generated_stories/horror_story_20260102_155854.md`

---

## 전체 워크플로 예시

### 예시 1: 기본 템플릿 사용

**워크플로 구조:**
```
[Manual Trigger]
    ↓
[Execute Command]
    ↓
[Code: 파일 경로 추출]
    ↓
[Read Binary File]
    ↓
[결과 확인]
```

**Execute Command 노드 설정:**
- Command: `cd /Users/vinyl/vinylstudio/n8n-test && poetry run python3 main.py`
- Execute Once: ✅
- Timeout: `180000`

**Expected Output:**
- stdout에 로그 및 파일 경로 포함
- exitCode: 0

---

### 예시 2: 템플릿 선택 워크플로

**워크플로 구조:**
```
[Manual Trigger]
    ↓
[Set: 템플릿 선택]
    ↓
[Execute Command]
    ↓
[Code: 파일 경로 추출]
    ↓
[Read Binary File]
    ↓
[결과 확인]
```

**Set 노드 설정 (템플릿 선택):**

"Add Value" 클릭 후:

| Name | Value |
|------|-------|
| `template_path` | `templates/horror_story_prompt_template.json` |

**또는 드롭다운 방식:**

| Name | Type | Value |
|------|------|-------|
| `template_path` | String | `templates/sample.json` |

**Execute Command 노드 설정:**

Command 입력란:
```bash
cd /Users/vinyl/vinylstudio/n8n-test && poetry run python3 -c "from horror_story_generator import generate_horror_story; generate_horror_story(template_path='{{ $json.template_path }}')"
```

**변수 설명:**
- `{{ $json.template_path }}`는 Set 노드에서 설정한 값 참조
- n8n이 자동으로 변수를 치환하여 실행

**실행 시 실제 명령:**
```bash
cd /Users/vinyl/vinylstudio/n8n-test && poetry run python3 -c "from horror_story_generator import generate_horror_story; generate_horror_story(template_path='templates/sample.json')"
```

---

### 예시 3: 여러 템플릿 중 선택 (Webhook 활용)

**워크플로 구조:**
```
[Webhook]
    ↓
[Switch: 템플릿 분기]
    ↓
[Execute Command (템플릿별)]
    ↓
[결과 처리]
```

**Webhook 입력 예시:**
```json
{
  "template_type": "psychological"
}
```

**Switch 노드 설정:**

| Output | Condition |
|--------|-----------|
| `default` | `{{ $json.template_type }}` equals `default` |
| `psychological` | `{{ $json.template_type }}` equals `psychological` |
| `short` | `{{ $json.template_type }}` equals `short` |

**각 분기별 Execute Command 설정:**

**default 분기:**
```bash
cd /Users/vinyl/vinylstudio/n8n-test && poetry run python3 -c "from horror_story_generator import generate_horror_story; generate_horror_story(template_path='templates/horror_story_prompt_template.json')"
```

**psychological 분기:**
```bash
cd /Users/vinyl/vinylstudio/n8n-test && poetry run python3 -c "from horror_story_generator import generate_horror_story; generate_horror_story(template_path='templates/horror_story_prompt_psychological.json')"
```

**short 분기:**
```bash
cd /Users/vinyl/vinylstudio/n8n-test && poetry run python3 -c "from horror_story_generator import generate_horror_story; generate_horror_story(template_path='templates/horror_story_prompt_short.json')"
```

**주의:**
- 템플릿 파일이 실제로 존재해야 함
- 존재하지 않는 파일 지정 시 `FileNotFoundError` 발생

---

## 문제 해결

### 1. "python: command not found"

**원인:** Python이 PATH에 없거나 잘못된 명령어

**해결:**
```bash
# Python 경로 확인
which python3

# Execute Command에서 절대 경로 사용
cd /Users/vinyl/vinylstudio/n8n-test && /usr/local/bin/python3 main.py
```

### 2. "poetry: command not found"

**원인:** Poetry가 설치되지 않았거나 PATH에 없음

**해결 방법 1: Poetry 절대 경로 사용**
```bash
# Poetry 경로 확인
which poetry

# 예시
cd /Users/vinyl/vinylstudio/n8n-test && /Users/vinyl/.local/bin/poetry run python3 main.py
```

**해결 방법 2: 가상환경 직접 활성화**
```bash
cd /Users/vinyl/vinylstudio/n8n-test && source .venv/bin/activate && python main.py
```

### 3. "No module named 'anthropic'"

**원인:** 가상환경이 활성화되지 않았거나 의존성 미설치

**해결:**
```bash
# 의존성 설치 확인
cd /Users/vinyl/vinylstudio/n8n-test
poetry install

# n8n에서는 반드시 poetry run 사용
cd /Users/vinyl/vinylstudio/n8n-test && poetry run python3 main.py
```

### 4. "API key not found"

**원인:** .env 파일을 찾지 못하거나 환경 변수 미설정

**확인:**
```bash
# .env 파일 존재 여부
ls -la /Users/vinyl/vinylstudio/n8n-test/.env

# .env 파일 내용 확인
cat /Users/vinyl/vinylstudio/n8n-test/.env | grep ANTHROPIC_API_KEY
```

**해결:**
- .env 파일이 프로젝트 루트에 있는지 확인
- ANTHROPIC_API_KEY가 올바르게 설정되었는지 확인

### 5. Timeout 발생

**원인:** Claude API 호출 시간 초과

**해결:**
```
Timeout 값을 더 크게 설정
예: 300000 (5분)
```

### 6. "Permission denied"

**원인:** 파일 권한 문제

**해결:**
```bash
# Python 파일 실행 권한 확인
ls -la /Users/vinyl/vinylstudio/n8n-test/main.py

# 필요시 권한 추가
chmod +x /Users/vinyl/vinylstudio/n8n-test/main.py
```

---

## Docker 환경 추가 고려사항

### n8n을 Docker로 실행하는 경우

**문제:** Docker 컨테이너 내부에는 Python이 없을 수 있음

**해결 방법 1: 볼륨 마운트 + 호스트 명령 실행**

Docker에서 호스트 명령 실행은 복잡하므로 권장하지 않음

**해결 방법 2: Custom Docker 이미지**

```dockerfile
FROM n8nio/n8n:latest

# Python 및 Poetry 설치
RUN apk add --no-cache python3 py3-pip
RUN pip3 install poetry

# 프로젝트 복사
COPY . /app/horror-story-generator
WORKDIR /app/horror-story-generator

# 의존성 설치
RUN poetry install
```

**해결 방법 3: 볼륨 마운트로 templates 디렉토리 공유**

```bash
docker run -it --rm \
  --name n8n \
  -p 5678:5678 \
  -v /Users/vinyl/vinylstudio/n8n-test:/data/horror-story-generator \
  n8nio/n8n
```

**주의사항:**
- `templates/` 디렉토리가 컨테이너 내부에서도 접근 가능해야 함
- Execute Command에서 마운트된 경로 사용
- 예: `/data/horror-story-generator/templates/sample.json`

**해결 방법 4: HTTP API 사용 (권장)**

Docker 환경에서는 Execute Command보다 HTTP API 방식 권장 (Task 7 참고)

---

## 체크리스트

작업 전 확인 사항:

- [ ] Python 3.14 이상 설치 확인
- [ ] Poetry 설치 및 의존성 설치 완료
- [ ] .env 파일에 ANTHROPIC_API_KEY 설정
- [ ] `templates/` 디렉토리 존재 및 템플릿 파일 확인
- [ ] 사용할 템플릿 파일 경로 확인 (예: `templates/horror_story_prompt_template.json`)
- [ ] 수동 실행 테스트 성공 (`poetry run python3 main.py`)
- [ ] 특정 템플릿 사용 시 수동 테스트 성공
  ```bash
  poetry run python3 -c "from horror_story_generator import generate_horror_story; generate_horror_story(template_path='templates/sample.json')"
  ```
- [ ] 프로젝트 절대 경로 확인
- [ ] n8n Execute Command 노드에서 절대 경로 사용
- [ ] Timeout 180000 이상 설정
- [ ] 출력 디렉토리 쓰기 권한 확인

---

## 다음 단계

Execute Command로 기본 실행이 성공했다면:

1. **Task 2**: 출력 완결성 검증 및 에러 처리 추가
2. **Task 3**: 완전한 워크플로 템플릿 적용
3. **Task 4**: 환경 설정 및 보안 강화

---

## 요약

**이 가이드에서 다룬 내용:**
- ✅ Execute Command 노드 기본 설정
- ✅ Python/Poetry 환경 활성화 방법
- ✅ 환경 변수 설정 (.env 파일)
- ✅ stdout/stderr 처리
- ✅ 절대 경로 vs 상대 경로
- ✅ 일반적인 문제 해결 방법

**이 가이드에서 다루지 않은 내용:**
- ❌ Python 코드 수정
- ❌ 프롬프트 변경
- ❌ 출력 검증 로직 (Task 2에서 다룸)
- ❌ 고급 워크플로 (배치, 스케줄링 등)
