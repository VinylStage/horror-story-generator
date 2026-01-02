# n8n 환경 설정 및 보안 가이드

## 개요

이 문서는 n8n과 호러 소설 생성기를 연동하기 위한 환경 설정 방법을 설명합니다.

**핵심 원칙:**
- API 키 등 민감 정보는 안전하게 관리
- 환경별 (로컬/Docker/Cloud) 최적 설정 제공
- n8n 연동 관점에서의 보안 고려사항만 다룸

**다루는 환경:**
1. 로컬 n8n (npm 또는 로컬 실행)
2. Docker n8n
3. n8n.cloud (클라우드 호스팅)

---

## 프로젝트 디렉토리 구조

### 기본 구조

```
n8n-test/
├── .env                           # 환경 변수 (민감 정보 포함, .gitignore 필수)
├── .env.example                   # 환경 변수 예시 (공개 가능)
├── templates/                     # 프롬프트 템플릿 디렉토리
│   ├── horror_story_prompt_template.json  # 기본 템플릿
│   ├── sample.json
│   ├── horror_story_prompt_short.json     # 짧은 버전 (예시)
│   └── horror_story_prompt_psychological.json  # 심리 호러 (예시)
├── generated_stories/             # 생성된 소설 저장
│   ├── horror_story_*.md
│   └── horror_story_*_metadata.json
├── logs/                          # 실행 로그
│   └── horror_story_*.log
├── horror_story_generator.py      # 핵심 모듈
├── main.py                        # 테스트 스크립트
├── pyproject.toml                 # Poetry 의존성
└── poetry.lock
```

### templates 디렉토리 중요성

**템플릿 파일 역할:**
- 각 JSON 파일은 다른 장르/스타일/길이의 소설 생성 설정 포함
- n8n에서 템플릿을 선택하여 다양한 소설 생성 가능

**필수 확인:**
- `templates/` 디렉토리가 존재하는지
- 최소 1개 이상의 `.json` 템플릿 파일 포함
- n8n Execute Command가 접근 가능한 위치에 있는지

---

## 환경 1: 로컬 n8n

### 전제 조건

```bash
# n8n 설치 확인
npx n8n --version

# 또는 글로벌 설치
npm install -g n8n
n8n --version
```

### .env 파일 설정

#### 위치

```
/Users/vinyl/vinylstudio/n8n-test/.env
```

n8n과 Python 프로젝트가 **같은 서버/로컬 환경**에 있어야 합니다.

#### .env 파일 내용

```env
# Anthropic API 설정
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxxxxxxxxxx

# Claude 모델 설정
CLAUDE_MODEL=claude-sonnet-4-5-20250929
MAX_TOKENS=8192
TEMPERATURE=0.8

# 출력 디렉토리
OUTPUT_DIR=./generated_stories

# 로깅 설정
LOG_LEVEL=INFO
```

#### .env 파일 생성 방법

**1. .env.example 복사:**
```bash
cd /Users/vinyl/vinylstudio/n8n-test
cp .env.example .env
```

**2. 편집:**
```bash
# macOS/Linux
nano .env

# 또는 VS Code
code .env
```

**3. API 키 입력:**
- `ANTHROPIC_API_KEY` 값을 실제 API 키로 변경
- 다른 설정은 필요에 따라 조정

#### .env 파일 권한 설정

**보안을 위해 권한 제한:**

```bash
# .env 파일 권한 확인
ls -la .env

# 소유자만 읽기/쓰기 가능하게 설정
chmod 600 .env

# 확인
ls -la .env
# -rw------- 1 user user ... .env
```

**중요:**
- `.env` 파일은 절대 Git에 커밋하지 않음
- `.gitignore`에 `.env` 추가 확인

### Python 가상환경 설정

#### Poetry 사용 (권장)

