# 호러 소설 생성기

Claude API (Sonnet 4.5)를 활용한 한국어 호러 소설 자동 생성 시스템입니다.

## 특징

- **함수형 설계**: 각 기능이 독립적인 함수로 구현되어 확장 및 재사용이 쉽습니다
- **JSON 기반 프롬프트**: 소설의 모든 요소를 JSON 포맷으로 관리하여 커스터마이즈가 용이합니다
- **자동 저장**: 생성된 소설과 메타데이터를 자동으로 파일로 저장합니다
- **한국어 최적화**: 한국적 정서와 호러 요소를 반영한 프롬프트 설계

## 설치 방법

### 1. 의존성 설치

```bash
pip install -r requirements.txt
```

또는 Poetry 사용 시:

```bash
poetry install
```

### 2. 환경 변수 설정

`.env` 파일에 Anthropic API 키가 이미 설정되어 있습니다.

```env
ANTHROPIC_API_KEY=your_key_here
CLAUDE_MODEL=claude-sonnet-4.5-20250929
OUTPUT_DIR=./generated_stories
MAX_TOKENS=8192
TEMPERATURE=0.8
```

## 사용 방법

### 기본 실행

```bash
python horror_story_generator.py
```

### 프로그래밍 방식 사용

```python
from horror_story_generator import generate_horror_story

# 기본 실행
result = generate_horror_story()
print(result["story"])

# 커스텀 요청으로 실행
result = generate_horror_story(
    custom_request="1980년대 한국의 시골 마을을 배경으로 한 귀신 이야기를 써주세요."
)

# 파일 저장 없이 실행
result = generate_horror_story(save_output=False)
```

### 템플릿 커스터마이즈

```python
from horror_story_generator import customize_template, generate_horror_story
import json

# 템플릿 커스터마이즈
custom_template = customize_template(
    genre="cosmic_horror",
    location="deep_sea_research_station",
    atmosphere="claustrophobic_dread"
)

# 커스터마이즈된 템플릿을 파일로 저장
with open("custom_template.json", "w", encoding="utf-8") as f:
    json.dump(custom_template, f, ensure_ascii=False, indent=2)

# 커스텀 템플릿으로 소설 생성
result = generate_horror_story(
    template_path="custom_template.json",
    custom_request="우주적 공포를 다룬 심해 연구소 이야기"
)
```

### 고급 사용: 개별 함수 활용

```python
from horror_story_generator import (
    load_environment,
    load_prompt_template,
    build_system_prompt,
    build_user_prompt,
    call_claude_api,
    save_story
)

# 1. 환경 설정 로드
config = load_environment()

# 2. 템플릿 로드
template = load_prompt_template("horror_story_prompt_template.json")

# 3. 템플릿 수정 (원하는 대로)
template["story_config"]["genre"] = "gothic_horror"
template["story_elements"]["setting"]["location"] = "abandoned_castle"

# 4. 프롬프트 생성
system_prompt = build_system_prompt(template)
user_prompt = build_user_prompt("중세 성을 배경으로 한 고딕 호러", template)

# 5. API 호출
story = call_claude_api(system_prompt, user_prompt, config)

# 6. 저장
file_path = save_story(story, config["output_dir"], {"genre": "gothic_horror"})
print(f"저장됨: {file_path}")
```

## 프롬프트 템플릿 구조

`horror_story_prompt_template.json` 파일은 다음과 같은 구조로 이루어져 있습니다:

```json
{
  "story_config": {
    "genre": "호러 장르 (예: psychological_horror, supernatural_horror)",
    "atmosphere": "분위기 (예: dark_unsettling, oppressive)",
    "length": "분량 (예: short, medium, long)",
    "target_audience": "대상 독자 (예: adult, young_adult)"
  },
  "story_elements": {
    "setting": {
      "location": "장소",
      "time_period": "시대",
      "weather": "날씨/환경",
      "atmosphere_details": "분위기 디테일"
    },
    "characters": {
      "protagonist": "주인공 정보",
      "antagonist": "적대자 정보"
    },
    "plot_structure": {
      "act_1": "1막 구조",
      "act_2": "2막 구조",
      "act_3": "3막 구조"
    },
    "horror_techniques": {
      "primary_fear_type": "주요 공포 유형",
      "scare_tactics": "공포 전술",
      "suspense_building": "긴장감 조성 방법"
    }
  },
  "writing_style": {
    "narrative_perspective": "시점",
    "tense": "시제",
    "tone": "톤",
    "language_style": "언어 스타일"
  },
  "additional_requirements": {
    "word_count": "목표 분량",
    "chapter_structure": "챕터 구조",
    "avoid": "피해야 할 요소",
    "emphasize": "강조할 요소"
  }
}
```

