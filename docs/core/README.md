# Horror Story Generator

A research-grounded Korean horror story generation system using Claude API with deduplication control and research integration.

> **Version:** v1.5.0 <!-- x-release-please-version -->
>
> All documentation reflects the current `src/` package structure and Canonical Enum v1.0.

---

## Features

- **Research-Grounded Generation**: 52 Knowledge Units and 15 Templates derived from academic horror research
- **Template-Based Prompts**: Canonical dimension system ensures unique story patterns
- **Deduplication Control**: SQLite + FAISS-based similarity detection with hybrid story dedup (v1.4.0)
- **Research Integration**: Ollama-powered research card generation for fresh concepts
- **Trigger API**: Non-blocking job execution via FastAPI
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
# Generate a single story
python main.py

# Generate multiple stories with deduplication
python main.py --max-stories 5 --enable-dedup --interval-seconds 60

# Run for 24 hours
python main.py --duration-seconds 86400 --interval-seconds 1800 --enable-dedup
```

---

## Project Structure

```
horror-story-generator/
├── main.py                      # Story generation CLI entry point
├── src/                         # Main source package
│   ├── infra/                   # Infrastructure modules
│   │   ├── data_paths.py        # Centralized path management
│   │   ├── job_manager.py       # Job lifecycle management
│   │   ├── job_monitor.py       # Process monitoring
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
│   │   ├── executor/            # CLI executor
│   │   │   ├── cli.py           # Entry point
│   │   │   ├── executor.py      # Ollama-based generation
│   │   │   └── validator.py     # Output validation
│   │   └── integration/         # Story-research bridge
│   │       ├── loader.py        # Card loading
│   │       ├── selector.py      # Context selection
│   │       └── vector_backend_hooks.py  # Vector operations (v1.4.0)
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
│   ├── novel/                   # Generated stories (v1.3.1+)
│   ├── story_vectors/           # Story FAISS index (v1.4.0)
│   └── *.db                     # SQLite databases
├── logs/                        # Execution logs
├── tests/                       # Test suite
└── docs/                        # Documentation
```

---

## CLI Reference

### Story Generation

```bash
python main.py [OPTIONS]

Options:
  --max-stories N          Maximum stories to generate (default: 1)
  --duration-seconds N     Run duration limit in seconds
  --interval-seconds N     Wait time between generations (default: 0)
  --enable-dedup           Enable deduplication control
  --db-path PATH           SQLite database path
  --load-history           Load existing stories into memory
  --model MODEL            Model selection (see below)
```

**Model Options:**

| Value | Description |
|-------|-------------|
| (default) | Claude Sonnet - 고품질 한국어 호러 |
| `claude-sonnet-4-5-20250929` | Claude Sonnet 명시적 지정 |
| `claude-opus-4-5-20251101` | Claude Opus (고성능) |
| `ollama:qwen3:30b` | 로컬 Ollama 모델 |

**Examples:**
```bash
# Claude 기본 (권장)
python main.py --max-stories 3 --enable-dedup

# Ollama 로컬 모델
python main.py --model ollama:qwen3:30b
```

### Research Generation

```bash
python -m src.research.executor run TOPIC [OPTIONS]

Arguments:
  TOPIC                    Research topic (e.g., "Korean apartment horror")

Options:
  --tags TAG [TAG ...]     Classification tags
  --model MODEL            Model selection (see below)
  --timeout N              Generation timeout in seconds
  --dry-run                Show prompt without executing
  --skip-markdown          Skip generating markdown file
  -o, --output-dir PATH    Output directory (default: data/research)
```

**Model Options:**

| Value | Description | Timeout |
|-------|-------------|---------|
| `qwen3:30b` (default) | Ollama 로컬 모델 | 60s |
| `gemini` | Google Gemini API | 120s |
| `deep-research` | Gemini Deep Research Agent (고품질, 권장) | 300-600s |

**Requirements:**
- Gemini 모델: `GEMINI_ENABLED=true`, `GEMINI_API_KEY` 환경변수 필요

**Examples:**
```bash
# Ollama 기본
python -m src.research.executor run "Korean apartment horror"

# Gemini Deep Research (권장)
python -m src.research.executor run "Korean apartment horror" --model deep-research --timeout 300

# Gemini 표준
python -m src.research.executor run "Urban isolation" --model gemini --timeout 120

# 태그 포함
python -m src.research.executor run "Subway horror" --tags urban supernatural --model deep-research
```

### API Server

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

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/jobs/story/trigger` | Trigger story generation job |
| POST | `/jobs/research/trigger` | Trigger research generation job |
| GET | `/jobs/{job_id}` | Get job status |
| GET | `/jobs` | List all jobs |
| POST | `/jobs/{job_id}/cancel` | Cancel running job |
| POST | `/jobs/monitor` | Update all running job statuses |
| POST | `/jobs/{job_id}/dedup_check` | Check canonical deduplication |
| POST | `/research/run` | Run research generation (sync) |
| GET | `/research/list` | List research cards |
| POST | `/research/dedup` | Check semantic similarity (FAISS) |

See `docs/technical/TRIGGER_API.md` for detailed API documentation.

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

### 3. Trigger API Pipeline

```
HTTP Request → Job Creation → Subprocess Launch → PID Monitoring → Status Update
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
STORY_SEMANTIC_THRESHOLD=0.85        # Semantic HIGH threshold
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
| `docs/technical/TRIGGER_API.md` | API reference |
| `docs/core/ROADMAP.md` | Future development plans |
| `CONTRIBUTING.md` | Development guidelines |
| `docs/technical/canonical_enum.md` | Canonical dimension definitions |
| `docs/technical/decision_log.md` | Design decision records |
| `docs/technical/RESEARCH_DEDUP_SETUP.md` | Research embedding setup |
| `docs/technical/STORY_SEMANTIC_DEDUP.md` | Story semantic dedup setup (v1.4.0) |

---

## License

MIT License

---

## Acknowledgments

- Horror research derived from academic sources (see Knowledge Units for citations)
- Built with Claude API (Anthropic)
- Research generation powered by Ollama