```bash
cd /Users/vinyl/vinylstudio/n8n-test

# Poetry 가상환경 확인
poetry env info

# 의존성 설치
poetry install

# 가상환경 활성화 테스트
poetry run python3 --version
```

#### 수동 실행 테스트

```bash
# .env 파일이 로드되는지 확인
poetry run python3 -c "import os; from dotenv import load_dotenv; load_dotenv(); print('API Key:', os.getenv('ANTHROPIC_API_KEY')[:20] + '...')"

# 전체 파이프라인 테스트
poetry run python3 main.py
```

### n8n 실행

```bash
# 기본 실행
n8n

# 특정 포트 지정
n8n start --tunnel
```

**n8n 데이터 저장 위치:**
- 기본: `~/.n8n/`
- 워크플로, Credentials, 설정 등 저장

---

## 환경 2: Docker n8n

### Docker Compose 설정

#### docker-compose.yml 예시

```yaml
version: '3.8'

services:
  n8n:
    image: n8nio/n8n:latest
    container_name: n8n
    restart: unless-stopped
    ports:
      - "5678:5678"
    environment:
      - N8N_BASIC_AUTH_ACTIVE=true
      - N8N_BASIC_AUTH_USER=admin
      - N8N_BASIC_AUTH_PASSWORD=your_secure_password
    volumes:
      # n8n 데이터 영구 저장
      - n8n_data:/home/node/.n8n

      # 호러 소설 생성기 프로젝트 마운트
      - /Users/vinyl/vinylstudio/n8n-test:/data/horror-story-generator

      # .env 파일 마운트 (읽기 전용 권장)
      - /Users/vinyl/vinylstudio/n8n-test/.env:/data/horror-story-generator/.env:ro

      # templates 디렉토리 마운트
      - /Users/vinyl/vinylstudio/n8n-test/templates:/data/horror-story-generator/templates:ro

      # 생성된 파일 저장 위치 (읽기/쓰기)
      - /Users/vinyl/vinylstudio/n8n-test/generated_stories:/data/horror-story-generator/generated_stories

      # 로그 디렉토리
      - /Users/vinyl/vinylstudio/n8n-test/logs:/data/horror-story-generator/logs

volumes:
  n8n_data:
```

#### 실행

```bash
docker-compose up -d

# 로그 확인
docker-compose logs -f n8n
```

### Docker 환경에서 Python 실행

**문제:** Docker 컨테이너 내부에는 Python이 없을 수 있음

**해결 방법 1: Custom Docker Image (권장)**

**Dockerfile:**
```dockerfile
FROM n8nio/n8n:latest

# 루트 권한으로 전환
USER root

# Python 및 Poetry 설치
RUN apk add --no-cache python3 py3-pip curl

# Poetry 설치
RUN curl -sSL https://install.python-poetry.org | python3 -

# PATH 설정
ENV PATH="/root/.local/bin:${PATH}"

# 프로젝트 복사
COPY . /data/horror-story-generator
WORKDIR /data/horror-story-generator

# 의존성 설치
RUN poetry install --no-interaction --no-ansi

# n8n 사용자로 다시 전환
USER node

# n8n 실행
CMD ["n8n"]
```

**빌드 및 실행:**
```bash
# 이미지 빌드
docker build -t n8n-horror-generator .

# 실행
docker run -d \
  --name n8n \
  -p 5678:5678 \
  -v n8n_data:/home/node/.n8n \
  -v $(pwd)/generated_stories:/data/horror-story-generator/generated_stories \
  n8n-horror-generator
```

**해결 방법 2: 호스트 Python 사용 (Docker-in-Docker)**

복잡하므로 권장하지 않음. Custom Image 방식 사용 권장.

### Docker 환경에서 Execute Command 경로

**컨테이너 내부 경로 사용:**

```bash
cd /data/horror-story-generator && poetry run python3 main.py
```

**템플릿 선택 시:**
```bash
cd /data/horror-story-generator && poetry run python3 -c "from horror_story_generator import generate_horror_story; generate_horror_story(template_path='templates/sample.json')"
```