## 출력 파일

생성된 소설은 `generated_stories/` 디렉토리에 저장됩니다:

- `horror_story_YYYYMMDD_HHMMSS.txt`: 생성된 소설 본문
- `horror_story_YYYYMMDD_HHMMSS_metadata.json`: 생성 메타데이터

## 함수 레퍼런스

### 주요 함수

#### `generate_horror_story(template_path, custom_request, save_output)`
전체 파이프라인을 실행하여 호러 소설을 생성합니다.

**Parameters:**
- `template_path` (str): 프롬프트 템플릿 파일 경로 (기본값: "horror_story_prompt_template.json")
- `custom_request` (str, optional): 사용자 커스텀 요청사항
- `save_output` (bool): 결과를 파일로 저장할지 여부 (기본값: True)

**Returns:**
- `dict`: 생성된 소설, 메타데이터, 파일 경로를 포함한 딕셔너리

#### `customize_template(template_path, **kwargs)`
템플릿의 특정 값을 커스터마이즈합니다.

**Parameters:**
- `template_path` (str): 원본 템플릿 경로
- `**kwargs`: 수정할 필드와 값

**Returns:**
- `dict`: 커스터마이즈된 템플릿

#### `call_claude_api(system_prompt, user_prompt, config)`
Claude API를 호출합니다.

**Parameters:**
- `system_prompt` (str): 시스템 프롬프트
- `user_prompt` (str): 사용자 프롬프트
- `config` (dict): API 설정 정보

**Returns:**
- `str`: 생성된 텍스트

## 확장 예시

### 1. 배치 생성

```python
from horror_story_generator import generate_horror_story

themes = [
    "유령 저택",
    "폐병원",
    "저주받은 마을",
    "고립된 섬"
]

for theme in themes:
    result = generate_horror_story(
        custom_request=f"{theme}을 배경으로 한 호러 소설"
    )
    print(f"✅ {theme} 소설 생성 완료!")
```

### 2. 대화형 생성기

```python
from horror_story_generator import generate_horror_story

def interactive_horror_generator():
    print("호러 소설 생성기에 오신 것을 환영합니다!")

    location = input("배경 장소를 입력하세요: ")
    theme = input("원하는 테마를 입력하세요: ")
    style = input("원하는 스타일을 입력하세요 (예: 심리적, 초자연적): ")

    request = f"{location}을 배경으로 {theme}를 주제로 한 {style} 호러 소설"

    result = generate_horror_story(custom_request=request)

    print("\n생성 완료!")
    print(f"파일 저장 위치: {result['file_path']}")

    return result

if __name__ == "__main__":
    interactive_horror_generator()
```

### 3. 웹 API 서버

```python
from flask import Flask, request, jsonify
from horror_story_generator import generate_horror_story

app = Flask(__name__)

@app.route("/generate", methods=["POST"])
def api_generate():
    data = request.json
    custom_request = data.get("request", None)

    result = generate_horror_story(
        custom_request=custom_request,
        save_output=True
    )

    return jsonify({
        "success": True,
        "story": result["story"],
        "metadata": result["metadata"],
        "file_path": result.get("file_path")
    })

if __name__ == "__main__":
    app.run(port=5000)
```

## 팁

1. **Temperature 조정**: `.env` 파일의 `TEMPERATURE` 값을 조정하여 창의성을 조절할 수 있습니다
   - 0.7-0.8: 균형잡힌 창의성
   - 0.9-1.0: 더 창의적이고 예측 불가능
   - 0.5-0.6: 더 일관되고 예측 가능

2. **토큰 수 조정**: 긴 소설을 원하면 `MAX_TOKENS` 값을 높이세요 (최대 8192)

3. **프롬프트 튜닝**: `horror_story_prompt_template.json`을 수정하여 원하는 스타일로 조정하세요

## 라이선스

MIT License

## 문의

이슈나 개선 제안이 있으시면 언제든지 연락주세요!
