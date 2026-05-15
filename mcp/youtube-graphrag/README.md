# LBSocial YouTube GraphRAG MCP Server

This folder contains a custom Model Context Protocol (MCP) server for querying the YouTube metadata graph built in the OpenClaw + n8n + Neo4j tutorial series.

> This server is designed for public tutorials and teaching demonstrations. It is not a production-ready GraphRAG service. For production deployment, use managed secrets, access control, logging, rate limiting, and read-only database roles.

It is a course-focused MCP server, not a general-purpose Neo4j MCP server. If you only need generic schema inspection and Cypher execution, use the official Neo4j MCP server. If you are following this tutorial series and want OpenClaw to search the YouTube GraphRAG database, use this server.

## Tutorial resources

- LBSocial website: https://www.lbsocial.net/
- LBSocial YouTube channel: https://www.youtube.com/@LBSocial
- How to Build a GraphRAG Ingestion Pipeline with OpenClaw, n8n & Neo4j: https://www.lbsocial.net/post/graphrag-ingestion-pipeline-openclaw-n8n-neo4j

The website is the main home for LBSocial tutorials, videos, and course resources. The YouTube channel hosts the public videos for OpenClaw, n8n, Neo4j, GraphRAG, and the workflow lessons that this MCP server supports.

## 中文简介

这个文件夹是 LBSocial YouTube GraphRAG 教程的定制 MCP server。前一阶段由 n8n 调用 YouTube Data API、生成 Gemini embeddings，并把 YouTube metadata 写入 Neo4j；这个 MCP server 负责让 OpenClaw 或其他 MCP client 查询这个图数据库，完成视频语义搜索、相关视频推荐和学习路径生成。

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

## Recommendation flow

The main user-facing scenario is video recommendation from OpenClaw, including OpenClaw sessions reached from Telegram:

```text
Telegram user asks a question
  -> OpenClaw receives the question
  -> OpenClaw calls this MCP server
  -> MCP server embeds the question
  -> Neo4j vector search finds relevant Video nodes
  -> Cypher graph traversal adds Channel and Topic context
  -> OpenClaw summarizes the result as video recommendations or a learning path
```

This server is not a geo-query demo and it is not a general database chat interface. It is a focused retrieval tool for recommending LBSocial YouTube tutorial videos and related learning resources from the tutorial graph.

## Semantic search + Cypher graph traversal

The v1 query pattern combines embedding-based semantic search with Cypher graph traversal:

- Semantic search uses `Video.embedding` through the `video_embeddings` Neo4j vector index.
- Cypher traversal enriches the vector matches with graph context:
  - `(:Channel)-[:PUBLISHED]->(:Video)`
  - `(:Video)-[:HAS_TOPIC]->(:Topic)`
- Returned context is source-aware and designed for OpenClaw summaries:
  - video title
  - URL
  - channel
  - topics
  - similarity score
  - short `document_text_summary`

This follows the same GraphRAG idea used in earlier LBSocial Neo4j + Gemini tutorials: first retrieve semantically relevant nodes, then use the graph to add connected context. This YouTube tutorial server does not apply geospatial filters.

## Tools

| Tool | Purpose |
|---|---|
| `get_neo4j_schema_and_indexes` | Inspect labels, relationships, sampled properties, vector indexes, and fulltext indexes. |
| `search_youtube_videos` | Search YouTube `Video` nodes with query embedding + Neo4j vector search + graph traversal. |
| `search_youtube_kg` | Backward-compatible alias for `search_youtube_videos`. |
| `get_recent_youtube_videos` | List recently updated videos for a simple connectivity demo. |
| `get_video_context` | Retrieve metadata, channel, topics, and embedded text for videos matching a title phrase. |
| `get_related_videos` | Recommend videos related to a source video using semantic similarity and shared topics. |
| `recommend_learning_path` | Search relevant videos and return structured context for OpenClaw to summarize as a learning path. |
| `run_readonly_cypher` | Run read-only Cypher after a conservative safety check. |

## Tool-first design

The main workflow uses fixed MCP tools instead of asking the LLM to freely write Cypher for every user question.

- `search_youtube_videos` is the primary tool for normal recommendation questions.
- `get_recent_youtube_videos` is useful for a simple connectivity demo.
- `get_video_context` retrieves context for a known video title phrase.
- `get_related_videos` recommends follow-up videos from a known source video.
- `recommend_learning_path` returns ordered video matches with guidance for OpenClaw to summarize a learning path.
- `run_readonly_cypher` is an advanced/debugging tool, not the main user-facing entrypoint.

Fixed tools keep the public tutorial, student reproduction, and Telegram demo more stable. The server still uses Cypher internally, but the tested query patterns live inside the MCP tools.

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

## Tutorial environment

This tutorial project targets:

- Google Cloud VM for the OpenClaw runtime.
- Python 3.10 or newer.
- `uv` for local dependency sync and execution.
- Neo4j AuraDB with the tutorial `Channel` / `Video` / `Topic` graph.
- Gemini embeddings stored as 768-dimensional vectors on `Video.embedding`.
- FastMCP 3.x for stdio MCP integration.