**주의:**
- 호스트 경로가 아닌 컨테이너 내부 마운트 경로 사용
- `/data/horror-story-generator`는 docker-compose.yml에서 설정한 경로

### Docker 환경 변수 주입

**방법 1: .env 파일 마운트 (권장)**

docker-compose.yml에서 이미 설정:
```yaml
- /Users/vinyl/vinylstudio/n8n-test/.env:/data/horror-story-generator/.env:ro
```

**방법 2: Docker 환경 변수로 직접 주입**

docker-compose.yml에 추가:
```yaml
services:
  n8n:
    environment:
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - CLAUDE_MODEL=claude-sonnet-4-5-20250929
```

호스트에서 환경 변수 export:
```bash
export ANTHROPIC_API_KEY=sk-ant-xxxxx
docker-compose up -d
```

---

## 환경 3: n8n.cloud

### 개요

n8n.cloud는 클라우드 호스팅 서비스로, **Execute Command 노드를 사용할 수 없습니다.**

**대안:**
1. **HTTP API 방식** (Task 7 - 선택사항 참고)
   - Python을 별도 서버에서 실행
   - FastAPI/Flask로 API 제공
   - n8n.cloud에서 HTTP Request 노드로 호출

2. **자체 서버 구축**
   - n8n을 자체 서버에 Docker로 설치
   - Execute Command 노드 사용 가능

### n8n.cloud 환경 변수 설정

**만약 HTTP API 방식을 사용한다면:**

1. n8n.cloud 좌측 메뉴 **"Settings"** → **"Environment Variables"**
2. **"Add Variable"** 클릭
3. 변수 추가:

| Name | Value |
|------|-------|
| `HORROR_API_URL` | `https://your-api-server.com` |
| `HORROR_API_KEY` | `your_api_key` |

4. HTTP Request 노드에서 사용:
```
URL: {{ $env.HORROR_API_URL }}/generate
Headers: { "Authorization": "Bearer {{ $env.HORROR_API_KEY }}" }
```

### n8n.cloud Credentials 활용

**Credentials 생성:**

1. 좌측 메뉴 **"Credentials"** → **"Add Credential"**
2. **"Header Auth"** 또는 **"Generic Credential"** 선택
3. 이름: `Horror API Auth`
4. 값 입력:
   - Header Name: `Authorization`
   - Header Value: `Bearer your_api_key`

5. HTTP Request 노드에서 Credentials 선택

---

## 보안 체크리스트

### API 키 관리

- [ ] `.env` 파일은 절대 Git에 커밋하지 않음
- [ ] `.gitignore`에 `.env` 추가 확인
- [ ] `.env` 파일 권한 `600` (소유자만 읽기/쓰기)
- [ ] `.env.example`은 실제 값 없이 키 이름만 포함
- [ ] Docker 환경에서는 `.env` 파일을 읽기 전용(`:ro`)으로 마운트
- [ ] n8n Credentials에 API 키 저장 시 암호화 확인
- [ ] API 키는 주기적으로 로테이션 (Anthropic 대시보드에서)

### 파일 권한 설정

**로컬 환경:**

```bash
# .env 파일 권한
chmod 600 .env

# templates 디렉토리 (읽기 전용)
chmod 644 templates/*.json

# generated_stories 디렉토리 (쓰기 가능)
chmod 755 generated_stories/

# logs 디렉토리 (쓰기 가능)
chmod 755 logs/
```

**Docker 환경:**

```yaml
# docker-compose.yml에서 읽기 전용 마운트
volumes:
  - ./templates:/data/horror-story-generator/templates:ro  # 읽기 전용
  - ./generated_stories:/data/horror-story-generator/generated_stories  # 읽기/쓰기
```

### 로그 파일 관리

**로그에 민감 정보 포함 방지:**

