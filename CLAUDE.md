# Claude Code Work Rules

> You are Claude Code, acting as an autonomous contributor to this repository.
>
> **These rules are NON-NEGOTIABLE.**

---

## 0. Pre-Work Obligations (Mandatory)

### 0.1 Task Understanding

Before writing or modifying ANY code or document, you MUST:

- Read and understand the Issue content and relevant repository context
- Identify scope, constraints, and risks

### 0.2 Task List Creation

You MUST create a clear, step-by-step task list BEFORE starting work.

The task list MUST include:

- What will be changed
- What will NOT be changed
- Testing approach
- Documentation impact

### 0.3 User Confirmation Gate

You MUST NOT start implementation until:

- The task list is presented to the user
- Explicit user confirmation or agreement is received

> **If confirmation is missing or ambiguous, STOP.**

---

## 1. Issue First Policy

### 1.1 Mandatory Issue

- You MUST NOT work without an existing GitHub Issue.
- If a TODO, problem, or improvement is discovered:
  - **STOP immediately**
  - Create or request creation of a GitHub Issue first

---

## 2. Branching Rules

### 2.1 Branch Origin

- You MUST create a branch from `develop`.

### 2.2 Branch Naming Convention

Branch naming MUST follow:

```
<type>/<issue-number>-short-description
```

**Allowed types:** `feat` | `fix` | `refactor` | `tech` | `docs`

### 2.3 Main Branch Protection

- You MUST **NEVER** work directly on `main`.
- You MUST NOT touch `main` unless there is an explicit, exceptional user instruction.

---

## 3. Commit Rules

### 3.1 Conventional Commits

