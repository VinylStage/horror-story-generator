# Horror Story Generator

A research-grounded Korean horror story generation system using Claude API with deduplication control and research integration.

> **Version:** v1.3.2
>
> All documentation reflects the current `src/` package structure and Canonical Enum v1.0.

---

## Features

- **Research-Grounded Generation**: 52 Knowledge Units and 15 Templates derived from academic horror research
- **Template-Based Prompts**: Canonical dimension system ensures unique story patterns
- **Deduplication Control**: SQLite + FAISS-based similarity detection prevents repetitive content
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
│   │   └── research/            # Research dedup (FAISS)
│   │       ├── dedup.py         # Duplicate detection
│   │       ├── embedder.py      # Ollama embeddings
│   │       └── index.py         # FAISS index management
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
│   │       └── selector.py      # Context selection
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
```

### Research Generation

```bash
python -m src.research.executor run TOPIC [OPTIONS]

Arguments:
  TOPIC                    Research topic (e.g., "Korean apartment horror")

Options:
  --tags TAG [TAG ...]     Classification tags
  --model MODEL            Ollama model (default: qwen3:30b)
  --timeout N              Generation timeout in seconds
```

### API Server

```bash
uvicorn src.api.main:app --host 0.0.0.0 --port 8000
```

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

**Research Dedup (Semantic Embedding via FAISS):**

| Signal | Score Range | Behavior |
|--------|-------------|----------|
| LOW | < 0.70 | Unique topic |
| MEDIUM | 0.70 - 0.85 | Some overlap (logged) |
| HIGH | ≥ 0.85 | Likely duplicate |

Research embeddings use `nomic-embed-text` model via Ollama (768 dimensions).

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

---

## License

MIT License

---

## Acknowledgments

- Horror research derived from academic sources (see Knowledge Units for citations)
- Built with Claude API (Anthropic)
- Research generation powered by Ollama

