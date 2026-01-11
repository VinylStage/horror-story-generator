# n8n 워크플로 Import 및 사용 가이드

## 개요

이 문서는 제공된 n8n 워크플로 템플릿을 import하고 사용하는 방법을 설명합니다.

**제공되는 워크플로:**
1. `01_basic_generation.json` - 기본 소설 생성 (단순 실행)
2. `02_template_selection.json` - 템플릿 선택 생성 (템플릿 변수 활용 + 검증)

---

## 워크플로 Import 방법

### 1. n8n 접속

```bash
# 로컬 n8n 실행 (이미 실행 중이면 스킵)
npx n8n

# 브라우저에서 접속
http://localhost:5678
```

### 2. 워크플로 Import

**방법 1: 파일에서 Import**

1. n8n 좌측 메뉴에서 **"Workflows"** 클릭
2. 우측 상단 **"Add workflow"** 드롭다운 클릭
3. **"Import from file..."** 선택
4. 파일 선택:
   - `n8n_workflows/01_basic_generation.json`
   - 또는 `n8n_workflows/02_template_selection.json`
5. **"Import"** 클릭

**방법 2: JSON 복사 붙여넣기**

1. 워크플로 JSON 파일을 텍스트 에디터로 열기
2. 전체 내용 복사 (Cmd+A, Cmd+C)
3. n8n에서 **"Add workflow"** → **"Import from URL or Text"**
4. JSON 내용 붙여넣기
5. **"Import"** 클릭

---

## 워크플로 1: Basic Generation

### 개요

가장 간단한 형태의 워크플로입니다.
- Manual Trigger로 수동 실행
- 기본 템플릿 사용 (`main.py` 실행)
- 파일 경로 추출 및 결과 확인

### 노드 구성

```
[Manual Trigger]
    ↓
[Execute: Generate Story]
    ↓
[Extract File Paths]
    ↓
[Read: Markdown File] + [Read: Metadata JSON]
    ↓
[Parse Results]
```

### 필수 수정 사항

워크플로를 import한 후 **반드시 수정해야 할 부분**:

#### 1. Execute Command 노드

**노드 이름:** `Execute: Generate Story`

**수정 항목:** Command 경로

**기본값:**
```bash
cd /Users/vinyl/vinylstudio/n8n-test && poetry run python3 main.py
```

**수정 방법:**
1. 노드 더블클릭
2. Command 필드에서 `/Users/vinyl/vinylstudio/n8n-test`를 **실제 프로젝트 경로**로 변경
3. 예: `cd /home/user/projects/horror-generator && poetry run python3 main.py`

#### 2. Extract File Paths 노드 (Code)

**수정 항목:** 절대 경로 prefix

**코드 내 수정 위치:**
```javascript
const absoluteMdPath = mdPath.startsWith('/') ? mdPath : `/Users/vinyl/vinylstudio/n8n-test/${mdPath}`;
```

**수정 방법:**
1. 노드 더블클릭
2. `/Users/vinyl/vinylstudio/n8n-test`를 **실제 프로젝트 경로**로 변경
3. Save

### 실행 방법

1. 워크플로 우측 상단 **"Execute workflow"** 클릭
2. 또는 Manual Trigger 노드의 **"Execute node"** 클릭
3. 각 노드 실행 결과 확인 (녹색 체크 표시)
4. 마지막 노드 클릭하여 결과 확인

### 예상 결과

**Parse Results 노드 출력:**
```json
{
  "markdown_content": "---\ntitle: \"소설 제목\"\n...",
  "full_markdown_length": 7996,
  "metadata": {
    "title": "백색 병동",
    "word_count": 7996,
    "usage": {
      "input_tokens": 1219,
      "output_tokens": 8192
    }
  },
  "generation_success": true
}
```

---

## 워크플로 2: Template Selection

### 개요

템플릿을 선택하여 실행하는 워크플로입니다.
- Set 노드에서 템플릿 선택
- 기본 완결성 검증 포함
- 실무 사용에 적합

### 노드 구성

```
[Manual Trigger]
    ↓
[Set: Template Selection]  ← 여기서 템플릿 선택
    ↓
[Execute: Generate with Template]
    ↓
[Extract File Paths]
    ↓
[Read: Metadata JSON]
    ↓
[Validate Output]  ← 완결성 검증
```

### 필수 수정 사항

#### 1. Execute Command 노드

**노드 이름:** `Execute: Generate with Template`

**수정 항목:** Command 경로

**기본값:**
```bash
cd /Users/vinyl/vinylstudio/n8n-test && poetry run python3 -c "from horror_story_generator import generate_horror_story; generate_horror_story(template_path='{{ $json.template_path }}')"
```

**수정 방법:**
1. `/Users/vinyl/vinylstudio/n8n-test`를 **실제 프로젝트 경로**로 변경
2. `{{ $json.template_path }}`는 그대로 유지 (n8n 변수)

#### 2. Extract File Paths 노드

워크플로 1과 동일하게 절대 경로 수정

#### 3. Set: Template Selection 노드 (템플릿 선택)

**여기서 사용할 템플릿을 선택합니다.**

**기본값:**
```json
{
  "template_path": "templates/horror_story_prompt_template.json"
}
```