Create a local environment file:

```bash
cp .env.example .env
nano .env
```

Fill in your Neo4j AuraDB and Gemini credentials. Do not commit real credentials.

The MCP server does not call the YouTube Data API directly. If you are rebuilding the n8n ingestion workflow, keep the YouTube API key in your n8n credentials or ingestion-side environment, not in this MCP server `.env` file.

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

## Local testing clients

This folder includes small local MCP clients for testing before registering the server with OpenClaw. They start `server.py` over stdio, call the MCP tools, and print the results. Run them from this folder after `uv sync` and after creating `.env`.

| File | Use when | What it does |
|---|---|---|
| `local_client_test.py` | You want one command to verify the whole local setup. | Calls schema inspection, recent videos, semantic search, learning-path retrieval, and read-only Cypher. |
| `local_ask.py` | You want to type questions like a user. | Prompts for natural-language questions and returns video recommendations from `search_youtube_videos`. |
| `local_tool_menu.py` | You want to test one MCP tool at a time. | Shows a numbered menu for all exposed tools, including related videos, title context, and read-only Cypher. |

Run a full smoke test:

```bash
uv run python local_client_test.py --question "OpenClaw n8n Neo4j GraphRAG" --top-k 3
```

Ask questions interactively:

```bash
uv run python local_ask.py
```

Try every exposed MCP tool from a menu:

```bash
uv run python local_tool_menu.py
```

The local clients are for development and tutorial testing only. OpenClaw and other MCP clients should register `server.py`, not the `local_*.py` helper scripts.

The tools use `@mcp.tool(output_schema=None)` so FastMCP 3.x clients receive JSON content without strict structured-output validation errors. This keeps the local client tests and stdio MCP integration aligned.

## Use with Claude Desktop or another MCP client

OpenClaw is the main tutorial client, but the server can also run from any stdio MCP client that supports custom servers. For Claude Desktop, add an entry like this to your MCP configuration and adjust the path for your machine:

```json
{
  "mcpServers": {
    "lbsocial-youtube-graphrag": {
      "command": "uv",
      "args": [
        "--directory",
        "/absolute/path/to/openclaw-n8n-neo4j-workflows/mcp/youtube-graphrag",
        "run",
        "python",
        "server.py"
      ]
    }
  }
}
```

The server still needs a local `.env` file in `mcp/youtube-graphrag/` with Neo4j and embedding-provider credentials.

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

```text
Use get_related_videos for video AN2WL_jBoY8 and suggest what to watch next.
```

```text
Use recommend_learning_path for: I want to learn how OpenClaw works with n8n, Neo4j, MCP, and GraphRAG.
Return a practical watching order with video titles and URLs.
```

```text
Use the youtube_graphrag_cypher_prompt to decide whether this question should use a fixed tool or read-only Cypher:
How many videos are connected to each topic?
```

## MCP prompt template for Cypher guidance

The v1.1 server also exposes an MCP prompt template:

```text
youtube_graphrag_cypher_prompt(question)
```

This prompt does not execute database queries. It guides OpenClaw or another MCP client on how to work safely with this graph:

- Use the current `Channel` / `Video` / `Topic` schema.
- Prefer `search_youtube_videos` for ordinary video recommendation questions.
- Prefer `recommend_learning_path` for learning-path questions.
- Prefer `get_related_videos` when the user starts from a known video.
- Generate only read-only Cypher for statistical or analytical questions.
- Do not generate `CREATE`, `MERGE`, `DELETE`, `SET`, schema changes, or admin operations.
- Use `run_readonly_cypher` only for advanced read-only inspection or analysis.

The fixed tools remain the main path for the public tutorial and Telegram demo. The prompt template is for guided advanced analysis, not free-form database mutation.

## Related videos and learning paths

The v1.1 recommendation tools are still Video-level GraphRAG tools:

```text
get_related_videos(video_id)
recommend_learning_path(question)
```

`get_related_videos` combines semantic similarity from the `video_embeddings` vector index with shared `Topic` nodes from the graph. It excludes the source video and returns source-aware related video records.

`recommend_learning_path` reuses semantic video search and returns an instruction for OpenClaw to turn the ordered matches into a practical viewing sequence.

Transcript chunks, timestamps, `TranscriptChunk`, `NEXT` relationships, course/module nodes, and richer AI Tutor behavior are future v2 work.

## Security notes

- Do not commit `.env` or real credentials.
- Use a read-only Neo4j credential when your Neo4j tier supports it.
- Keep `run_readonly_cypher` conservative; it blocks common write/admin keywords.
- For production, use Google Secret Manager or Cloud Run secrets instead of local `.env` files.
- Use YouTube data only in ways that follow the YouTube API Services Terms of Service and your own data-retention policy.
- Do not include private institutional materials, internal service URLs, or non-public workflow credentials in public tutorial commits.

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
