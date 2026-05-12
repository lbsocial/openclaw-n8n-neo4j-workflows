"""LBSocial YouTube GraphRAG MCP server.

This MCP server exposes domain-specific tools for searching a Neo4j-based
YouTube knowledge graph. It is designed for OpenClaw tutorials, but the core
logic can also be reused by a Gemini Live / Cloud Run tool adapter.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any, Literal

from dotenv import load_dotenv
from fastmcp import FastMCP
from neo4j import GraphDatabase
from openai import OpenAI

try:
    from google import genai
except Exception:  # pragma: no cover - optional provider
    genai = None

load_dotenv()


EmbeddingProvider = Literal["openai", "gemini"]


@dataclass(frozen=True)
class Settings:
    neo4j_uri: str
    neo4j_username: str
    neo4j_password: str
    neo4j_database: str
    embedding_provider: EmbeddingProvider
    openai_embedding_model: str
    gemini_embedding_model: str
    vector_index: str
    chunk_label: str
    video_label: str
    topic_label: str
    video_to_chunk_rel: str
    chunk_to_topic_rel: str
    chunk_text_property: str
    chunk_start_property: str
    chunk_end_property: str
    video_title_property: str
    video_url_property: str
    topic_name_property: str


def env(name: str, default: str | None = None) -> str:
    value = os.getenv(name, default)
    if value is None or value == "":
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def load_settings() -> Settings:
    provider = env("EMBEDDING_PROVIDER", "openai").lower()
    if provider not in {"openai", "gemini"}:
        raise RuntimeError("EMBEDDING_PROVIDER must be either 'openai' or 'gemini'.")

    return Settings(
        neo4j_uri=env("NEO4J_URI"),
        neo4j_username=env("NEO4J_USERNAME"),
        neo4j_password=env("NEO4J_PASSWORD"),
        neo4j_database=env("NEO4J_DATABASE", "neo4j"),
        embedding_provider=provider,  # type: ignore[arg-type]
        openai_embedding_model=env("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"),
        gemini_embedding_model=env("GEMINI_EMBEDDING_MODEL", "text-embedding-004"),
        vector_index=env("YOUTUBE_CHUNK_VECTOR_INDEX", "chunk_embedding_index"),
        chunk_label=env("YOUTUBE_CHUNK_LABEL", "Chunk"),
        video_label=env("YOUTUBE_VIDEO_LABEL", "Video"),
        topic_label=env("YOUTUBE_TOPIC_LABEL", "Topic"),
        video_to_chunk_rel=env("YOUTUBE_VIDEO_TO_CHUNK_REL", "HAS_CHUNK"),
        chunk_to_topic_rel=env("YOUTUBE_CHUNK_TO_TOPIC_REL", "MENTIONS_TOPIC"),
        chunk_text_property=env("YOUTUBE_CHUNK_TEXT_PROPERTY", "text"),
        chunk_start_property=env("YOUTUBE_CHUNK_START_PROPERTY", "start_time"),
        chunk_end_property=env("YOUTUBE_CHUNK_END_PROPERTY", "end_time"),
        video_title_property=env("YOUTUBE_VIDEO_TITLE_PROPERTY", "title"),
        video_url_property=env("YOUTUBE_VIDEO_URL_PROPERTY", "url"),
        topic_name_property=env("YOUTUBE_TOPIC_NAME_PROPERTY", "name"),
    )


settings = load_settings()
mcp = FastMCP("lbsocial-youtube-graphrag")
driver = GraphDatabase.driver(
    settings.neo4j_uri,
    auth=(settings.neo4j_username, settings.neo4j_password),
)


def _safe_identifier(value: str, label: str) -> str:
    """Allow only simple Neo4j labels, relationship types, properties, and index names."""
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
        raise RuntimeError(f"Unsafe {label}: {value!r}")
    return value


def _embed_with_openai(question: str) -> list[float]:
    client = OpenAI(api_key=env("OPENAI_API_KEY"))
    response = client.embeddings.create(
        model=settings.openai_embedding_model,
        input=question,
    )
    return response.data[0].embedding


def _embed_with_gemini(question: str) -> list[float]:
    if genai is None:
        raise RuntimeError("google-genai is not available. Install dependencies with `uv sync`.")
    client = genai.Client(api_key=env("GEMINI_API_KEY"))
    response = client.models.embed_content(
        model=settings.gemini_embedding_model,
        contents=question,
    )
    embedding = response.embeddings[0].values
    return list(embedding)


def embed_question(question: str) -> list[float]:
    if settings.embedding_provider == "openai":
        return _embed_with_openai(question)
    if settings.embedding_provider == "gemini":
        return _embed_with_gemini(question)
    raise RuntimeError(f"Unsupported embedding provider: {settings.embedding_provider}")


def _youtube_search_cypher() -> str:
    vector_index = _safe_identifier(settings.vector_index, "vector index")
    chunk_label = _safe_identifier(settings.chunk_label, "chunk label")
    video_label = _safe_identifier(settings.video_label, "video label")
    topic_label = _safe_identifier(settings.topic_label, "topic label")
    video_to_chunk_rel = _safe_identifier(settings.video_to_chunk_rel, "video-to-chunk relationship")
    chunk_to_topic_rel = _safe_identifier(settings.chunk_to_topic_rel, "chunk-to-topic relationship")
    chunk_text_property = _safe_identifier(settings.chunk_text_property, "chunk text property")
    chunk_start_property = _safe_identifier(settings.chunk_start_property, "chunk start property")
    chunk_end_property = _safe_identifier(settings.chunk_end_property, "chunk end property")
    video_title_property = _safe_identifier(settings.video_title_property, "video title property")
    video_url_property = _safe_identifier(settings.video_url_property, "video URL property")
    topic_name_property = _safe_identifier(settings.topic_name_property, "topic name property")

    return f"""
    CALL db.index.vector.queryNodes($vector_index, $top_k, $query_embedding)
    YIELD node AS chunk, score

    MATCH (video:{video_label})-[:{video_to_chunk_rel}]->(chunk:{chunk_label})
    OPTIONAL MATCH (chunk)-[:{chunk_to_topic_rel}]->(topic:{topic_label})

    RETURN
      video.{video_title_property} AS video_title,
      video.{video_url_property} AS video_url,
      chunk.{chunk_start_property} AS start_time,
      chunk.{chunk_end_property} AS end_time,
      chunk.{chunk_text_property} AS matched_text,
      collect(DISTINCT topic.{topic_name_property}) AS topics,
      score
    ORDER BY score DESC
    """


def _video_context_cypher() -> str:
    chunk_label = _safe_identifier(settings.chunk_label, "chunk label")
    video_label = _safe_identifier(settings.video_label, "video label")
    topic_label = _safe_identifier(settings.topic_label, "topic label")
    video_to_chunk_rel = _safe_identifier(settings.video_to_chunk_rel, "video-to-chunk relationship")
    chunk_to_topic_rel = _safe_identifier(settings.chunk_to_topic_rel, "chunk-to-topic relationship")
    chunk_text_property = _safe_identifier(settings.chunk_text_property, "chunk text property")
    chunk_start_property = _safe_identifier(settings.chunk_start_property, "chunk start property")
    chunk_end_property = _safe_identifier(settings.chunk_end_property, "chunk end property")
    video_title_property = _safe_identifier(settings.video_title_property, "video title property")
    video_url_property = _safe_identifier(settings.video_url_property, "video URL property")
    topic_name_property = _safe_identifier(settings.topic_name_property, "topic name property")

    return f"""
    MATCH (video:{video_label})
    WHERE toLower(toString(video.{video_title_property})) CONTAINS toLower($video_title)

    OPTIONAL MATCH (video)-[:{video_to_chunk_rel}]->(chunk:{chunk_label})
    OPTIONAL MATCH (chunk)-[:{chunk_to_topic_rel}]->(topic:{topic_label})

    RETURN
      video.{video_title_property} AS video_title,
      video.{video_url_property} AS video_url,
      collect(DISTINCT {{
        start_time: chunk.{chunk_start_property},
        end_time: chunk.{chunk_end_property},
        text: chunk.{chunk_text_property}
      }}) AS chunks,
      collect(DISTINCT topic.{topic_name_property}) AS topics
    LIMIT $limit
    """


@mcp.tool()
def search_youtube_kg(question: str, top_k: int = 5) -> dict[str, Any]:
    """Search the LBSocial YouTube knowledge graph using vector-based GraphRAG.

    Use this tool when a user asks for LBSocial videos, tutorials, timestamps,
    topics, or learning-path material related to OpenClaw, n8n, Neo4j, GraphRAG,
    Gemini, cloud data workflows, or AI/data-science education.
    """
    if top_k < 1 or top_k > 20:
        raise ValueError("top_k must be between 1 and 20.")

    query_embedding = embed_question(question)

    with driver.session(database=settings.neo4j_database) as session:
        records = session.run(
            _youtube_search_cypher(),
            vector_index=settings.vector_index,
            top_k=top_k,
            query_embedding=query_embedding,
        )
        matches = [dict(record) for record in records]

    return {
        "question": question,
        "top_k": top_k,
        "embedding_provider": settings.embedding_provider,
        "vector_index": settings.vector_index,
        "matches": matches,
    }


@mcp.tool()
def get_video_context(video_title: str, limit: int = 5) -> dict[str, Any]:
    """Retrieve chunks and topics for videos whose titles match a text phrase."""
    if limit < 1 or limit > 20:
        raise ValueError("limit must be between 1 and 20.")

    with driver.session(database=settings.neo4j_database) as session:
        records = session.run(
            _video_context_cypher(),
            video_title=video_title,
            limit=limit,
        )
        results = [dict(record) for record in records]

    return {
        "video_title_search": video_title,
        "limit": limit,
        "results": results,
    }


def _is_safe_read_query(cypher: str) -> bool:
    blocked = [
        r"\bCREATE\b",
        r"\bMERGE\b",
        r"\bDELETE\b",
        r"\bDETACH\b",
        r"\bSET\b",
        r"\bREMOVE\b",
        r"\bDROP\b",
        r"\bLOAD\s+CSV\b",
        r"\bCALL\s+dbms\.",
    ]
    return not any(re.search(pattern, cypher, re.IGNORECASE) for pattern in blocked)


@mcp.tool()
def run_readonly_cypher(cypher: str, limit: int = 20) -> dict[str, Any]:
    """Run a manually supplied read-only Cypher query after a conservative safety check."""
    if not _is_safe_read_query(cypher):
        return {
            "safe": False,
            "message": "Blocked because the Cypher query appears to contain write/admin operations.",
            "cypher": cypher,
        }

    safe_query = cypher.strip()
    if " LIMIT " not in f" {safe_query.upper()} ":
        safe_query = f"{safe_query}\nLIMIT {limit}"

    with driver.session(database=settings.neo4j_database) as session:
        records = session.run(safe_query)
        results = [dict(record) for record in records]

    return {
        "safe": True,
        "cypher": safe_query,
        "results": results,
    }


if __name__ == "__main__":
    mcp.run()