**변경 방법:**
1. 노드 더블클릭
2. `template_path` 값 변경:
   - `templates/horror_story_prompt_template.json` (기본)
   - `templates/sample.json`
   - `templates/horror_story_prompt_short.json` (짧은 버전)
   - `templates/horror_story_prompt_psychological.json` (심리 호러)
3. Save

**주의:** 템플릿 파일이 실제로 존재해야 합니다.

### 템플릿 선택 예시

**심리 호러 생성:**
```json
{
  "template_path": "templates/horror_story_prompt_psychological.json"
}
```

**짧은 소설 생성:**
```json
{
  "template_path": "templates/horror_story_prompt_short.json"
}
```

### 검증 로직

**Validate Output 노드**에서 기본 검증 수행:

- `word_count >= 1000`: 최소 분량 확인
- `output_tokens < 8192`: 토큰 한계 도달 여부
- `is_complete`: 검증 통과 여부

**검증 결과 예시:**
```json
{
  "template_used": "templates/horror_story_prompt_template.json",
  "title": "백색 병동",
  "word_count": 7996,
  "output_tokens": 8192,
  "is_complete": true,
  "validation_message": "Generation successful"
}
```

**검증 실패 시:**
```json
{
  "is_complete": false,
  "validation_message": "Output may be incomplete"
}
```

---

## 워크플로 수정 가이드

### 템플릿을 하드코딩이 아닌 입력으로 받기

**Webhook Trigger 사용:**

1. Manual Trigger 노드 삭제
2. Webhook 노드 추가
3. HTTP Method: POST
4. Path: `/generate-story`
5. Set 노드에서 Webhook 입력 받기:

```json
{
  "template_path": "={{ $json.body.template_path }}"
}
```

**Webhook 호출 예시:**
```bash
curl -X POST http://localhost:5678/webhook/generate-story \
  -H "Content-Type: application/json" \
  -d '{"template_path": "templates/sample.json"}'
```

### 알림 추가

**Validate Output 노드 뒤에 추가:**

1. **Slack 노드** 또는 **Email 노드** 추가
2. If 노드로 분기:
   - TRUE (성공) → Slack "생성 완료" 메시지
   - FALSE (실패) → Slack "생성 실패" 알림

---

## 문제 해결

### Import 실패

**증상:** "Invalid workflow format" 오류

**해결:**
1. JSON 파일이 유효한지 확인 (JSONLint.com 등)
2. 파일 인코딩이 UTF-8인지 확인
3. 파일 전체를 복사했는지 확인 (중괄호 `{}`가 완전한지)

### Execute Command 실패

**증상:** "Command not found" 또는 "Permission denied"

**확인 사항:**
1. 프로젝트 경로가 올바른지 확인
2. Poetry가 설치되어 있는지 확인 (`which poetry`)
3. 수동 실행 테스트:
   ```bash
   cd /your/project/path
   poetry run python3 main.py
   ```

### 파일 경로 추출 실패

**증상:** "파일 경로를 찾을 수 없습니다" 에러

**원인:** stdout 포맷이 예상과 다름

**해결:**
1. Execute Command 노드 출력 확인
2. stdout에 "저장 위치:"가 포함되어 있는지 확인
3. Extract File Paths 노드의 정규식 수정 필요시:
   ```javascript
   const mdPathMatch = stdout.match(/저장 위치: (.+\.md)/);
   ```

### 템플릿 파일 없음

**증상:** "FileNotFoundError: 프롬프트 템플릿 파일을 찾을 수 없습니다"

**해결:**
1. `templates/` 디렉토리 존재 확인
2. 템플릿 파일 존재 확인:
   ```bash
   ls -la /your/project/path/templates/
   ```
3. Set 노드의 `template_path` 값이 정확한지 확인

---

## 다음 단계

### 워크플로 확장

기본 워크플로를 기반으로 다음을 추가할 수 있습니다:

1. **Task 2 문서 참고:** 완결성 검증 및 재시도 로직
2. **Task 5 (권장):** 블로그 자동 업로드, 클라우드 저장
3. **Task 6 (권장):** 배치 생성, 스케줄링

### 권장 실습 순서

1. ✅ 워크플로 1 (Basic) import 및 실행
2. ✅ 경로 수정 후 정상 동작 확인
3. ✅ 워크플로 2 (Template Selection) import
4. ✅ 다양한 템플릿으로 테스트
5. ⏭️ Task 2 문서 참고하여 검증 로직 강화

---

## 요약

**이 가이드에서 다룬 내용:**
- ✅ 워크플로 Import 방법 (파일 / JSON)
- ✅ 워크플로 1: 기본 생성 (단순 실행)
- ✅ 워크플로 2: 템플릿 선택 (변수 활용 + 검증)
- ✅ 필수 수정 사항 (경로 변경)
- ✅ 템플릿 선택 방법
- ✅ 문제 해결 가이드

**제공된 워크플로 특징:**
- ✅ 최소 동작 예제 (단순 구조)
- ✅ 고급 분기/배치 로직 없음 (Task 5, 6에서 다룸)
- ✅ 실패 시 중단 (재시도 로직은 Task 2 참고)
- ✅ 템플릿을 변수로 처리 가능
- ✅ 기본 검증 포함 (워크플로 2)

**다루지 않은 내용:**
- ❌ 재시도 로직 (Task 2 참고)
- ❌ 배치 생성 (Task 6 참고)
- ❌ 블로그 업로드 (Task 5 참고)
- ❌ 스케줄링 (Task 6 참고)
