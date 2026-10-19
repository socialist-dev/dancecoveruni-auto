---
name: n8n-workflow-designer
description: Use this skill when asked to design, generate, validate, debug, or export automated workflows for n8n.
---

# n8n Workflow Designer Skill

This skill guides the Agent to design, validate, and generate production-grade n8n workflow definitions using declarative JSON schemas.

## Workflow Generation Protocol

### 1. Specification & Topology Planning
Before writing workflow JSON:
1. **Identify Nodes**: Webhooks/Triggers, Processing Nodes (Code, Set, If, Switch), and External Integrations (Discord, Telegram, Slack, Postgres).
2. **Consult Schema via MCP**: Use the `n8n-docs` MCP tool to confirm required parameters and output schema for each node type.
3. **Declare Invariants**: Never hardcode credentials; always reference n8n Credentials Manager.

### 2. Node Connection Architecture
Structure the JSON adhering to standard n8n format:
- `nodes`: Array of node definitions with `id`, `name`, `type`, `typeVersion`, `position`, and `parameters`.
- `connections`: Object mapping output pins of source nodes to input pins of destination nodes.

### 3. Verification & Deployment
1. Verify JSON syntax and ensure all referenced credentials exist.
2. If `n8n-manager` MCP is available, use `create_workflow` or `update_workflow` to deploy strictly to the local test environment.
3. Test with a mock webhook payload before enabling production triggers.
