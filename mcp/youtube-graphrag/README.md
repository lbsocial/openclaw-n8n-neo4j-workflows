# LBSocial YouTube GraphRAG MCP Server

This folder contains a custom Model Context Protocol (MCP) server for searching an LBSocial YouTube knowledge graph stored in Neo4j.

It is designed for the OpenClaw + n8n + Neo4j tutorial series.

## What this MCP server does

The server exposes three tools:

| Tool | Purpose |
|---|---|
| `search_youtube_kg` | Semantic GraphRAG search over transcript chunks using a Neo4j vector index. |
| `get_video_context` | Retrieve chunks and topics for videos matching a title phrase. |
| `run_readonly_cypher` | Run read-only Cypher after a conservative safety check. |

The main tutorial tool is `search_youtube_kg`.

It takes a natural-language question, generates an embedding, searches a Neo4j vector index, expands the matched chunks to connected videos and topics, and returns structured results for OpenClaw to summarize.

```text
OpenClaw
  -> custom MCP server
  -> embedding provider: OpenAI or Gemini
  -> Neo4j vector index
  -> Video / Chunk / Topic graph context
  -> OpenClaw summary
```

## Setup

From this folder:

```bash
uv sync
```

Create a local environment file:

```bash
cp .env.example .env
nano .env
```

Do not commit real credentials.

## Required Neo4j graph pattern

The default schema assumes this pattern:

```cypher
(:Video)-[:HAS_CHUNK]->(:Chunk)-[:MENTIONS_TOPIC]->(:Topic)
```

The `Chunk` node should have an embedding property indexed by a Neo4j vector index named:

```text
chunk_embedding_index
```

The default returned properties are:

```text
Video.title
Video.url
Chunk.start_time
Chunk.end_time
Chunk.text
Topic.name
```

If your actual graph uses different names, update the variables in `.env`.

## Run locally

```bash
uv run python server.py
```

The process may appear to wait silently. That is normal for a stdio MCP server because it waits for an MCP client such as OpenClaw.

## Register with OpenClaw

Create a wrapper script on the VM:

```bash
nano ~/openclaw-n8n-neo4j-workflows/mcp/youtube-graphrag/run.sh
```

Paste:

```bash
#!/usr/bin/env bash
set -euo pipefail

cd "$HOME/openclaw-n8n-neo4j-workflows/mcp/youtube-graphrag"
exec uv run python server.py
```

Then:

```bash
chmod +x ~/openclaw-n8n-neo4j-workflows/mcp/youtube-graphrag/run.sh
```

Register it:

```bash
openclaw mcp set lbsocial-youtube-graphrag "{
  \"command\": \"/bin/bash\",
  \"args\": [
    \"$HOME/openclaw-n8n-neo4j-workflows/mcp/youtube-graphrag/run.sh\"
  ]
}"
```

Check:

```bash
openclaw mcp list
openclaw mcp show lbsocial-youtube-graphrag --json
openclaw gateway restart
```

## Example OpenClaw prompts

```text
Use the lbsocial-youtube-graphrag MCP server to search my YouTube knowledge graph for videos about OpenClaw, n8n, and Neo4j MCP. Return video titles, timestamps, URLs, topics, and a short summary.
```

```text
Use search_youtube_kg to find the top 5 chunks related to semantic search with Neo4j. Summarize the result as a learning path.
```

```text
Use get_video_context to retrieve chunks and topics for the video whose title contains OpenClaw.
```

## Security notes

- Do not commit `.env` or real credentials.
- Use a read-only Neo4j credential when your Neo4j tier supports it.
- Keep `run_readonly_cypher` conservative; it blocks common write/admin keywords.
- For production, use Google Secret Manager or Cloud Run secrets instead of local `.env` files.

## Relationship to Gemini Live

This MCP server is for OpenClaw. Gemini Live should not call OpenClaw directly.

For the LBSocial Wix / Cloud Run app, reuse the same GraphRAG retrieval logic behind a Gemini Live function/tool declaration, for example:

```text
Gemini Live -> Cloud Run tool function -> GraphRAG retrieval -> Neo4j
```

The shared concept is the retrieval function:

```text
search_youtube_kg(question, top_k)
```
