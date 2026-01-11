# Document Map - Horror Story Generator

**Created:** 2026-01-12
**Purpose:** Index of all documentation with classification and migration status
**Note:** This is part of documentation consolidation. No files have been moved or deleted.

---

## Classification Legend

| Classification | Meaning | Action |
|----------------|---------|--------|
| `CORE` | Essential for understanding the current system | Consolidate into final docs |
| `TECHNICAL_DETAIL` | Useful technical reference, keep for developers | Reorganize under appropriate section |
| `HISTORICAL_ARCHIVE` | Records past decisions/work, not current operation | Move to archive/docs |
| `DELETE_CANDIDATE` | Superseded, outdated, or redundant | Flag for deletion (requires confirmation) |

---

## Root Directory Documents

| File | Classification | Rationale | Target Location |
|------|----------------|-----------|-----------------|
| `README.md` | `CORE` | Main project entry point, needs update | → `docs/README_DRAFT.md` (updated) |
| `CONTRIBUTING.md` | `CORE` | Developer onboarding, still relevant | Keep, update project structure |
| `PHASE1_IMPLEMENTATION_SUMMARY.md` | `HISTORICAL_ARCHIVE` | Records past implementation work | → `archive/docs/` |
| `PROMPT_REFACTOR_SUMMARY.md` | `HISTORICAL_ARCHIVE` | Records prompt changes from 2026-01-08 | → `archive/docs/` |
| `VERIFICATION_NOTES.md` | `HISTORICAL_ARCHIVE` | Implementation verification records | → `archive/docs/` |

---

## docs/ Directory Documents

### Core System Documentation

| File | Classification | Rationale | Target Location |
|------|----------------|-----------|-----------------|
| `docs/README.md` | `CORE` | docs index, describes foundation assets | Update to reflect current state |
| `docs/system_architecture.md` | `CORE` | System layer architecture | → `docs/ARCHITECTURE_DRAFT.md` |
| `docs/canonical_enum.md` | `TECHNICAL_DETAIL` | Canonical dimension definitions | Keep, reference from architecture |
| `docs/decision_log.md` | `TECHNICAL_DETAIL` | Design decisions with rationale | Keep as ADR reference |
| `docs/TRIGGER_API.md` | `CORE` | Current API documentation (Korean) | → `docs/API_DRAFT.md` |

### n8n Integration Documents

| File | Classification | Rationale | Target Location |
|------|----------------|-----------|-----------------|
| `docs/n8n_execute_command_guide.md` | `TECHNICAL_DETAIL` | n8n integration guide | Keep in `docs/guides/n8n/` |
| `docs/n8n_output_validation.md` | `TECHNICAL_DETAIL` | Output validation patterns | Keep in `docs/guides/n8n/` |
| `docs/n8n_workflow_import_guide.md` | `TECHNICAL_DETAIL` | Workflow import instructions | Keep in `docs/guides/n8n/` |
| `docs/n8n_environment_setup.md` | `TECHNICAL_DETAIL` | Environment setup for n8n | Keep in `docs/guides/n8n/` |

### Historical/Archive Documents

| File | Classification | Rationale | Target Location |
|------|----------------|-----------|-----------------|
| `docs/PROJECT_HANDOFF.md` | `HISTORICAL_ARCHIVE` | Project handoff from 2026-01-02 | → `archive/docs/` |
| `docs/runbook_24h_test.md` | `HISTORICAL_ARCHIVE` | 24h test runbook, specific to past test | → `archive/docs/` |
| `docs/work_log_20260108.md` | `HISTORICAL_ARCHIVE` | Daily work log | → `archive/docs/` |
| `docs/work_log_20260109.md` | `HISTORICAL_ARCHIVE` | Daily work log | → `archive/docs/` |
| `docs/FUTURE_VECTOR_BACKEND_NOTE.md` | `DELETE_CANDIDATE` | Placeholder for future work, no content | Delete or merge into roadmap |

### Documents Containing "PHASE" (Require Special Handling)

| File | Classification | Rationale | Target Location |
|------|----------------|-----------|-----------------|
| `docs/PHASE2_PREPARATION_ANALYSIS.md` | `HISTORICAL_ARCHIVE` | Marked "IMMUTABLE REFERENCE" | → `archive/docs/` |
| `docs/PHASE2A_TEMPLATE_ACTIVATION.md` | `HISTORICAL_ARCHIVE` | Template activation complete | → `archive/docs/` |
| `docs/PHASE2B_GENERATION_MEMORY.md` | `HISTORICAL_ARCHIVE` | Observation layer implemented | → `archive/docs/` |
| `docs/PHASE2C_DEDUP_CONTROL.md` | `CORE` | Current dedup implementation | Extract to `docs/ARCHITECTURE_DRAFT.md` |
| `docs/PHASE2C_RESEARCH_JOB.md` | `DELETE_CANDIDATE` | "SKELETON ONLY", superseded by research_executor | Delete after confirmation |
| `docs/PHASE_B_PLUS.md` | `CORE` | Current research/FAISS architecture | Extract to `docs/ARCHITECTURE_DRAFT.md` |

