# n8n 출력 완결성 검증 및 에러 처리 워크플로 패턴

## 개요

이 문서는 n8n 워크플로에서 **호러 소설 생성 결과의 완결성을 검증**하고, 문제 발생 시 대응하는 방법을 설명합니다.

**핵심 원칙:**
- 기존 Python 코드나 프롬프트는 수정하지 않음
- n8n 워크플로 레벨에서 출력을 검증
- 비정상 출력 감지 시 재시도/실패 처리 패턴 제공

**배경:**
- Claude API는 출력 제약(토큰 제한, 종료 조건)으로 인해 가끔 불완전한 출력을 생성할 수 있음
- 이는 모델 결함이 아니라 정상적인 동작 범위
- n8n에서는 출력을 검증하여 완결성을 확인하고, 필요시 재처리

---

## 출력 완결성 이슈 이해

### 발생 가능한 문제

1. **Markdown 문법 중단**
   - 마지막 문장이 중간에 끊김
   - 코드 블록, 리스트 등이 닫히지 않음

2. **문서 비정상 종료**
   - 소설이 완결되지 않고 중간에 끝남
   - 예: 3막 구조 중 2막까지만 생성

3. **출력 길이 부족**
   - 템플릿의 목표 분량(예: 3000자)에 미달
   - metadata.word_count가 예상보다 현저히 작음

### 템플릿별 차이점

**중요:** 각 템플릿은 다른 출력 특성을 가질 수 있습니다.

| 템플릿 | 예상 분량 | 구조 |
|--------|----------|------|
| `horror_story_prompt_template.json` | 3000자+ | 3-5장 구조 |
| `horror_story_prompt_short.json` | 1500자+ | 단편 |
| `horror_story_prompt_psychological.json` | 4000자+ | 심리 묘사 집중 |

**검증 전략:**
- 템플릿별 절대값 비교는 피함
- 상대적 패턴 검증 (예: 마크다운 닫힘 태그, 문장 완결성)
- metadata 활용 (word_count, usage 등)

---

## 검증 패턴 1: metadata 기반 검증

### 검증 가능한 metadata

Execute Command 실행 후 생성된 메타데이터 JSON:

```json
{
  "generated_at": "2026-01-02T16:03:39.877692",
  "model": "claude-sonnet-4-5-20250929",
  "template_used": "horror_story_prompt_template.json",
  "word_count": 7996,
  "usage": {
    "input_tokens": 1219,
    "output_tokens": 8192,
    "total_tokens": 9411
  },
  "title": "백색 병동",
  "tags": ["호러", "horror", ...],
  "description": ""
}
```

### n8n 워크플로: metadata 읽기

**노드 구성:**
```
[Execute Command]
    ↓
[Code: 파일 경로 추출]
    ↓
[Read Binary File: Metadata JSON]
    ↓
[Code: Metadata 파싱]
    ↓
[If: 완결성 검증]
```

**Code 노드 (Metadata 파싱):**

```javascript
// 메타데이터 JSON 파일 읽기 결과 파싱
const metadataContent = $input.item.binary.data;
const metadataText = Buffer.from(metadataContent, 'base64').toString('utf-8');
const metadata = JSON.parse(metadataText);

return {
  json: {
    word_count: metadata.word_count,
    output_tokens: metadata.usage.output_tokens,
    title: metadata.title,
    template_used: metadata.template_used
  }
};
```

### If 노드: 완결성 검증 조건

**검증 1: 최소 분량 확인**

```javascript
{{ $json.word_count }} >= 1000
```
- 1000자는 예시 (템플릿별로 조정 가능)
- 너무 짧은 출력은 비정상으로 간주

**검증 2: 출력 토큰 한계 도달 여부**

```javascript
{{ $json.output_tokens }} < 8192
```
- 8192는 MAX_TOKENS 설정값
- output_tokens가 max_tokens와 같으면 중간에 잘렸을 가능성

**검증 3: 제목 추출 여부**

```javascript
{{ $json.title }} !== "무제"
```
- 제목이 "무제"면 추출 실패 = 비정상 포맷일 가능성

**종합 조건 (AND):**

```javascript
{{ $json.word_count >= 1000 && $json.output_tokens < 8192 && $json.title !== "무제" }}
```

---

## 검증 패턴 2: Markdown 구조 검증

### 마크다운 파일 끝부분 패턴 확인

**노드 구성:**
```
[Read Binary File: Markdown]
    ↓
[Code: 마크다운 검증]
    ↓
[If: 구조 완결성]
```

