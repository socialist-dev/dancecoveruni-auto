---
name: spec-first-feature
description: Use this skill when tasked with designing, planning, or implementing a new software feature following Spec-Driven Development (SDD) and Test-First standards.
---

# Spec-First Feature Implementation Skill

This skill guides the Agent to build new features using Spec-Driven Development (SDD) and Test-Driven Development (TDD) to prevent architectural regressions and scope creep.

## Execution Workflow

### Step 1: Author Feature Specification
Before creating implementation files, draft an architectural specification at `specs/<feature-name>.md`:
1. **Feature Objective**: Define input/output boundaries, performance thresholds, and operational scope.
2. **Data Contracts**: Explicitly declare interfaces, data models, and schemas (e.g., TypeScript types, Pydantic models).
3. **Acceptance Criteria**: Provide an unambiguous checklist of verifiable conditions.

### Step 2: Test Fixtures & Unit Tests (Red)
1. Author test suites at `tests/test_<feature-name>.*`.
2. Cover happy path, edge cases, boundary conditions, and invalid inputs.
3. Execute the test command via terminal to confirm expected failure (Red phase).

### Step 3: Minimal Implementation (Green)
1. Write minimal operational code to satisfy data contracts.
2. Implement just enough logic to transition all failing tests to passing (Green phase).
3. Re-run tests via terminal to verify successful completion.

### Step 4: Refactor & Automated Quality Audit
1. Refactor logic for efficiency and readability while maintaining regression safety.
2. Run the project linter and typechecker.
3. Confirm 100% test suite pass rate before notifying the user.
