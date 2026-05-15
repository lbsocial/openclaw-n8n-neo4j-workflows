# openclaw-n8n-neo4j-workflows
Public OpenClaw, n8n, Neo4j, and GraphRAG workflow examples for AI automation tutorials.

> This repository is designed for public tutorials and teaching demonstrations. It is not a production-ready GraphRAG platform. For production deployment, use managed secrets, access control, logging, rate limiting, and read-only database roles.

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

## 中文简介

这个仓库是 LBSocial OpenClaw、n8n、Neo4j 和 GraphRAG 教程系列的公开配套代码。当前重点是一个定制的 YouTube GraphRAG MCP server：n8n 负责把 YouTube metadata、document text 和 Gemini embeddings 写入 Neo4j，MCP server 负责让 OpenClaw 查询图数据库，做语义搜索、相关视频推荐和学习路径生成。

## Compliance notes

- Use this repository for educational tutorials and demonstrations.
- Follow the YouTube API Services Terms of Service and the usage guidelines for any platform or dataset you connect.
- Do not commit real credentials, private API keys, internal service URLs, or non-public institutional materials.