현재 코드는 API 키를 로그에 출력하지 않지만, 확인:

```bash
# 로그에 API 키가 없는지 확인
grep -r "sk-ant" logs/

# 로그 파일 권한
chmod 600 logs/*.log
```

**로그 파일 정리:**

```bash
# 30일 이상 된 로그 삭제
find logs/ -name "*.log" -mtime +30 -delete

# 또는 cron으로 자동화
# 매일 자정에 실행
0 0 * * * find /path/to/logs/ -name "*.log" -mtime +30 -delete
```

### n8n 워크플로 보안

**Execute Command 노드 주의사항:**

- [ ] Command에 하드코딩된 API 키 없는지 확인
- [ ] 사용자 입력을 직접 Command에 삽입하지 않음 (Command Injection 방지)
- [ ] Webhook으로 받은 데이터는 검증 후 사용

**잘못된 예시 (위험):**
```bash
# 사용자 입력을 직접 삽입 - Command Injection 위험
cd /project && python -c "print('{{ $json.user_input }}')"
```

**올바른 예시:**
```bash
# 미리 정의된 템플릿 경로만 사용
cd /project && poetry run python3 -c "from horror_story_generator import generate_horror_story; generate_horror_story(template_path='{{ $json.template_path }}')"
```

**템플릿 경로 검증 (Code 노드 추가):**
```javascript
// 허용된 템플릿 리스트
const allowedTemplates = [
  'templates/horror_story_prompt_template.json',
  'templates/sample.json',
  'templates/horror_story_prompt_short.json'
];

const requestedTemplate = $json.template_path;

if (!allowedTemplates.includes(requestedTemplate)) {
  throw new Error('Invalid template path');
}

return { json: { template_path: requestedTemplate } };
```

---

## templates 디렉토리 관리

### 템플릿 파일 위치

**로컬 환경:**
```
/Users/vinyl/vinylstudio/n8n-test/templates/
```

**Docker 환경:**
```
# 호스트
/Users/vinyl/vinylstudio/n8n-test/templates/

# 컨테이너 내부
/data/horror-story-generator/templates/
```

### 템플릿 추가 방법

**1. 새 템플릿 파일 생성:**

```bash
cd /Users/vinyl/vinylstudio/n8n-test/templates

# 기존 템플릿 복사
cp horror_story_prompt_template.json horror_story_prompt_gothic.json

# 편집
code horror_story_prompt_gothic.json
```

**2. JSON 유효성 검증:**

```bash
# Python으로 검증
python3 -c "import json; json.load(open('templates/horror_story_prompt_gothic.json'))"

# 또는 온라인 도구: https://jsonlint.com/
```

**3. 수동 테스트:**

```bash
poetry run python3 -c "from horror_story_generator import generate_horror_story; generate_horror_story(template_path='templates/horror_story_prompt_gothic.json', save_output=False)"
```

**4. n8n 워크플로에서 사용:**

Set 노드에서:
```json
{
  "template_path": "templates/horror_story_prompt_gothic.json"
}
```

### 템플릿 백업

**중요:** templates 디렉토리는 Git으로 버전 관리 권장

```bash
# Git에 추가
git add templates/

# 커밋
git commit -m "feat: Add gothic horror template"

# 푸시
git push
```

---

## 문제 해결

### .env 파일을 찾을 수 없음

**증상:**
```
ValueError: ANTHROPIC_API_KEY가 .env 파일에 설정되지 않았습니다.
```

**확인:**
```bash
# 파일 존재 여부
ls -la /Users/vinyl/vinylstudio/n8n-test/.env

# 내용 확인
cat /Users/vinyl/vinylstudio/n8n-test/.env | grep ANTHROPIC_API_KEY

# 작업 디렉토리 확인 (Execute Command 실행 위치)
pwd
```

**해결:**
1. `.env` 파일이 프로젝트 루트에 있는지 확인
2. Execute Command에서 `cd` 명령으로 프로젝트 디렉토리로 이동 확인

