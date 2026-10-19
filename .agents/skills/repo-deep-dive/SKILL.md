---
name: repo-deep-dive
description: Use this skill when tasked with researching, reverse-engineering, mapping, or extracting modules from an unfamiliar open-source codebase or GitHub repository.
---

# Open-Source Repo Deep Dive & Extraction Skill

This skill guides the Agent to methodically explore, analyze, and extract modules from a foreign codebase while minimizing context window consumption.

## 4-Layer Exploration Strategy

### Layer 1: Metadata & Topology Mapping (Token-Light)
1. Read package configuration manifests (`package.json`, `pyproject.toml`, `Cargo.toml`, `go.mod`).
2. Identify: Core tech stack, primary dependencies, build scripts, and test runners.
3. List high-level directory structure using directory listing commands. Do not read deep source files yet.

### Layer 2: Entrypoint & Execution Tracing
1. Locate primary application entrypoints (`main.py`, `index.ts`, `cmd/server/main.go`, `App.tsx`).
2. Trace the core execution flow from initialization to primary request or rendering pipeline.
3. Document high-level architecture with a sequence diagram.

### Layer 3: Surgical Module Isolation
1. Identify target modules or algorithms to reuse or adapt.
2. Map immediate internal dependencies and required external libraries.
3. Extract core interfaces and types into an isolated specification document.

### Layer 4: Integration, Adaptation & Verification
1. Create a dedicated isolated test suite for the extracted module.
2. Clean up coupling and replace extraneous dependencies with local interfaces or mocks.
3. Run verification tests to ensure the module operates independently before final integration.