**Code 노드 (마크다운 검증):**

```javascript
// 마크다운 파일 내용
const markdownContent = $input.item.binary.data;
const markdownText = Buffer.from(markdownContent, 'base64').toString('utf-8');

// 검증 1: 파일이 정상적으로 끝나는지 (마지막 줄이 공백이 아님)
const lines = markdownText.trim().split('\n');
const lastLine = lines[lines.length - 1].trim();
const hasProperEnding = lastLine.length > 0;

// 검증 2: 마지막 줄이 문장으로 끝나는지 (마침표, 물음표, 느낌표)
const endsWithPunctuation = /[.!?。！？]$/.test(lastLine);

// 검증 3: 열린 마크다운 구문이 닫혔는지 (코드 블록)
const codeBlockCount = (markdownText.match(/```/g) || []).length;
const codeBlocksClosed = codeBlockCount % 2 === 0;

// 검증 4: YAML frontmatter 존재
const hasFrontmatter = markdownText.startsWith('---');

return {
  json: {
    has_proper_ending: hasProperEnding,
    ends_with_punctuation: endsWithPunctuation,
    code_blocks_closed: codeBlocksClosed,
    has_frontmatter: hasFrontmatter,
    markdown_valid: hasProperEnding && endsWithPunctuation && codeBlocksClosed && hasFrontmatter
  }
};
```

**If 노드 조건:**

```javascript
{{ $json.markdown_valid === true }}
```

---

## 검증 패턴 3: YAML Frontmatter 파싱

### frontmatter 유효성 확인

**Code 노드 (YAML 파싱):**

```javascript
const markdownContent = $input.item.binary.data;
const markdownText = Buffer.from(markdownContent, 'base64').toString('utf-8');

// frontmatter 추출
const frontmatterMatch = markdownText.match(/^---\n([\s\S]+?)\n---/);

if (!frontmatterMatch) {
  return {
    json: {
      frontmatter_valid: false,
      error: 'Frontmatter not found'
    }
  };
}

const frontmatterText = frontmatterMatch[1];

// 필수 필드 확인 (정규식으로 간단히 체크)
const hasTitle = /title:\s*".+"/.test(frontmatterText);
const hasDate = /date:\s*\d{4}-\d{2}-\d{2}/.test(frontmatterText);
const hasTags = /tags:\s*\[.+\]/.test(frontmatterText);
const hasGenre = /genre:\s*"호러"/.test(frontmatterText);

const frontmatterValid = hasTitle && hasDate && hasTags && hasGenre;

return {
  json: {
    frontmatter_valid: frontmatterValid,
    has_title: hasTitle,
    has_date: hasDate,
    has_tags: hasTags,
    has_genre: hasGenre
  }
};
```

---

## n8n 워크플로 분기 패턴

### 기본 분기 구조

```
[검증 노드들]
    ↓
[If: 모든 검증 통과?]
    ├─ TRUE → [정상 처리 경로]
    │           ↓
    │         [블로그 업로드 / 저장 등]
    │
    └─ FALSE → [비정상 처리 경로]
                ↓
              [재시도 또는 실패 처리]
```

### If 노드 종합 조건

**모든 검증을 통과한 경우만 TRUE:**

```javascript
{{
  $json.word_count >= 1000 &&
  $json.output_tokens < 8192 &&
  $json.markdown_valid === true &&
  $json.frontmatter_valid === true
}}
```

---

## 재시도 로직 워크플로

### 패턴 1: Loop 노드 활용

**워크플로 구조:**
```
[Manual Trigger]
    ↓
[Set: 재시도 설정]
    ↓
[Loop Node] ─┐
    ↓        │
[Execute Command]
    ↓        │
[검증 노드들]  │
    ↓        │
[If: 성공?] ─┤
    ├─ TRUE → [Loop 종료]
    └─ FALSE → [다시 Loop] (최대 3회)
```

**Set 노드 (재시도 설정):**

| Name | Value |
|------|-------|
| `max_retries` | `3` |
| `current_retry` | `0` |
| `template_path` | `templates/horror_story_prompt_template.json` |

**Loop 노드 설정:**
- Max Iterations: `3`
- Mode: `Run Once for All Items`

**If 노드 (Loop 종료 조건):**

```javascript
{{ $json.markdown_valid === true || $("Set").item.json.current_retry >= 3 }}
```

### 패턴 2: 재시도 시 파라미터 조정 (선택사항)

**주의:** 이는 예시이며, 실제 프롬프트 품질 개선은 이 레포 범위 밖입니다.

**Code 노드 (재시도 횟수별 설정):**

```javascript
const retry = $("Set").item.json.current_retry;