- Every commit MUST follow [Conventional Commits](https://www.conventionalcommits.org/).

### 3.2 Issue Tagging

- Every commit MUST include the Issue number.

```
feat: add router abstraction (#123)
```

---

## 4. Pull Request Rules

### 4.1 PR Target

- ALL PRs MUST target `develop`.
- You MUST merge work into `develop` first.

### 4.2 PR Metadata Requirements

- PR title MUST include `(#<issue-number>)`
- PR body MUST include ONE of:
  - `Fixes #<issue-number>`
  - `Refs #<issue-number>`

### 4.3 Main Branch Exception

- PRs targeting `main` are **FORBIDDEN** unless explicitly instructed by the user for release-related operations.

### 4.4 Release PR Title Format

When creating a PR from `develop` to `main` (release PR):

- PR title MUST follow [Conventional Commits](https://www.conventionalcommits.org/) format.
- This is CRITICAL for `release-please` to correctly parse commits and generate releases.

**Format:**

```
<type>: <description> (#<pr-number>)
```

**Valid examples:**

```
feat: implement scheduler API integration (#98)
fix: resolve authentication timeout issue (#102)
docs: update API documentation for v1.6.0 (#105)
```

**Invalid examples:**

```
❌ Develop (#98)
❌ Merge develop into main
❌ Release v1.6.0
```

**Allowed types:** `feat` | `fix` | `docs` | `refactor` | `tech` | `chore` | `ci` | `test` | `perf`

> **Failure to follow this format will cause `release-please` to skip automatic version bumping and release creation.**

---

## 5. Validation Awareness

### 5.1 CI as Authority

- Assume GitHub Actions validation is strict and authoritative.
- If validation fails:
  1. You MUST fix the issues
  2. Re-run validation
  3. Only then request review

---

## 6. Documentation Obligations

### 6.1 Mandatory Documentation Update

- If a technical change is made:
  - You MUST update the relevant documentation.
- If no relevant documentation exists:
  - You MUST create new documentation.

### 6.2 Documentation Familiarization

- If you are unsure how to document something:
  - Read existing related documents first
  - Follow established tone, structure, and conventions
- You MUST NOT guess documentation structure in isolation.

### 6.3 Documentation Scope

Documentation updates are REQUIRED for:

- Logic changes
- Behavior changes
- Configuration changes
- Operational impact

### 6.4 Change Impact Checklist (Mandatory)

When making code changes, you MUST verify and update ALL of the following layers.
Skipping any layer is a common source of bugs (e.g., KeyError from mismatched dict keys, Swagger not rendering schemas).

#### Layer 1: Source Code

| Target | Check |
|--------|-------|
| **Function/method signatures** | Parameter names, type hints, return types |
| **Function/method call sites** | All callers passing renamed keyword arguments |
| **Dict key access** | `dict["old_key"]` → `dict["new_key"]` across ALL consumers |
| **Variable names** | Local variables, class attributes, properties |
| **Error messages / string literals** | User-facing text, log messages, exception messages |
| **Backward-compat aliases** | Add `old_name = new_name` aliases if needed |

#### Layer 2: API / Swagger (FastAPI)

| Target | Check |
|--------|-------|
| **Router endpoint functions** | `response_model`, `status_code`, docstrings |
| **Pydantic schema classes** | Field names, `Field(description=...)`, class docstrings |
| **`main.py` tag metadata** | `tags_metadata` descriptions shown in Swagger UI |
| **Router → Service call mapping** | Ensure dict keys from service match what router reads |
| **Request body visibility** | Typed Pydantic params (NOT raw `Request`) so Swagger renders body schema |

> **Rule**: NEVER use raw `request: Request` for JSON body parsing. Always use typed Pydantic models so Swagger auto-generates documentation. If multiple input shapes are needed, create separate endpoints (e.g., `POST /tasks` + `POST /tasks/batch`).

#### Layer 3: Tests

| Target | Check |
|--------|-------|
| **Test method names** | Reflect new terminology |
| **Test endpoint paths** | Match actual router paths |
| **Mock return values** | Dict keys and attribute names match new code |
| **Auth / integration tests** | Endpoint paths used in cross-cutting tests |
| **Fixture names** | `create_job` → `create_task` etc. |

#### Layer 4: Documentation Files

| Target | Check |
|--------|-------|
| **`docs/core/API.md`** | Endpoint paths, request/response examples, field names |
| **`docs/task-scheduler/*.md`** | Domain model, design docs, test plans |
| **Module-level docstrings** | Top-of-file `"""..."""` in every changed module |
| **Inline comments** | Comments referencing old names |
| **README / CLAUDE.md** | If conventions or workflows changed |

#### Layer 5: Database / Persistence

| Target | Check |
|--------|-------|
| **SQL table/column names** | Migration code for renaming |
| **Row-to-entity mapping** | `row["old_col"]` → `row["new_col"]` |
| **DB schema comments** | Document backward-compat decisions |

> **Verification**: After all changes, run `grep -ri "old_term"` across `src/` and `tests/` to catch missed references. Only backward-compat aliases and DB migration code should remain.

---

## 7. Testing Rules

### 7.1 Mandatory Testing

- After development is complete, you MUST run tests.

### 7.2 Large or Risky Changes

- If logic changes are large, risky, or system-wide:
  - You MUST request explicit user permission
  - BEFORE running real, integration, or long-running tests

### 7.3 Test Reporting

- Test results MUST be summarized in the PR description.

---

## 8. Forbidden Actions

| Action | Status |
|--------|--------|
| Direct commits to `main` or `develop` | **FORBIDDEN** |
| Version number changes | **FORBIDDEN** |
| Manual changelog edits | **FORBIDDEN** |
| Untracked TODO comments | **FORBIDDEN** |
| Bypassing user confirmation gates | **FORBIDDEN** |

---

## 9. Completion Rules

When work is complete, you MUST:

- [ ] Ensure all validations pass
- [ ] Ensure documentation is updated or created
- [ ] Summarize changes clearly in the PR
- [ ] Close the Issue if appropriate

---

## 10. Rule Priority

> **If ANY instruction conflicts with these rules, THESE RULES TAKE ABSOLUTE PRIORITY.**
