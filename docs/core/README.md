# Horror Story Generator

A research-grounded Korean horror story generation system using Claude API with deduplication control and research integration.

> **Version:** v2.0.3 <!-- x-release-please-version -->
>
> All documentation reflects the current `src/` package structure and Canonical Enum v1.0.

---

## Features

- **Research-Grounded Generation**: 52 Knowledge Units and 15 Templates derived from academic horror research
- **Template-Based Prompts**: Canonical dimension system ensures unique story patterns
- **Deduplication Control**: SQLite + FAISS-based similarity detection with hybrid story dedup (v1.4.0)
- **Research Integration**: Ollama-powered research card generation for fresh concepts
- **Task Scheduler**: Queue-based task execution via FastAPI
- **Korean Output**: All stories generated in Korean with cultural specificity
- **24h Continuous Operation**: Background execution with graceful shutdown

---

## Quick Start

### Prerequisites

- Python 3.10+
- Anthropic API key (Claude)
- Ollama (optional, for research generation)

### Installation

```bash
# Clone repository
git clone <repository-url>
cd horror-story-generator

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your ANTHROPIC_API_KEY
```

### Basic Usage

```bash
# Start the API server
uvicorn src.api.main:app --host 0.0.0.0 --port 8000

# Generate a single story (blocking)
curl -X POST http://localhost:8000/story/generate \
  -H "Content-Type: application/json" \
  -d '{"topic": "Korean apartment horror"}'

# Create task(s) via scheduler (non-blocking, always array input)
curl -X POST http://localhost:8000/tasks \
  -H "Content-Type: application/json" \
  -d '[{"type": "story", "params": {"topic": "Korean apartment horror"}, "priority": 10}]'

# Check task status
curl http://localhost:8000/tasks/{task_id}
```

---

## Project Structure

```
horror-story-generator/
├── src/                         # Main source package
│   ├── infra/                   # Infrastructure modules
│   │   ├── data_paths.py        # Centralized path management
│   │   └── logging_config.py    # Logging setup
│   │
│   ├── registry/                # Data persistence
│   │   ├── story_registry.py    # Story dedup registry (SQLite)
│   │   ├── seed_registry.py     # Seed usage tracking
│   │   └── research_registry.py # Research card tracking
│   │
│   ├── dedup/                   # Deduplication logic
│   │   ├── similarity.py        # Story similarity (in-memory)
│   │   ├── research/            # Research dedup (FAISS)
│   │   │   ├── dedup.py         # Duplicate detection
│   │   │   ├── embedder.py      # Ollama embeddings
│   │   │   └── index.py         # FAISS index management
│   │   └── story/               # Story semantic dedup (v1.4.0)
│   │       ├── embedder.py      # Story text embedding
│   │       ├── index.py         # Story FAISS index
│   │       ├── semantic_dedup.py # Semantic similarity
│   │       └── hybrid_dedup.py  # Hybrid scoring
│   │
│   ├── story/                   # Story generation pipeline
│   │   ├── generator.py         # Core generation orchestration
│   │   ├── api_client.py        # Claude API client
│   │   ├── prompt_builder.py    # Prompt construction
│   │   ├── template_loader.py   # Template loading
│   │   ├── story_seed.py        # Seed data structures
│   │   └── seed_integration.py  # Seed injection
│   │
│   ├── research/                # Research generation
│   │   ├── executor/            # Research executor
│   │   │   ├── executor.py      # Ollama-based generation
│   │   │   └── validator.py     # Output validation
│   │   └── integration/         # Story-research bridge
│   │       ├── loader.py        # Card loading
│   │       ├── selector.py      # Context selection
│   │       └── vector_backend_hooks.py  # Vector operations (v1.4.0)
│   │
│   ├── scheduler/               # Task scheduler engine
│   │   ├── service.py           # Scheduler service
│   │   ├── persistence.py       # SQLite persistence
│   │   └── executor.py          # Task execution dispatch
│   │
│   └── api/                     # FastAPI application
│       ├── main.py              # API server
│       ├── routers/             # HTTP endpoints
│       ├── schemas/             # Pydantic models
│       └── services/            # Business logic
│
├── assets/                      # Static assets
│   └── templates/               # 15 Template skeletons
│
├── data/                        # Runtime data
│   ├── research/                # Research cards (YYYY/MM/)
│   ├── seeds/                   # Story seeds
│   ├── novel/                   # Generated stories
│   ├── story_vectors/           # Story FAISS index (v1.4.0)
│   └── *.db                     # SQLite databases
├── logs/                        # Execution logs
├── tests/                       # Test suite
└── docs/                        # Documentation
```