// 재시도 횟수에 따라 다른 전략 (예시)
let strategy = {};

if (retry === 0) {
  // 첫 시도: 기본 설정
  strategy = {
    template_path: 'templates/horror_story_prompt_template.json'
  };
} else if (retry === 1) {
  // 2번째 시도: 다른 템플릿 시도 (더 짧은 버전)
  strategy = {
    template_path: 'templates/horror_story_prompt_short.json'
  };
} else {
  // 3번째 시도: 마지막 시도
  strategy = {
    template_path: 'templates/horror_story_prompt_template.json'
  };
}

return {
  json: {
    ...strategy,
    retry_count: retry + 1
  }
};
```

**Execute Command (동적 템플릿):**

```bash
cd /Users/vinyl/vinylstudio/n8n-test && poetry run python3 -c "from horror_story_generator import generate_horror_story; generate_horror_story(template_path='{{ $json.template_path }}')"
```

---

## 실패 처리 워크플로

### 최종 실패 시 알림

**워크플로 구조:**
```
[If: 최종 실패?]
    ↓
[Send Email / Slack]
    ↓
[로그 파일 수집]
    ↓
[실패 기록 저장]
```

### Email 알림 (Gmail 노드)

**Subject:**
```
[n8n] 호러 소설 생성 실패 - {{ $now }}
```

**Body:**
```
호러 소설 생성이 {{ $json.retry_count }}회 시도 후 실패했습니다.

템플릿: {{ $json.template_path }}
마지막 word_count: {{ $json.word_count }}
Output tokens: {{ $json.output_tokens }}

검증 결과:
- Markdown 유효성: {{ $json.markdown_valid }}
- Frontmatter 유효성: {{ $json.frontmatter_valid }}

로그 파일 경로:
{{ $json.log_file_path }}
```

### Slack 알림 (Slack 노드)

**Channel:** `#n8n-alerts`

**Message:**
```json
{
  "text": "호러 소설 생성 실패",
  "blocks": [
    {
      "type": "section",
      "text": {
        "type": "mrkdwn",
        "text": "*호러 소설 생성 실패*\n템플릿: `{{ $json.template_path }}`\n재시도 횟수: {{ $json.retry_count }}"
      }
    },
    {
      "type": "section",
      "fields": [
        {
          "type": "mrkdwn",
          "text": "*Word Count:*\n{{ $json.word_count }}"
        },
        {
          "type": "mrkdwn",
          "text": "*Output Tokens:*\n{{ $json.output_tokens }}"
        }
      ]
    }
  ]
}
```

### 로그 파일 자동 수집

**Read Binary File 노드:**

File Path:
```
{{ $json.log_file_path }}
```
- Execute Command 실행 시 로그 파일 경로를 추출하여 저장
- 예: `/Users/vinyl/vinylstudio/n8n-test/logs/horror_story_20260102_155606.log`

**Email 첨부:**
- Binary Property: `data`
- File Name: `{{ $json.log_file_name }}`

### 실패 파라미터 저장 (Google Sheets)

**Append 노드 설정:**

| Column | Value |
|--------|-------|
| Timestamp | `{{ $now }}` |
| Template | `{{ $json.template_path }}` |
| Retry Count | `{{ $json.retry_count }}` |
| Word Count | `{{ $json.word_count }}` |
| Output Tokens | `{{ $json.output_tokens }}` |
| Markdown Valid | `{{ $json.markdown_valid }}` |
| Frontmatter Valid | `{{ $json.frontmatter_valid }}` |
| Status | `FAILED` |

---

## [참고용] 프롬프트 레벨 완결성 강제 예시

**주의:**
- 이 섹션은 참고용 가이드입니다
- 실제 프롬프트 수정은 사용자의 재량입니다
- 이 레포지토리는 프롬프트 개선을 다루지 않습니다

### 템플릿에 추가 가능한 완결성 지시 예시

기존 `templates/horror_story_prompt_template.json`의 `additional_requirements` 섹션에 추가할 수 있는 예시:

