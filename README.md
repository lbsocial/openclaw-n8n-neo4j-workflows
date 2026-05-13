# openclaw-n8n-neo4j-workflows
Public OpenClaw, n8n, Neo4j, and GraphRAG workflow examples for AI automation tutorials.

## LBSocial links

- Website: https://www.lbsocial.net/
- YouTube channel: https://www.youtube.com/@LBSocial

LBSocial is the home for the tutorials, videos, and course resources behind these examples. The YouTube channel hosts the public videos for OpenClaw, n8n, Neo4j, GraphRAG, and related workflow lessons.

## Current resources

- [`mcp/youtube-graphrag`](./mcp/youtube-graphrag/): a custom MCP server for the OpenClaw + n8n + YouTube metadata + Gemini embedding + Neo4j tutorial series.

The YouTube GraphRAG MCP server is designed for the tutorial schema:

```text
(:Channel)-[:PUBLISHED]->(:Video)-[:HAS_TOPIC]->(:Topic)
```

It searches `Video.embedding` through the `video_embeddings` Neo4j vector index and returns video, channel, topic, and source context for OpenClaw to summarize.

If you need a generic Neo4j MCP server, use the official Neo4j MCP project. This repository focuses on course-ready workflow examples that students can follow and adapt.
