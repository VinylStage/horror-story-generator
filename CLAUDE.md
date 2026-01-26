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