```json
{
  "additional_requirements": {
    "word_count": 3000,
    "chapter_structure": "단편 형식 또는 3-5개 챕터",

    "completion_constraints": {
      "enforce_ending": true,
      "ending_instruction": "반드시 이야기를 완결된 형태로 종료하고, 마지막 문장은 마침표로 끝낼 것",
      "structure_completion": "모든 시작된 챕터, 코드 블록, 리스트는 반드시 닫을 것",
      "minimum_length_enforcement": "3000자 미만으로 끝나지 않도록 주의"
    }
  }
}
```

**build_system_prompt() 함수에서 활용 방법:**

현재 코드는 이미 `additional_requirements`를 읽습니다:

```python
requirements = template.get("additional_requirements", {})
if requirements:
    system_prompt += "\n## 추가 요구사항\n"
    system_prompt += f"- 목표 분량: {requirements.get('word_count', 3000)}자\n"
    # ... 기타 필드 처리
```

위 JSON을 추가하면 자동으로 시스템 프롬프트에 포함됩니다.

**프롬프트 문구 예시:**

```
## 완결성 제약사항
- 이야기는 반드시 완결된 형태로 종료하세요
- 마지막 문장은 반드시 마침표(.)로 끝나야 합니다
- 시작한 모든 마크다운 구문(코드 블록, 리스트 등)은 반드시 닫으세요
- 3000자 미만으로 끝나지 않도록 충분한 내용을 작성하세요
```

**효과:**
- Claude가 출력 종료 시 완결성을 더 고려
- 하지만 토큰 제한은 여전히 존재하므로 100% 보장은 불가능
- n8n 워크플로 검증과 병행 권장

---

## 템플릿별 검증 기준 설정

### 검증 기준을 템플릿에 따라 조정

**Set 노드 (템플릿별 기준):**

```javascript
const template = $json.template_path;

let validation = {};

if (template.includes('short')) {
  // 짧은 템플릿
  validation = {
    min_word_count: 1000,
    expected_structure: 'single_chapter'
  };
} else if (template.includes('psychological')) {
  // 심리 호러 템플릿
  validation = {
    min_word_count: 3500,
    expected_structure: 'multi_chapter'
  };
} else {
  // 기본 템플릿
  validation = {
    min_word_count: 2500,
    expected_structure: 'standard'
  };
}

return { json: validation };
```

**If 노드 (동적 기준 적용):**

```javascript
{{ $json.word_count >= $("Set Validation Criteria").item.json.min_word_count }}
```

---

## 전체 워크플로 예시: 완결성 검증 + 재시도

```
[Manual Trigger]
    ↓
[Set: 템플릿 및 재시도 설정]
    ↓
[Loop: 최대 3회] ─────┐
    ↓                  │
[Set: 템플릿별 검증 기준]  │
    ↓                  │
[Execute Command]      │
    ↓                  │
[Code: 파일 경로 추출]    │
    ↓                  │
[Read: Metadata JSON]  │
    ↓                  │
[Read: Markdown]       │
    ↓                  │
[Code: Metadata 검증]   │
    ↓                  │
[Code: Markdown 검증]   │
    ↓                  │
[If: 모든 검증 통과?]    │
    ├─ TRUE → [Loop 종료] → [정상 처리]
    │                           ↓
    │                     [블로그 업로드]
    │
    └─ FALSE ─────────────┘
         (재시도)

[If: 최종 실패?]
    ↓
[Slack 알림]
    ↓
[Email 알림 + 로그 첨부]
    ↓
[실패 기록 저장 (Sheets)]
```

---

## 요약

**이 가이드에서 다룬 내용:**
- ✅ metadata 기반 완결성 검증 (word_count, output_tokens)
- ✅ Markdown 구조 검증 (문장 끝, 코드 블록 닫힘)
- ✅ YAML frontmatter 유효성 검증
- ✅ n8n If 노드를 통한 워크플로 분기
- ✅ Loop 노드를 활용한 재시도 로직
- ✅ Slack/Email 알림 및 로그 수집
- ✅ 템플릿별 검증 기준 동적 조정
- ✅ [참고용] 프롬프트 레벨 완결성 제약 예시

**이 가이드에서 다루지 않은 내용:**
- ❌ Claude 모델 자체 개선
- ❌ 프롬프트 품질 향상 작업
- ❌ 콘텐츠 생성 로직 수정
- ❌ 새로운 검증 알고리즘 개발 (기존 메타데이터만 활용)

**범위 준수:**
- 기존 Python 코드 변경 없음
- n8n 워크플로 레벨에서만 검증 수행
- 프롬프트 개선은 선택적 참고용 예시만 제공
