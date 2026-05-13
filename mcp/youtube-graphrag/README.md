# LBSocial YouTube GraphRAG MCP Server

This folder contains a custom Model Context Protocol (MCP) server for querying the YouTube metadata graph built in the OpenClaw + n8n + Neo4j tutorial series.

It is a course-focused MCP server, not a general-purpose Neo4j MCP server. If you only need generic schema inspection and Cypher execution, use the official Neo4j MCP server. If you are following this tutorial series and want OpenClaw to search the YouTube GraphRAG database, use this server.

## Tutorial resources

- LBSocial website: https://www.lbsocial.net/
- LBSocial YouTube channel: https://www.youtube.com/@LBSocial

The website is the main home for LBSocial tutorials, videos, and course resources. The YouTube channel hosts the public videos for OpenClaw, n8n, Neo4j, GraphRAG, and the workflow lessons that this MCP server supports.

## What this server does

The n8n workflow handles ingestion:

```text
YouTube URL
  -> YouTube Data API metadata
  -> document_text
  -> Gemini embedding
  -> Neo4j AuraDB
```

This MCP server handles querying:

```text
OpenClaw
  -> LBSocial YouTube GraphRAG MCP server
  -> Gemini query embedding
  -> Neo4j vector search
  -> Channel / Video / Topic graph context
  -> OpenClaw summary or learning path
```

## Tools

| Tool | Purpose |
|---|---|
| `get_neo4j_schema_and_indexes` | Inspect labels, relationships, sampled properties, vector indexes, and fulltext indexes. |
| `search_youtube_videos` | Search YouTube `Video` nodes with query embedding + Neo4j vector search + graph traversal. |
| `search_youtube_kg` | Backward-compatible alias for `search_youtube_videos`. |
| `get_recent_youtube_videos` | List recently updated videos for a simple connectivity demo. |
| `get_video_context` | Retrieve metadata, channel, topics, and embedded text for videos matching a title phrase. |
| `run_readonly_cypher` | Run read-only Cypher after a conservative safety check. |

## Expected graph schema

This server expects the tutorial graph:

```cypher
(:Channel)-[:PUBLISHED]->(:Video)-[:HAS_TOPIC]->(:Topic)
```

The default vector search expects:

```text
Video.embedding
video_embeddings
768 dimensions
cosine similarity
```

The default returned properties are:

```text
Video.video_id
Video.title
Video.url
Video.published_at
Video.document_text
Channel.channel_title
Topic.name
```

You can rename labels, relationships, properties, and the vector index through `.env`, but the server is still designed around this Video / Channel / Topic tutorial model.

## Official Neo4j MCP vs this server

The official Neo4j MCP server is the right choice when you want a generic bridge from an MCP client to any Neo4j database. It can inspect schema and run Cypher, and it is useful for broad database work.

This tutorial server is intentionally narrower:

- It uses the same Gemini embedding setup as the n8n ingestion lesson.
- It knows the YouTube metadata graph shape.
- It returns source-aware video results that OpenClaw can summarize into recommendations or learning paths.
- It gives students a small, readable example they can modify after following the course.

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

Fill in your Neo4j AuraDB and Gemini credentials. Do not commit real credentials.

## Create the vector index

If the n8n workflow stores 768-dimensional Gemini embeddings on `Video.embedding`, create the index:

```cypher
CREATE VECTOR INDEX video_embeddings IF NOT EXISTS
FOR (v:Video) ON (v.embedding)
OPTIONS {
  indexConfig: {
    `vector.dimensions`: 768,
    `vector.similarity_function`: 'cosine'
  }
};
```

Check it:

```cypher
SHOW INDEXES
YIELD name, type, state, labelsOrTypes, properties
WHERE name = "video_embeddings"
RETURN name, type, state, labelsOrTypes, properties;
```

## Run locally

```bash
uv run python server.py
```

The process may appear to wait silently. That is normal for a stdio MCP server because it waits for an MCP client such as OpenClaw, VS Code, Gemini CLI, or Claude Desktop.

## Register with OpenClaw on the VM

Create a wrapper script on the Google Cloud VM:

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
Use the lbsocial-youtube-graphrag MCP server to inspect the Neo4j schema and indexes.
```

```text
Use search_youtube_videos to find the top 5 videos related to OpenClaw, n8n, Neo4j MCP, and GraphRAG. Return video titles, URLs, topics, and a short summary.
```

```text
Use get_recent_youtube_videos to list the most recently updated videos in the graph.
```

```text
Use get_video_context to retrieve context for videos whose title contains OpenClaw.
```

## Security notes

- Do not commit `.env` or real credentials.
- Use a read-only Neo4j credential when your Neo4j tier supports it.
- Keep `run_readonly_cypher` conservative; it blocks common write/admin keywords.
- For production, use Google Secret Manager or Cloud Run secrets instead of local `.env` files.

## Relationship to Gemini Live

This MCP server is for OpenClaw and other MCP clients. Gemini Live should not call OpenClaw directly.

For the LBSocial Wix / Cloud Run app, reuse the same retrieval idea behind a Gemini Live function/tool declaration:

```text
Gemini Live -> Cloud Run tool function -> GraphRAG retrieval -> Neo4j
```

The shared concept is the retrieval function:

```text
search_youtube_videos(question, top_k)
```