### docs/phase_b/ Subdirectory

| File | Classification | Rationale | Target Location |
|------|----------------|-----------|-----------------|
| `docs/phase_b/overview.md` | `DELETE_CANDIDATE` | Philosophy doc, features not implemented | Delete or archive |
| `docs/phase_b/dedup_signal_policy.md` | `TECHNICAL_DETAIL` | Signal definitions still valid | Extract to architecture |
| `docs/phase_b/research_quality_schema.md` | `TECHNICAL_DETAIL` | Schema still in use | Extract to API/schema docs |
| `docs/phase_b/cultural_scope_strategy.md` | `DELETE_CANDIDATE` | Weighting not implemented | Delete or archive |
| `docs/phase_b/future_vector_backend.md` | `DELETE_CANDIDATE` | Marked "NOT STARTED" | Merge into roadmap |

### docs/analysis/ Subdirectory (Recent Analysis)

| File | Classification | Rationale | Target Location |
|------|----------------|-----------|-----------------|
| `docs/analysis/TASK1_AS_IS_OVERVIEW.md` | `CORE` | Current system summary | Reference for architecture |
| `docs/analysis/TASK2_PHASE_DOCUMENT_CLASSIFICATION.md` | `TECHNICAL_DETAIL` | Document classification work | Reference for this map |
| `docs/analysis/TASK3_VERSION_DEFINITION_DRAFT.md` | `TECHNICAL_DETAIL` | Version definition proposal | Inform roadmap |
| `docs/analysis/TASK4_DIRECTORY_STRUCTURE_PROPOSAL.md` | `TECHNICAL_DETAIL` | Structure redesign proposal | Reference for future refactor |
| `docs/analysis/TASK5_DOCUMENTATION_STRATEGY.md` | `TECHNICAL_DETAIL` | Documentation strategy | Reference for this consolidation |
| `docs/analysis/TASK6_CLEANUP_PLAN.md` | `TECHNICAL_DETAIL` | Cleanup execution plan | Reference for future cleanup |

---

## Other Directories with Documentation

### phase1_foundation/

| Path | Classification | Rationale | Target Location |
|------|----------------|-----------|-----------------|
| `phase1_foundation/00_raw_research/report.md` | `HISTORICAL_ARCHIVE` | Raw research notes | → `archive/research/` |
| `phase1_foundation/02_canonical_abstraction/canonical_enum.md` | `TECHNICAL_DETAIL` | Duplicate of docs/canonical_enum.md | Delete (keep docs/ version) |

### phase2_execution/

| Path | Classification | Rationale | Target Location |
|------|----------------|-----------|-----------------|
| `phase2_execution/ku_selector/ku_selector_spec.md` | `HISTORICAL_ARCHIVE` | Spec for unimplemented feature | → `archive/docs/` |
| `phase2_execution/prompt_compiler/prompt_schema.md` | `HISTORICAL_ARCHIVE` | Spec for unimplemented feature | → `archive/docs/` |

---

## Classification Summary

| Classification | Count | Percentage |
|----------------|-------|------------|
| `CORE` | 9 | 24% |
| `TECHNICAL_DETAIL` | 15 | 41% |
| `HISTORICAL_ARCHIVE` | 9 | 24% |
| `DELETE_CANDIDATE` | 4 | 11% |
| **Total** | **37** | **100%** |

---

## New Documents to Create (Drafts)

| File | Purpose | Sources |
|------|---------|---------|
| `docs/README_DRAFT.md` | Updated project README | README.md, docs/README.md |
| `docs/ARCHITECTURE_DRAFT.md` | Unified system architecture | system_architecture.md, PHASE_B_PLUS.md, PHASE2C_DEDUP_CONTROL.md |
| `docs/API_DRAFT.md` | API reference | TRIGGER_API.md, research_quality_schema.md |
| `docs/roadmap_DRAFT.md` | Future work items | future_vector_backend.md, unimplemented features |

---

## Migration Notes

### Files NOT to Move or Delete (Actively Used)

The following are actively used by code and must not be moved without code changes:

- `phase1_foundation/01_knowledge_units/` - Used by `ku_selector.py`
- `phase1_foundation/03_templates/` - Used by `template_manager.py`
- `data/` directory structure - Used by multiple modules

### Uncertain Classifications (Human Confirmation Required)

| File | Question |
|------|----------|
| `docs/phase_b/cultural_scope_strategy.md` | Is cultural weighting planned for implementation? |
| `phase2_execution/` directory | Should specs be preserved for future reference? |
| Work logs (`work_log_*.md`) | Preserve for audit trail or archive? |

---

## Next Steps

1. **Create draft documents** (README_DRAFT, ARCHITECTURE_DRAFT, API_DRAFT, roadmap_DRAFT)
2. **Review DELETE_CANDIDATEs** with human confirmation
3. **Create archive directory structure** if approved
4. **Update code paths** if directory structure changes
5. **Remove phase-based naming** from consolidated documents

---

**Document Status:** Draft - Pending Review
