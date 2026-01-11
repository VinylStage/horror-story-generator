# Horror Story Generator

A research-grounded Korean horror story generation system using Claude API with deduplication control and research integration.

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
├── horror_story_generator.py    # Core generation logic
├── api_client.py                # Claude API client
├── prompt_builder.py            # Prompt construction
├── ku_selector.py               # Knowledge Unit selection
├── template_manager.py          # Template loading
├── story_saver.py               # Story persistence
├── story_registry.py            # Deduplication registry
├── job_manager.py               # Job lifecycle management
├── job_monitor.py               # Process monitoring
│
├── research_executor/           # Research generation CLI
│   ├── cli.py                   # Entry point: python -m research_executor run
│   ├── research_generator.py    # Ollama-based generation
│   └── validator.py             # Output validation
│
├── research_api/                # FastAPI trigger API
│   ├── main.py                  # API server
│   └── routers/jobs.py          # Job endpoints
│
├── research_integration/        # Research integration modules
│   ├── story_seeds.py           # Seed management
│   ├── faiss_index.py           # Vector similarity
│   └── research_dedup_manager.py
│
├── phase1_foundation/           # Foundation assets [Active]
│   ├── 01_knowledge_units/      # 52 Knowledge Units (JSON)
│   └── 03_templates/            # 15 Templates (JSON)
│
├── data/                        # Runtime data
│   ├── stories/                 # Generated stories
│   ├── research/                # Research cards
│   ├── stories.db               # Story dedup registry
│   └── research_registry.db     # Research dedup registry
│
├── jobs/                        # Job metadata (JSON)
├── logs/                        # Execution logs
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
python -m research_executor run TOPIC [OPTIONS]

Arguments:
  TOPIC                    Research topic (e.g., "Korean apartment horror")

Options:
  --tags TAG [TAG ...]     Classification tags
  --model MODEL            Ollama model (default: qwen3:30b)
  --timeout N              Generation timeout in seconds
```

### API Server

```bash
uvicorn research_api.main:app --host 0.0.0.0 --port 8000
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
| POST | `/jobs/{job_id}/dedup_check` | Check research card deduplication |

See `docs/API_DRAFT.md` for detailed API documentation.

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

See `docs/ARCHITECTURE_DRAFT.md` for detailed architecture documentation.

---

## Deduplication System

### Signal Levels

| Signal | Score Range | Behavior |
|--------|-------------|----------|
| LOW | < 0.3 | Accept story |
| MEDIUM | 0.3 - 0.6 | Accept story (logged) |
| HIGH | > 0.6 | Regenerate (max 2 retries), then skip |

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
OUTPUT_DIR=./generated_stories
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

See `CONTRIBUTING.md` for development guidelines.

---

## Documentation

| Document | Description |
|----------|-------------|
| `docs/ARCHITECTURE_DRAFT.md` | System architecture details |
| `docs/API_DRAFT.md` | API reference |
| `docs/roadmap_DRAFT.md` | Future development plans |
| `docs/DOCUMENT_MAP.md` | Documentation index |
| `docs/canonical_enum.md` | Canonical dimension definitions |
| `docs/decision_log.md` | Design decision records |

---

## License

MIT License

---

## Acknowledgments

- Horror research derived from academic sources (see Knowledge Units for citations)
- Built with Claude API (Anthropic)
- Research generation powered by Ollama

---

**Note:** This is a draft document. See `docs/DOCUMENT_MAP.md` for documentation status.