### Story Output Format

Generated stories follow vinylog blog-compatible format:

**Filename Pattern**: `story-YYYYMMDD-HHMMSS.md`

**Frontmatter Fields**:

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `title` | string | Extracted from story | "할머니의 집" |
| `slug` | string | URL-friendly ID | "story-20260118-183713" |
| `category` | string | Fixed value | "Horror" |
| `date` | string | Generation date | "2026-01-18" |
| `excerpt` | string | Story preview | "나는 할머니 집에..." |
| `tags` | array | YAML format tags | `- 호러`<br>`- horror` |
| `readTime` | string | 200 chars/min | "22 min read" |
| `featured` | boolean | Featured flag | false |
| `thumbnail` | string | Thumbnail URL | "" |
| `genre` | string | Genre | "호러" |
| `wordCount` | integer | Character count | 4376 |
| `model` | string | Generation model | "claude-sonnet-4-5..." |
| `temperature` | number | Model temp | 0.8 |
| `draft` | boolean | Draft status | false |

---

## API Usage

### Starting the Server

```bash
uvicorn src.api.main:app --host 0.0.0.0 --port 8000

# Options
--host HOST              Bind address (default: 127.0.0.1)
--port PORT              Port number (default: 8000)
--reload                 Auto-reload on code changes (dev only)
```

**Endpoints:**
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- Health: `http://localhost:8000/health`

### Backup & Restore (v1.4.3+)

```bash
# 전체 백업 (압축)
./scripts/backup.sh --compress

# 복구
./scripts/restore.sh backups/backup_20260118_120000.tar.gz

# 복구 미리보기
./scripts/restore.sh backups/backup_20260118_120000.tar.gz --dry-run

# 백업 무결성 검증 (13개 테스트)
./scripts/verify_backup.sh
```

**백업 대상:**
- Story Registry (`data/story_registry.db`)
- Research 데이터 (`data/research/` - DB, FAISS, JSON)
- 생성된 스토리 (`data/novel/` - format: `story-YYYYMMDD-HHMMSS.md`)
- Story 벡터 인덱스 (`data/story_vectors/`)
- Seed 데이터 (`data/seeds/`)

