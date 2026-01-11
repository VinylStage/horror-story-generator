# STEP 3: Migration Safety Plan

**Status:** Plan Only (Not Executed)
**Date:** 2026-01-12
**Purpose:** Define safe, reversible migration steps

---

## 1. Migration Principles

### 1.1 Core Safety Rules

1. **One Commit Per Logical Change** - Each move is atomic and revertible
2. **Tests Pass After Each Step** - No broken intermediate states
3. **Backward Compatibility Period** - Keep re-exports during transition
4. **No Data Loss** - Generated data directories untouched initially
5. **Documentation First** - Update docs before code

### 1.2 Git Safety Protocol

```bash
# Before ANY migration work
git checkout main
git pull origin main
git checkout -b refactor/step3-restructure

# After EACH migration phase
git add -A
git commit -m "refactor(structure): <phase description>"
pytest  # Must pass
git push origin refactor/step3-restructure
```

---

## 2. Migration Phases

### Phase 0: Preparation (LOW RISK)
**Risk Level:** LOW
**Estimated Effort:** Small

| Step | Action | Command | Rollback |
|------|--------|---------|----------|
| 0.1 | Create target directories | `mkdir -p src/{generator,research,api,dedup,registry,jobs,common}` | `rm -rf src/` |
| 0.2 | Create assets directories | `mkdir -p assets/{knowledge_units,templates,canonical}` | `rm -rf assets/` |
| 0.3 | Create docs subdirectories | `mkdir -p docs/{core,technical,archive/{phase_docs,n8n_guides,work_logs}}` | Reverse mkdir |
| 0.4 | Add `__init__.py` files | Create empty init files | Remove them |

**Verification:**
```bash
ls -la src/*/
ls -la assets/*/
ls -la docs/*/
```

---

### Phase 1: Documentation Migration (LOW RISK)
**Risk Level:** LOW
**Estimated Effort:** Small

Documentation has no runtime impact and can be moved freely.