### Docker에서 templates 디렉토리 접근 불가

**증상:**
```
FileNotFoundError: 프롬프트 템플릿 파일을 찾을 수 없습니다
```

**확인:**
```bash
# Docker 컨테이너 내부 접속
docker exec -it n8n /bin/sh

# 디렉토리 확인
ls -la /data/horror-story-generator/templates/
```

**해결:**
docker-compose.yml에서 templates 마운트 확인:
```yaml
volumes:
  - /Users/vinyl/vinylstudio/n8n-test/templates:/data/horror-story-generator/templates:ro
```

### 권한 오류

**증상:**
```
Permission denied: './generated_stories'
```

**해결:**
```bash
# 디렉토리 권한 확인
ls -la generated_stories/

# 쓰기 권한 부여
chmod 755 generated_stories/
chmod 755 logs/

# Docker의 경우 소유자 확인
# n8n은 보통 node 사용자로 실행됨
sudo chown -R 1000:1000 generated_stories/
sudo chown -R 1000:1000 logs/
```

---

## 환경별 권장 설정 요약

| 환경 | 권장 방식 | 보안 수준 | 복잡도 |
|------|----------|-----------|--------|
| **로컬 n8n** | .env 파일 + Poetry | 중간 | 낮음 |
| **Docker n8n** | Custom Image + 볼륨 마운트 | 높음 | 중간 |
| **n8n.cloud** | HTTP API (Task 7) | 높음 | 높음 |

---

## 체크리스트: 환경 설정 완료 확인

### 공통

- [ ] `.env` 파일 생성 및 API 키 설정
- [ ] `.env` 파일 권한 `600` 설정
- [ ] `.gitignore`에 `.env` 추가
- [ ] `templates/` 디렉토리 존재 확인
- [ ] 최소 1개 템플릿 파일 존재
- [ ] `generated_stories/` 디렉토리 쓰기 권한
- [ ] `logs/` 디렉토리 쓰기 권한
- [ ] 수동 실행 테스트 성공

### 로컬 환경

- [ ] Poetry 설치 및 의존성 설치
- [ ] n8n 설치 및 실행 가능
- [ ] Execute Command 노드에서 절대 경로 사용
- [ ] 템플릿 경로 확인

### Docker 환경

- [ ] docker-compose.yml 작성
- [ ] 볼륨 마운트 설정 (프로젝트, .env, templates)
- [ ] Custom Image 빌드 (Python 포함)
- [ ] 컨테이너 내부 경로로 Command 수정
- [ ] 파일 권한 확인 (UID 1000)

### n8n.cloud

- [ ] HTTP API 서버 구축 필요성 인지
- [ ] Task 7 (선택사항) 참고 계획
- [ ] 또는 자체 서버로 전환 고려

---

## 요약

**이 가이드에서 다룬 내용:**
- ✅ 프로젝트 디렉토리 구조 (templates 포함)
- ✅ 로컬 n8n 환경 설정 (.env, Poetry, 권한)
- ✅ Docker n8n 환경 설정 (볼륨, Custom Image)
- ✅ n8n.cloud 대안 (HTTP API)
- ✅ 보안 체크리스트 (API 키, 파일 권한, 로그)
- ✅ templates 디렉토리 관리 (추가, 백업, 검증)
- ✅ 문제 해결 가이드

**다루지 않은 내용:**
- ❌ API 키 자동 로테이션 시스템
- ❌ 비밀 관리 확장 (Vault, AWS Secrets Manager 등)
- ❌ 고급 보안 설정 (네트워크 격리, 방화벽 등)
- ❌ 프로덕션 레벨 인프라 구축

**범위 준수:**
- n8n 연동 관점에서의 환경 설정만 다룸
- 기본적인 보안 수준 제공
- 실무 사용 가능한 설정 중심
