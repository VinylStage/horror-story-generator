# TODO Index

**Status:** Active
**Version:** v1.3.1
**Last Updated:** 2026-01-13
**Audit Method:** Documentation scan (no source code TODO comments)

---

## Overview

This document consolidates all TODOs, deferred items, explicit non-features, planned improvements, and future work references extracted from project documentation. Items are categorized, prioritized, and deduplicated.

**Total Items:** 32
**Intentionally Deferred:** 18
**Explicitly Not Planned:** 5
**Open Questions/Uncertainties:** 9

---

## Table of Contents

1. [RESEARCH_PIPELINE_V2](#1-research_pipeline_v2)
2. [STORY_GENERATION_ENHANCEMENT](#2-story_generation_enhancement)
3. [INFRA / PERFORMANCE](#3-infra--performance)
4. [API / OBSERVABILITY](#4-api--observability)
5. [RELEASE / PROCESS](#5-release--process)
6. [DOCUMENTATION_ONLY](#6-documentation_only)
7. [EXPLICITLY NOT PLANNED](#7-explicitly-not-planned)
8. [OPEN QUESTIONS / UNCERTAINTIES](#8-open-questions--uncertainties)

---

## 1. RESEARCH_PIPELINE_V2

Items related to multi-step deep research, web crawling, citations, agent loops.

| ID | Description | Priority | Source | Status |
|----|-------------|----------|--------|--------|
| TODO-001 | **Multi-step agent research loop** - Current research is single LLM call. Future: iterative refinement, self-reflection, recursive queries | P2 | `docs/core/ROADMAP.md` (implied), Analysis task | DEFERRED |
| TODO-002 | **Citation crawling / web search integration** - Research does not crawl external sources | P3 | Analysis task (explicit non-feature) | NOT PLANNED |
| TODO-003 | **OpenSearch as Vector DB candidate** - Replace FAISS with OpenSearch for long-term scalability and metadata filtering | P3 | `docs/technical/FUTURE_VECTOR_BACKEND_NOTE.md` | DEFERRED |

**Notes:**
- Current "deep research" is structurally deep (prompt + post-processing) but single-call
- Multi-agent research explicitly confirmed as NOT present in current implementation

---

## 2. STORY_GENERATION_ENHANCEMENT

Items related to style options, quality scoring, retry logic.

| ID | Description | Priority | Source | Status |
|----|-------------|----------|--------|--------|
| TODO-004 | **Story quality validation** - Validate generated stories against canonical constraints, check alignment with template canonical_core | P2 | `docs/OPERATIONAL_STATUS.md`, `docs/core/ROADMAP.md` | DEFERRED |
| TODO-005 | **Story Embedding-Based Deduplication** - Replace canonical fingerprint matching with semantic embeddings (FAISS + sentence-transformers) | P2 | `docs/core/ROADMAP.md` (Medium-Term) | DEFERRED |
| TODO-006 | **Cultural Weighting System** - Prioritize Korean-specific content in KU/template selection with `--cultural-mode korean|universal` | P2 | `docs/core/ROADMAP.md` (Medium-Term) | DEFERRED |
| TODO-007 | **Prompt Compiler** - Automated prompt construction from template + KUs with rule engine, variation engine | P2 | `docs/core/ROADMAP.md` (Medium-Term) | DEFERRED |
| TODO-008 | **Output Validation Strictness** - How strict should canonical constraint checking be? | P3 | `docs/technical/decision_log.md` (D-104) | DEFERRED |
| TODO-009 | **Variation Engine Design** - Should variation_axes be parametric or stochastic? | P3 | `docs/technical/decision_log.md` (D-102) | DEFERRED |
| TODO-010 | **Prompt Compilation Strategy** - How to structure LLM prompts from template + KUs | P3 | `docs/technical/decision_log.md` (D-103) | DEFERRED |
| TODO-011 | **Story output Canonical Key generation** - Stories do not generate their own Canonical Key | P3 | `docs/technical/CANONICAL_KEY_APPLICATION_SCOPE.md` | DEFERRED |
| TODO-012 | **Canonical Key enforcement on story output** - No validation that story content matches template's canonical_core | P3 | `docs/technical/CANONICAL_KEY_APPLICATION_SCOPE.md` | DEFERRED |
| TODO-013 | **Cross-pipeline Canonical Key matching** - No automatic matching between research affinity and template core | P3 | `docs/technical/CANONICAL_KEY_APPLICATION_SCOPE.md` | DEFERRED |

**Notes:**
- TODO-004 and TODO-012 are related (quality validation and canonical enforcement)
- Cultural weighting design exists in archived docs, not implemented

---

## 3. INFRA / PERFORMANCE

Items related to FAISS optimization, background jobs, scaling.

| ID | Description | Priority | Source | Status |
|----|-------------|----------|--------|--------|
| TODO-014 | **Job storage scalability** - File-based JSON may not scale for high volume | P2 | `docs/core/ARCHITECTURE.md`, `docs/core/ROADMAP.md` | UNCERTAIN |
| TODO-015 | **FAISS index performance beyond 10,000 research cards** - Performance characteristics unknown at scale | P3 | `docs/core/ARCHITECTURE.md` | UNCERTAIN |
| TODO-016 | **Unify output directories** - generated_stories/ vs data/stories/ inconsistency | P3 | `docs/core/ROADMAP.md` (Technical Debt) | **DONE (v1.3.1)** |
| TODO-017 | **Path constant centralization** - Currently scattered across modules | P3 | `docs/core/ROADMAP.md` (Technical Debt) | **DONE (v1.3.1)** |
| TODO-018 | **Legacy research_cards.jsonl cleanup** - Superseded by data/research/ | P3 | `docs/core/ROADMAP.md` (Technical Debt) | **DONE (v1.3.1)** |
| TODO-019 | **Job history cleanup / automatic pruning** - No automatic pruning mechanism | P3 | `docs/core/ROADMAP.md` (Technical Debt) | **DONE (v1.3.1)** |

**Notes:**
- Job storage and FAISS scaling are UNCERTAIN, not blocking

---

## 4. API / OBSERVABILITY

Items related to progress tracking, WebSocket, monitoring.

| ID | Description | Priority | Source | Status |
|----|-------------|----------|--------|--------|
| TODO-020 | **Webhook Notifications** - POST to user-specified URL on job status change with retry logic | P1 | `docs/core/ROADMAP.md` (Near-Term), `docs/technical/TRIGGER_API.md`, `docs/core/API.md` | **DONE (v1.3.0)** |
| TODO-021 | **Batch Job Trigger** - POST /jobs/batch/trigger, GET /jobs/batch/{batch_id} for aggregate status | P1 | `docs/core/ROADMAP.md` (Near-Term), `docs/technical/TRIGGER_API.md` | PLANNED |
| TODO-022 | **n8n Integration Examples** - Complete n8n workflow templates for common patterns | P2 | `docs/core/ROADMAP.md` (Near-Term), `docs/technical/TRIGGER_API.md` | PLANNED |
| TODO-023 | **Real-time monitoring dashboard** - Not implemented | P3 | `docs/OPERATIONAL_STATUS.md` | NOT PLANNED |
| TODO-024 | **Authentication approach** - API keys vs OAuth undecided | P2 | `docs/core/ROADMAP.md` (Open Questions) | UNCERTAIN |

**Notes:**
- Webhook and Batch Job are highest priority API enhancements

---

## 5. RELEASE / PROCESS

Items related to release-please, automation.

| ID | Description | Priority | Source | Status |
|----|-------------|----------|--------|--------|
| TODO-025 | **Test coverage gaps** - ~93% but some edge cases remain | P3 | `docs/core/ROADMAP.md` (Technical Debt) | PENDING |

**Notes:**
- No release-please or CI/CD automation documented as TODO

---

## 6. DOCUMENTATION_ONLY

Items related to doc cleanup, explanation additions.

| ID | Description | Priority | Source | Status |
|----|-------------|----------|--------|--------|
| TODO-026 | **Remove phase-based naming** - All docs and directories contain legacy phase naming | P2 | `docs/core/ROADMAP.md` (Technical Debt) | PENDING |
| TODO-027 | **Consolidate scattered docs** - Effort underway but not complete | P2 | `docs/core/ROADMAP.md` (Technical Debt) | IN PROGRESS |
| TODO-028 | **Archive historical docs** - DOCUMENT_MAP.md identifies targets | P3 | `docs/core/ROADMAP.md` (Technical Debt) | PENDING |

**Notes:**
- Doc consolidation partially addressed by recent verification reports

---

## 7. EXPLICITLY NOT PLANNED

Features explicitly marked as out of scope.

| ID | Description | Source | Reason |
|----|-------------|--------|--------|
| NP-001 | **Multimodal content (images)** | `docs/core/ROADMAP.md` | Beyond current project goals |
| NP-002 | **Distributed execution** | `docs/core/ROADMAP.md`, `docs/OPERATIONAL_STATUS.md` | Complexity vs. benefit |
| NP-003 | **Real-time collaboration** | `docs/core/ROADMAP.md` | Single-user design |
| NP-004 | **Commercial API hosting** | `docs/core/ROADMAP.md` | Local-first architecture |
| NP-005 | **Platform auto-upload** | `docs/OPERATIONAL_STATUS.md` | Not in scope |

---

## 8. OPEN QUESTIONS / UNCERTAINTIES

Items requiring investigation or decision before implementation.

| ID | Question | Source | Status |
|----|----------|--------|--------|
| Q-001 | **Optimal KU count per template?** | `docs/core/ROADMAP.md`, `docs/core/ARCHITECTURE.md`, `docs/technical/decision_log.md` (D-101) | Currently 2-5, needs validation after 10+ generations |
| Q-002 | **Embedding model choice?** | `docs/core/ROADMAP.md` | multilingual-MiniLM vs ko-sroberta |
| Q-003 | **Job storage scalability?** | `docs/core/ROADMAP.md`, `docs/core/ARCHITECTURE.md` | File-based may not scale |
| Q-004 | **Authentication approach?** | `docs/core/ROADMAP.md` | API keys vs OAuth |
| Q-005 | **FAISS index performance beyond 10,000 cards?** | `docs/core/ARCHITECTURE.md` | Unknown |
| Q-006 | **Output validation strictness level?** | `docs/core/ROADMAP.md` | May require LLM-based analysis |
| Q-007 | **Variation engine design?** | `docs/technical/decision_log.md` | Parametric vs stochastic |
| Q-008 | **Prompt compilation strategy?** | `docs/technical/decision_log.md` | Structure TBD |
| Q-009 | **KU count per template validation?** | `docs/technical/decision_log.md` | Revisit after 10+ generations |

---

## Priority Legend

| Priority | Definition |
|----------|------------|
| P0 | Blocks correctness or data integrity |
| P1 | Needed for next production milestone |
| P2 | Clear enhancement, not urgent |
| P3 | Nice-to-have / long-term |

---

## Summary by Category

| Category | Total | P0 | P1 | P2 | P3 |
|----------|-------|----|----|----|----|
| RESEARCH_PIPELINE_V2 | 3 | 0 | 0 | 1 | 2 |
| STORY_GENERATION_ENHANCEMENT | 10 | 0 | 0 | 4 | 6 |
| INFRA / PERFORMANCE | 2 | 0 | 0 | 1 | 1 |
| API / OBSERVABILITY | 5 | 0 | 1 | 2 | 1 |
| RELEASE / PROCESS | 1 | 0 | 0 | 0 | 1 |
| DOCUMENTATION_ONLY | 3 | 0 | 0 | 2 | 1 |
| **TOTAL** | **24** | **0** | **1** | **10** | **12** |

---

## Change Log

| Date | Change |
|------|--------|
| 2026-01-13 | TODO-016~019 (Infra/Performance debt) marked DONE in v1.3.1 |
| 2026-01-13 | TODO-020 (Webhook Notifications) marked DONE in v1.3.0 |
| 2026-01-13 | Initial extraction from v1.2.1 documentation |

---

**Note:** This index does NOT include source code TODO comments. It reflects documentation-based future work items only.