| Step | Action | Files | Rollback |
|------|--------|-------|----------|
| 1.1 | Move archive docs | PHASE*.md, work_log*.md, n8n*.md, PROJECT_HANDOFF.md | `git checkout HEAD~1 -- docs/` |
| 1.2 | Move technical docs | canonical_enum.md, decision_log.md, runbook*.md | Same |
| 1.3 | Promote draft docs | README_DRAFT→README, ARCHITECTURE_DRAFT→ARCHITECTURE | Same |
| 1.4 | Move raw research | phase1_foundation/00_raw_research/ | Same |
| 1.5 | Move phase2 specs | phase2_execution/*.md | Same |

**Verification:**
```bash
ls docs/core/
ls docs/technical/
ls docs/archive/
```

**Commit:**
```bash
git add docs/
git commit -m "docs(structure): reorganize documentation into core/technical/archive tiers"
```

---

### Phase 2: Asset Migration (MEDIUM RISK)
**Risk Level:** MEDIUM
**Estimated Effort:** Medium

Assets require path updates in code.

| Step | Action | Current Path | New Path |
|------|--------|--------------|----------|
| 2.1 | Move KUs | phase1_foundation/01_knowledge_units/ | assets/knowledge_units/ |
| 2.2 | Move templates | phase1_foundation/03_templates/ | assets/templates/ |
| 2.3 | Move canonical | phase1_foundation/02_canonical_abstraction/ | assets/canonical/ |
| 2.4 | Update data_paths.py | - | Update path constants |
| 2.5 | Update template_loader.py | - | Update path references |

**Required Code Changes:**

```python
# data_paths.py - BEFORE
KNOWLEDGE_UNITS_PATH = Path("phase1_foundation/01_knowledge_units")
TEMPLATES_PATH = Path("phase1_foundation/03_templates")

# data_paths.py - AFTER
KNOWLEDGE_UNITS_PATH = Path("assets/knowledge_units")
TEMPLATES_PATH = Path("assets/templates")
```

**Verification:**
```bash
pytest tests/test_data_paths.py
pytest tests/test_template_loader.py
python -c "from template_loader import load_templates; print(load_templates())"
```

**Rollback:**
```bash
git checkout HEAD~1 -- phase1_foundation/ assets/ data_paths.py template_loader.py
```

**Commit:**
```bash
git add phase1_foundation/ assets/ data_paths.py template_loader.py
git commit -m "refactor(assets): move foundation assets to assets/ directory"
```

---

### Phase 3: Package Consolidation (MEDIUM RISK)
**Risk Level:** MEDIUM
**Estimated Effort:** Medium

Consolidate existing packages without moving root modules yet.

| Step | Action | Current | Target |
|------|--------|---------|--------|
| 3.1 | Move research_api | research_api/* | src/api/* |
| 3.2 | Move research_executor | research_executor/* | src/research/* |
| 3.3 | Move research_dedup | research_dedup/* | src/dedup/* |
| 3.4 | Merge research_integration | research_integration/* | src/research/* |
| 3.5 | Update relative imports | - | All moved files |

**Import Update Pattern:**

```python
# BEFORE (in research_api/routers/jobs.py)
from ..services.dedup_service import DedupService

# AFTER (in src/api/routers/jobs.py)
from src.api.services.dedup_service import DedupService
```

**Required grep/sed updates:**
```bash
# Find all imports that need updating
grep -r "from research_api" --include="*.py"
grep -r "from research_executor" --include="*.py"
grep -r "from research_dedup" --include="*.py"
grep -r "from research_integration" --include="*.py"
```

**Verification:**
```bash
pytest tests/test_api_endpoints.py
pytest tests/test_research_*.py
pytest tests/test_dedup_*.py
python -m src.research.cli --help  # Test CLI still works
uvicorn src.api.main:app --help    # Test API still works
```

**Rollback:**
```bash
git checkout HEAD~1 -- research_api/ research_executor/ research_dedup/ research_integration/ src/
```

---

### Phase 4: Root Module Migration (HIGH RISK)
**Risk Level:** HIGH
**Estimated Effort:** Large

This is the highest-risk phase. Move root Python modules to src/.

| Step | Action | Current | Target |
|------|--------|---------|--------|
| 4.1 | Create src/generator/ modules | - | Move generator-related |
| 4.2 | Create src/dedup/ additions | - | Move dedup-related |
| 4.3 | Create src/registry/ | - | Move registry-related |
| 4.4 | Create src/jobs/ | - | Move job-related |
| 4.5 | Create src/common/ | - | Move common utilities |
| 4.6 | Keep main.py as wrapper | main.py | Thin wrapper |

**Detailed File Moves:**

```
# Generator
horror_story_generator.py → src/generator/horror_story_generator.py
api_client.py → src/generator/api_client.py
prompt_builder.py → src/generator/prompt_builder.py
template_loader.py → src/generator/template_loader.py
logging_config.py → src/generator/logging_config.py

# Dedup (additions to existing)
story_registry.py → src/dedup/story_registry.py
similarity.py → src/dedup/similarity.py

# Registry
research_registry.py → src/registry/research_registry.py
seed_registry.py → src/registry/seed_registry.py
seed_integration.py → src/registry/seed_integration.py

# Jobs
job_manager.py → src/jobs/manager.py
job_monitor.py → src/jobs/monitor.py

# Common
data_paths.py → src/common/data_paths.py
story_seed.py → src/common/story_seed.py
```

**Backward Compatibility Re-exports:**

Create temporary re-export files at root during transition:

```python
# horror_story_generator.py (root - temporary)
"""Backward compatibility re-export. Remove in v0.5.0"""
import warnings
warnings.warn(
    "Import from src.generator instead of root",
    DeprecationWarning,
    stacklevel=2
)
from src.generator.horror_story_generator import *
```

**Mass Import Update:**
```bash
# Find all files needing updates
grep -rn "from horror_story_generator import" --include="*.py"
grep -rn "from story_registry import" --include="*.py"
grep -rn "from similarity import" --include="*.py"
# ... etc for each module
```

**Verification:**
```bash
pytest  # Full test suite
python main.py --help
python -m src.research.cli --help
uvicorn src.api.main:app --help
```

**Rollback:**
```bash
git checkout HEAD~1 -- *.py src/ tests/
```

---

### Phase 5: Test Import Updates (MEDIUM RISK)
**Risk Level:** MEDIUM
**Estimated Effort:** Medium

Update all test imports to use new paths.

```python
# BEFORE
from horror_story_generator import HorrorStoryGenerator

# AFTER
from src.generator import HorrorStoryGenerator
```

**Verification:**
```bash
pytest --collect-only  # Verify tests can be collected
pytest                  # Full test run
```

---

### Phase 6: Cleanup (LOW RISK)
**Risk Level:** LOW
**Estimated Effort:** Small

Remove backward compatibility shims after transition period.

| Step | Action | Timing |
|------|--------|--------|
| 6.1 | Remove root re-export files | After v0.4.0 release |
| 6.2 | Remove empty phase directories | After confirmation |
| 6.3 | Update pyproject.toml packages | With cleanup |
| 6.4 | Final documentation update | Last step |

---

## 3. Risk Assessment Matrix

| Phase | Risk | Impact if Failed | Mitigation |
|-------|------|------------------|------------|
| Phase 0 | LOW | None - just directories | Simple rm |
| Phase 1 | LOW | Docs broken links | Git revert |
| Phase 2 | MEDIUM | Runtime path errors | Keep originals temporarily |
| Phase 3 | MEDIUM | Import errors | Extensive testing |
| Phase 4 | HIGH | Complete breakage | Re-export shims, git revert |
| Phase 5 | MEDIUM | Test failures | Fix or revert |
| Phase 6 | LOW | Minor cleanup | Skip if issues |

---

## 4. Rollback Strategy

### Quick Rollback (Any Phase)
```bash
git checkout main
git branch -D refactor/step3-restructure
```

### Partial Rollback (Specific Phase)
```bash
git log --oneline  # Find commit before problematic phase
git revert <commit-hash>
```

### Emergency Recovery
```bash
# If in bad state, reset to last known good
git stash
git checkout main
git pull origin main
```

---

## 5. Verification Checklist

After each phase, verify:

- [ ] `pytest` passes (100% of existing tests)
- [ ] `python main.py --help` works
- [ ] `python -m research_executor run --help` works (or new path)
- [ ] `uvicorn research_api.main:app --help` works (or new path)
- [ ] No import errors in any module
- [ ] Documentation links not broken
- [ ] Git history clean (no merge conflicts)

---

## 6. Estimated Total Effort

| Phase | Effort | Files Affected | Risk |
|-------|--------|----------------|------|
| Phase 0 | 10 min | 0 (dirs only) | LOW |
| Phase 1 | 30 min | ~25 docs | LOW |
| Phase 2 | 1 hour | ~5 data + 2 code | MEDIUM |
| Phase 3 | 2 hours | ~25 package files | MEDIUM |
| Phase 4 | 3 hours | ~15 root + all imports | HIGH |
| Phase 5 | 1 hour | ~23 test files | MEDIUM |
| Phase 6 | 30 min | Cleanup only | LOW |

**Total Estimated: 8-10 hours of focused work**

---

## 7. Prerequisites Before Execution

1. **All tests passing** - Current test suite at 93%+ coverage
2. **Clean git state** - No uncommitted changes
3. **Backup exists** - Remote push of current state
4. **Block period** - No concurrent development
5. **Human approval** - Review of this plan

---

## 8. Execution Status

**THIS IS A PLAN ONLY.**

No migration has been executed.

Execution requires explicit human approval and should be done in a dedicated refactoring session.

---

## 9. Open Questions

1. **Should Phase 4 be split into smaller commits?**
   - Pro: More granular rollback
   - Con: More complex, more intermediate broken states

2. **How long to maintain backward compatibility shims?**
   - Proposal: Until v0.5.0 release

3. **Should we update CI/CD before or after migration?**
   - Proposal: After, once structure is stable

4. **External integrations (n8n) - how to communicate changes?**
   - Proposal: Document in release notes, provide migration guide
