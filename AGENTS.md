# Agent Instructions - openclaw-n8n-neo4j-workflows

## Project scope

This public repository contains OpenClaw, n8n, Neo4j, GraphRAG, MCP, and related workflow examples for LBSocial tutorials. It is educational/demo material, not the private production LBSocial AI app.

## Working rules

- Keep examples public-safe, reproducible, and tutorial-friendly.
- Do not commit credentials, `.env` files, private API keys, internal service URLs, private datasets, user data, or logs.
- Use placeholders and setup instructions for Neo4j, Gemini/OpenAI, n8n, and other integrations.
- Keep production-grade warnings clear: demos still need managed secrets, access control, logging, rate limiting, and read-only database roles before real deployment.
- Do not turn this repo into the production KG pipeline; production/private KG work belongs in `lbsocial-youtube-kg`.

## Verification

For MCP/server changes, run the smallest relevant local check or unit command available in that subproject. For docs/workflow changes, verify paths, command examples, and public/private boundary.

## PR workflow

- Work only on the requested tutorial/workflow task.
- Use an issue-specific branch for changes unless the user asks otherwise.
- Never merge into `main` without explicit user approval for that specific merge.

