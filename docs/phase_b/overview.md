# Phase B: Research Quality Influence

## Purpose

Phase B extends the horror story generation system with **quality influence** capabilities derived from research cards. This phase introduces a non-blocking advisory layer that provides contextual suggestions to the story generator without enforcing constraints.

## Core Principle: Influence, Not Control

Phase B operates on a fundamental design principle:

> **Research informs generation; it does not dictate it.**

The system will:
- **Suggest** relevant concepts from research cards
- **Surface** deduplication signals for user awareness
- **Provide** cultural context hints

The system will NOT:
- Block story generation based on research quality
- Automatically filter or reject stories
- Override user creative decisions

## Components

### 1. Research Context Injection
Research cards produce `key_concepts` and `horror_applications` that can be optionally injected into the system prompt via `prompt_builder.py`. This provides thematic guidance without enforcement.

### 2. Dedup Signal Advisory
Similarity signals (LOW/MEDIUM/HIGH) are computed and displayed to the user. The user decides whether to proceed, regenerate, or modify parameters.

### 3. Quality Metadata (Optional)
Research cards may include optional quality fields for future filtering and prioritization. These fields are advisory and do not affect generation flow.

## Integration Points

| Component | File | Function |
|-----------|------|----------|
| Research Context | `prompt_builder.py` | `build_system_prompt(research_context=...)` |
| Dedup Signal | `story_registry.py` | `compute_similarity()` |
| Quality Display | `main.py` (future) | CLI output formatting |

## Non-Goals for Phase B

- No automatic research execution before generation
- No embedding-based semantic search (deferred to future vector backend)
- No LLM-based quality scoring at runtime
- No generation blocking or rejection logic

## User Control Philosophy

All Phase B features are **opt-in** and **transparent**:

1. User explicitly requests research injection via CLI flag
2. Dedup signals are displayed, not enforced
3. Quality metadata is informational only

The user remains in full control of the creative process.
