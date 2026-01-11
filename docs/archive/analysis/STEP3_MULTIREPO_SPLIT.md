# STEP 3: Multi-Repository Split Assessment

**Status:** Assessment Only (NOT EXECUTED)
**Date:** 2026-01-12
**Purpose:** Evaluate potential for splitting into multiple repositories

---

## IMPORTANT NOTICE

**THIS DOCUMENT IS FOR FUTURE PLANNING ONLY.**

No repository split is being executed. This assessment identifies:
- Which components could theoretically become separate repos
- Current coupling that prevents immediate separation
- What would need to change before splitting

---

## 1. Current Monorepo State

The repository currently contains:

| Component | Description | Could Be Separate? |
|-----------|-------------|-------------------|
| Story Generator | Claude-based story generation | Potentially |
| Research Generator | Ollama-based research cards | Potentially |
| Trigger API | FastAPI job execution | Yes |
| Dedup System | FAISS + SQLite deduplication | Yes |
| Foundation Assets | KUs, templates, canonical | Questionable |

---

## 2. Potential Repository Candidates

### 2.1 horror-story-core (Story Generation)

**What it would contain:**
- `src/generator/*`
- `src/common/story_seed.py`
- Story dedup logic
- Foundation assets

**Dependencies:**
- Claude API (anthropic package)
- Foundation assets (templates, KUs)
- Dedup system

**Separation Readiness:** LOW

**Blockers:**
- Tightly coupled to foundation assets
- Shares dedup system with research
- Entry point (main.py) spans concerns

### 2.2 horror-research (Research Generation)

**What it would contain:**
- `src/research/*`
- Research-specific dedup
- Ollama client

**Dependencies:**
- Ollama API
- FAISS for vector dedup
- Common data paths

**Separation Readiness:** MEDIUM

**Blockers:**
- Shares dedup infrastructure
- Research cards feed into story generation
- Common data path utilities

### 2.3 horror-api (Trigger API)

**What it would contain:**
- `src/api/*`
- Job management (`src/jobs/*`)
- API-specific schemas

**Dependencies:**
- FastAPI, Uvicorn
- Calls story/research CLIs via subprocess

**Separation Readiness:** HIGH

**Rationale:**
- Already isolated via subprocess calls
- No direct Python imports of generation logic
- Could call any CLI that matches expected interface

### 2.4 horror-dedup (Deduplication Library)

**What it would contain:**
- `src/dedup/*`
- FAISS index management
- Embedding logic

**Dependencies:**
- FAISS-cpu
- sentence-transformers (if local embedding)
- SQLite

**Separation Readiness:** MEDIUM

**Blockers:**
- Used by both story and research pipelines
- Would need versioned interface contract
- Embedding model choice couples to use case

### 2.5 horror-assets (Foundation Assets)

**What it would contain:**
- Knowledge Units JSON
- Template skeletons JSON
- Canonical mappings

**Dependencies:**
- None (static data)

**Separation Readiness:** HIGH (as data package)

**Considerations:**
- Could be a separate data-only package
- Versioned independently
- Consumers install as dependency

---

## 3. Dependency Graph

```
┌─────────────────────────────────────────────────────────────────┐
│                         horror-api                               │
│                    (subprocess calls)                            │
└──────────────────────────┬──────────────────────────────────────┘
                           │
          ┌────────────────┴────────────────┐
          │                                 │
          ▼                                 ▼
┌─────────────────────┐         ┌─────────────────────┐
│   horror-story-core │         │   horror-research   │
└─────────┬───────────┘         └─────────┬───────────┘
          │                               │
          │         ┌─────────────────────┘
          │         │
          ▼         ▼
┌─────────────────────┐
│    horror-dedup     │
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│   horror-assets     │
│   (data package)    │
└─────────────────────┘
```

---

## 4. What Must Stay Monorepo (For Now)

### 4.1 Immediate Blockers

| Coupling | Reason | Resolution Required |
|----------|--------|---------------------|
| Shared dedup | Story + Research use same FAISS infrastructure | Define stable interface |
| Foundation assets | Hardcoded paths in multiple modules | Package as installable |
| Common utilities | data_paths.py used everywhere | Extract to shared package |
| Registry databases | SQLite files shared across modules | Database abstraction |

### 4.2 Technical Debt Preventing Split

1. **Path Coupling**
   - `data_paths.py` assumes monorepo structure
   - Templates loaded relative to project root
   - Database paths hardcoded

2. **Import Coupling**
   - Direct imports between components
   - No interface contracts
   - No version compatibility checks

3. **Data Flow Coupling**
   - Research cards → Story prompts (direct file access)
   - Shared embedding model instance
   - Common logging configuration

---

## 5. Prerequisites for Future Split

### 5.1 Before Any Split

1. **Complete STEP 3 restructuring**
   - Move to `src/` structure
   - Clear module boundaries
   - Clean imports

2. **Define interface contracts**
   - API schemas as separate package
   - CLI argument formats documented
   - File format specifications

3. **Abstract shared infrastructure**
   - Dedup as standalone library
   - Database access layer
   - Configuration management

### 5.2 Minimum Viable Split Order

If splitting becomes necessary:

1. **First: horror-assets** (data package)
   - Lowest risk
   - No code, just data
   - Version independently

2. **Second: horror-api** (API server)
   - Already isolated via subprocess
   - Minimal code changes
   - Could point to any CLI

3. **Third: horror-dedup** (library)
   - Required by both generators
   - Needs stable interface
   - Medium complexity

4. **Last: horror-story-core + horror-research**
   - Highest coupling
   - Most complex
   - Defer until absolutely necessary

---

## 6. Recommended Approach

### 6.1 Current Recommendation

**STAY MONOREPO**

Reasons:
- Single developer/small team
- Shared infrastructure not yet abstracted
- Restructuring not complete
- No compelling split benefit yet

### 6.2 When to Reconsider

Consider splitting when:
- Multiple teams working independently
- Components need different release cycles
- Deployment requires isolation
- Repository size becomes problematic
- Clear boundaries established

### 6.3 Incremental Steps Toward Split-Readiness

Without actually splitting:

1. Complete STEP 3 restructuring
2. Add `__init__.py` with clean public APIs
3. Document interface contracts
4. Use relative imports within packages
5. Treat packages as if they were separate

---

## 7. Risk Assessment

| Split Scenario | Risk | Effort | Benefit |
|----------------|------|--------|---------|
| Keep monorepo | LOW | None | Simplicity |
| Split horror-assets | LOW | Small | Clean data versioning |
| Split horror-api | MEDIUM | Medium | Deployment flexibility |
| Split horror-dedup | MEDIUM | Medium | Reusable library |
| Full split | HIGH | Large | Team independence |

---

## 8. Conclusion

### 8.1 Summary

- Multi-repo split is **theoretically possible** but **not recommended now**
- Current coupling makes immediate split high-risk
- STEP 3 restructuring is prerequisite
- Focus on clean boundaries within monorepo first

### 8.2 Action Items (Not Executed)

1. Complete monorepo restructuring (STEP 3)
2. Establish clean package boundaries
3. Document interface contracts
4. Revisit split decision after v0.5.0

---

## 9. Execution Status

**THIS IS AN ASSESSMENT ONLY.**

No repository split is being executed.

This document exists to:
- Guide future architectural decisions
- Identify current coupling issues
- Provide roadmap if split becomes necessary

Any actual split would require:
- Explicit human decision
- Significant preparation work
- Careful migration planning
