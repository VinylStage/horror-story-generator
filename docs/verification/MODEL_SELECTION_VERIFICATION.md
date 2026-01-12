# Model Selection & Gemini Preparation - Verification Report

**Date:** 2026-01-13
**Version:** v1.1.0
**Status:** VERIFIED

---

## Task Summary

Implemented unified model selection for story and research generation pipelines with Gemini API preparation.

---

## A) MODEL SELECTION

### Story Generation

| Provider | CLI Format | Example |
|----------|-----------|---------|
| Claude (default) | `(none)` or model name | `python main.py` |
| Ollama | `ollama:{model}` | `python main.py --model ollama:llama3` |

**Verification:**
```python
>>> from src.story.model_provider import parse_model_spec
>>> parse_model_spec(None)
ModelInfo(provider='anthropic', model_name='claude-sonnet-4-5-20250929', full_spec='claude-sonnet-4-5-20250929')
>>> parse_model_spec('ollama:llama3')
ModelInfo(provider='ollama', model_name='llama3', full_spec='ollama:llama3')
```

### Research Generation

| Provider | CLI Format | Example |
|----------|-----------|---------|
| Ollama (default) | `(none)` or model name | `python -m src.research.executor run "topic"` |
| Gemini | `gemini` | `python -m src.research.executor run "topic" --model gemini` |

**Verification:**
```python
>>> from src.research.executor.model_provider import parse_research_model_spec
>>> parse_research_model_spec(None)
ResearchModelInfo(provider='ollama', model_name='qwen3:30b', full_spec='ollama:qwen3:30b')
>>> parse_research_model_spec('gemini')
ResearchModelInfo(provider='gemini', model_name='gemini-2.5-flash', full_spec='gemini:gemini-2.5-flash')
```

---

## B) METADATA RECORDING

### Story Metadata

Location: `src/story/generator.py` (lines 496, 761)

```json
{
  "model": "claude-sonnet-4-5-20250929",
  "provider": "anthropic"
}
```

or

```json
{
  "model": "llama3",
  "provider": "ollama"
}
```

### Research Metadata

Location: `src/research/executor/executor.py` (line 204)

```json
{
  "model": "qwen3:30b",
  "provider": "ollama"
}
```

---

## C) GEMINI API PREPARATION

### Feature-Flagged Configuration

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `GEMINI_ENABLED` | `false` | Must be `true` to use Gemini |
| `GEMINI_API_KEY` | `""` | Required when enabled |
| `GEMINI_MODEL` | `gemini-2.5-flash` | Default Gemini model |

### Provider Implementation

Location: `src/research/executor/model_provider.py`

- `GeminiResearchProvider` class (lines 204-278)
- Uses `google-genai` SDK: `from google import genai`
- Client initialization: `client = genai.Client(api_key=self.api_key)`

### Availability Check

```python
>>> from src.research.executor.model_provider import is_gemini_available, GEMINI_ENABLED
>>> GEMINI_ENABLED
False
>>> is_gemini_available()
False
```

---

## D) PIPELINE INTEGRATION

### CLI Arguments

**Story CLI (main.py):**
```
--model MODEL         모델 선택. 기본=Claude Sonnet. 형식: 'ollama:llama3', 'ollama:qwen', 또는 Claude 모델명
```

**Research CLI (src.research.executor):**
```
-m MODEL, --model MODEL
                      Model to use. Default: qwen3:30b. Formats: 'qwen3:30b' (Ollama), 'gemini' or 'gemini:model-name' (Gemini API)
```

### API Schema

**Story Trigger (POST /jobs/story/trigger):**
```json
{
  "model": "ollama:llama3"
}
```

**Research Trigger (POST /jobs/research/trigger):**
```json
{
  "model": "gemini"
}
```

---

## E) DOCUMENTATION UPDATED

| Document | Changes |
|----------|---------|
| `README.md` | Added model selection CLI examples, Gemini/Ollama env vars |
| `docs/core/ARCHITECTURE.md` | Added "Model Selection" section with provider abstraction diagram |
| `docs/core/API.md` | Added `model` field to story/research trigger requests |
| `docs/technical/runbook_24h_test.md` | Added `--model` CLI argument, OLLAMA env vars |

---

## F) FILES CHANGED

### Created

| File | Purpose |
|------|---------|
| `src/story/model_provider.py` | Story provider abstraction (Claude/Ollama) |
| `src/research/executor/model_provider.py` | Research provider abstraction (Ollama/Gemini) |

### Modified

| File | Changes |
|------|---------|
| `main.py` | Added `--model` argument |
| `src/story/api_client.py` | Added `call_llm_api()` function |
| `src/story/generator.py` | Added `model_spec` parameter, `provider` metadata |
| `src/api/schemas/jobs.py` | Added `model` field to `StoryTriggerRequest` |
| `src/api/routers/jobs.py` | Added model to CLI command builder |
| `src/research/executor/executor.py` | Added `provider` metadata, `execute_research_with_provider()` |
| `src/research/executor/cli.py` | Updated help text for `--model` |
| `.env.example` | Added Gemini and Ollama configuration |

---

## G) COMMITS

| Hash | Description |
|------|-------------|
| `cb53603` | feat: add model selection for story generation and Gemini prep for research |
| `e541ba9` | docs: add model selection and Gemini API documentation |

---

## H) BACKWARD COMPATIBILITY

| Scenario | Result |
|----------|--------|
| `python main.py` (no args) | Uses Claude Sonnet (default) |
| `python -m src.research.executor run "topic"` | Uses Ollama qwen3:30b (default) |
| Existing dedup pipeline | Unchanged |
| Existing metadata fields | Extended, not modified |

---

## I) VERIFICATION CHECKLIST

- [x] Story generation: Claude default works
- [x] Story generation: Ollama model spec parsing works
- [x] Research generation: Ollama default works
- [x] Research generation: Gemini model spec parsing works
- [x] Gemini is feature-flagged (disabled by default)
- [x] `provider` field added to story metadata
- [x] `provider` field added to research metadata
- [x] `--model` CLI argument for story
- [x] `--model` CLI argument for research
- [x] API schema includes `model` field
- [x] Documentation updated (README, ARCHITECTURE, API, runbook)
- [x] `.env.example` includes Gemini/Ollama vars
- [x] All tests pass (21/21 story dedup tests)

---

**Verification Status: PASS**

All objectives completed. Model selection is operational for both pipelines.