자세한 내용은 `docs/technical/BACKUP_RESTORE_GUIDE.md` 참조.

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/tasks` | Create task(s) in scheduler queue |
| GET | `/tasks` | List all tasks |
| GET | `/tasks/{task_id}` | Get task details |
| PATCH | `/tasks/{task_id}` | Update task priority |
| DELETE | `/tasks/{task_id}` | Cancel task |
| GET | `/tasks/{task_id}/runs` | Get task execution history |
| POST | `/tasks/group` | Create task group |
| POST | `/scheduler/start` | Start scheduler |
| POST | `/scheduler/stop` | Stop scheduler |
| GET | `/scheduler/status` | Get scheduler status |
| POST | `/story/generate` | Generate story directly (blocking) |
| POST | `/research/run` | Run research generation (blocking) |
| GET | `/research/list` | List research cards |
| POST | `/research/dedup` | Check semantic similarity (FAISS) |
| POST | `/dedup/evaluate` | Evaluate story deduplication |

See `docs/core/API.md` for detailed API documentation.

---

## Architecture Overview

The system consists of three main pipelines:

### 1. Story Generation Pipeline

```
Template + Knowledge Units → Prompt Builder → Claude API → Story → Dedup Check → Save
```

### 2. Research Generation Pipeline

```
Topic → Ollama (qwen3) → Research Card → FAISS Index → Dedup Check → Save
```

### 3. Task Scheduler Pipeline

```
POST /tasks → Task Queue (SQLite) → Scheduler Dispatch → Executor → Status Update
```

See `docs/core/ARCHITECTURE.md` for detailed architecture documentation.

---

## Deduplication System

### Signal Levels

**Story Dedup (Canonical Matching):**

| Signal | Score Range | Behavior |
|--------|-------------|----------|
| LOW | < 0.3 | Accept story |
| MEDIUM | 0.3 - 0.6 | Accept story (logged) |
| HIGH | > 0.6 | Regenerate (max 2 retries), then skip |

**Story Semantic Dedup (v1.4.0, Hybrid):**

Combines signature-based exact matching with semantic embedding similarity:

```
hybrid_score = (canonical_score × 0.3) + (semantic_score × 0.7)
```

| Signal | Score Range | Behavior |
|--------|-------------|----------|
| LOW | < 0.70 | Accept story |
| MEDIUM | 0.70 - 0.85 | Accept story (logged) |
| HIGH | ≥ 0.85 | Duplicate detected |

**Research Dedup (Semantic Embedding via FAISS):**

| Signal | Score Range | Behavior |
|--------|-------------|----------|
| LOW | < 0.70 | Unique topic |
| MEDIUM | 0.70 - 0.85 | Some overlap (logged) |
| HIGH | ≥ 0.85 | Likely duplicate |

Both story and research embeddings use `nomic-embed-text` model via Ollama (768 dimensions).

### Canonical Dimensions

Stories are fingerprinted using 5 canonical dimensions:
- **setting_archetype**: Where horror occurs (apartment, hospital, digital, etc.)
- **primary_fear**: Core psychological fear (isolation, identity_erasure, etc.)
- **antagonist_archetype**: Source of threat (system, technology, ghost, etc.)
- **threat_mechanism**: How horror operates (surveillance, erosion, etc.)
- **twist_family**: Narrative resolution pattern (revelation, inevitability, etc.)

---

## Configuration

### Environment Variables

```bash
# Required
ANTHROPIC_API_KEY=sk-ant-...

# Optional
CLAUDE_MODEL=claude-sonnet-4-5-20250929
MAX_TOKENS=8192
TEMPERATURE=0.8
NOVEL_OUTPUT_DIR=./data/novel
STORY_REGISTRY_DB_PATH=./data/stories.db
LOG_LEVEL=INFO

# Story Dedup (v1.4.0)
ENABLE_STORY_DEDUP=true              # Enable signature-based dedup
STORY_DEDUP_STRICT=false             # Abort on duplicate detection
ENABLE_STORY_SEMANTIC_DEDUP=true     # Enable semantic embedding dedup
STORY_SEMANTIC_THRESHOLD_HIGH=0.85   # Semantic HIGH threshold
STORY_SEMANTIC_THRESHOLD_MEDIUM=0.70 # Semantic MEDIUM threshold
STORY_HYBRID_THRESHOLD=0.85          # Hybrid duplicate threshold

# Vector Backend (v1.4.0)
VECTOR_BACKEND_ENABLED=true          # Enable vector operations for research

# API Authentication (Optional)
API_AUTH_ENABLED=false    # true로 설정 시 X-API-Key 인증 활성화
API_KEY=your-secure-key   # 인증에 사용할 API 키
```

---

## Development

### Running Tests

```bash
pytest tests/ -v
```

### Code Style

- PEP 8 compliance
- Type hints required
- Google-style docstrings

See root `CONTRIBUTING.md` for development guidelines.

---

## Documentation

| Document | Description |
|----------|-------------|
| `docs/core/ARCHITECTURE.md` | System architecture details |
| `docs/core/API.md` | API reference |
| `docs/core/ROADMAP.md` | Future development plans |
| `CONTRIBUTING.md` | Development guidelines |
| `docs/technical/canonical_enum.md` | Canonical dimension definitions |
| `docs/technical/decision_log.md` | Design decision records |
| `docs/technical/RESEARCH_DEDUP_SETUP.md` | Research embedding setup |
| `docs/technical/STORY_SEMANTIC_DEDUP.md` | Story semantic dedup setup (v1.4.0) |

---

## License

CC BY-NC-SA 4.0

---

## Acknowledgments

- Horror research derived from academic sources (see Knowledge Units for citations)
- Built with Claude API (Anthropic)
- Research generation powered by Ollama
