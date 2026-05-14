"""LBSocial YouTube GraphRAG MCP server.

This MCP server is intentionally domain-specific for the OpenClaw + n8n +
Neo4j tutorial series. It queries the YouTube metadata graph created by the
n8n ingestion workflow, where Gemini embeddings are stored on Video nodes.
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
    from google.genai import types as genai_types
except Exception:  # pragma: no cover - optional provider
    genai = None
    genai_types = None

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
    gemini_embedding_dimensions: int
    vector_index: str
    video_label: str
    channel_label: str
    topic_label: str
    channel_to_video_rel: str
    video_to_topic_rel: str
    video_embedding_property: str
    video_id_property: str
    video_title_property: str
    video_url_property: str
    video_document_text_property: str
    video_published_at_property: str
    channel_title_property: str
    topic_name_property: str
    schema_sample_size: int


def env(name: str, default: str | None = None) -> str:
    value = os.getenv(name, default)
    if value is None or value == "":
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer.") from exc


def load_settings() -> Settings:
    provider = env("EMBEDDING_PROVIDER", "gemini").lower()
    if provider not in {"openai", "gemini"}:
        raise RuntimeError("EMBEDDING_PROVIDER must be either 'openai' or 'gemini'.")

    return Settings(
        neo4j_uri=env("NEO4J_URI"),
        neo4j_username=env("NEO4J_USERNAME"),
        neo4j_password=env("NEO4J_PASSWORD"),
        neo4j_database=env("NEO4J_DATABASE", "neo4j"),
        embedding_provider=provider,  # type: ignore[arg-type]
        openai_embedding_model=env("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"),
        gemini_embedding_model=env("GEMINI_EMBEDDING_MODEL", "gemini-embedding-001"),
        gemini_embedding_dimensions=env_int("GEMINI_EMBEDDING_DIMENSIONS", 768),
        vector_index=env("YOUTUBE_VIDEO_VECTOR_INDEX", "video_embeddings"),
        video_label=env("YOUTUBE_VIDEO_LABEL", "Video"),
        channel_label=env("YOUTUBE_CHANNEL_LABEL", "Channel"),
        topic_label=env("YOUTUBE_TOPIC_LABEL", "Topic"),
        channel_to_video_rel=env("YOUTUBE_CHANNEL_TO_VIDEO_REL", "PUBLISHED"),
        video_to_topic_rel=env("YOUTUBE_VIDEO_TO_TOPIC_REL", "HAS_TOPIC"),
        video_embedding_property=env("YOUTUBE_VIDEO_EMBEDDING_PROPERTY", "embedding"),
        video_id_property=env("YOUTUBE_VIDEO_ID_PROPERTY", "video_id"),
        video_title_property=env("YOUTUBE_VIDEO_TITLE_PROPERTY", "title"),
        video_url_property=env("YOUTUBE_VIDEO_URL_PROPERTY", "url"),
        video_document_text_property=env("YOUTUBE_VIDEO_DOCUMENT_TEXT_PROPERTY", "document_text"),
        video_published_at_property=env("YOUTUBE_VIDEO_PUBLISHED_AT_PROPERTY", "published_at"),
        channel_title_property=env("YOUTUBE_CHANNEL_TITLE_PROPERTY", "channel_title"),
        topic_name_property=env("YOUTUBE_TOPIC_NAME_PROPERTY", "name"),
        schema_sample_size=env_int("NEO4J_SCHEMA_SAMPLE_SIZE", 100),
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


def _identifiers() -> dict[str, str]:
    return {
        "vector_index": _safe_identifier(settings.vector_index, "vector index"),
        "video_label": _safe_identifier(settings.video_label, "video label"),
        "channel_label": _safe_identifier(settings.channel_label, "channel label"),
        "topic_label": _safe_identifier(settings.topic_label, "topic label"),
        "channel_to_video_rel": _safe_identifier(
            settings.channel_to_video_rel, "channel-to-video relationship"
        ),
        "video_to_topic_rel": _safe_identifier(
            settings.video_to_topic_rel, "video-to-topic relationship"
        ),
        "video_embedding_property": _safe_identifier(
            settings.video_embedding_property, "video embedding property"
        ),
        "video_id_property": _safe_identifier(settings.video_id_property, "video ID property"),
        "video_title_property": _safe_identifier(
            settings.video_title_property, "video title property"
        ),
        "video_url_property": _safe_identifier(settings.video_url_property, "video URL property"),
        "video_document_text_property": _safe_identifier(
            settings.video_document_text_property, "video document text property"
        ),
        "video_published_at_property": _safe_identifier(
            settings.video_published_at_property, "video published-at property"
        ),
        "channel_title_property": _safe_identifier(
            settings.channel_title_property, "channel title property"
        ),
        "topic_name_property": _safe_identifier(settings.topic_name_property, "topic name property"),
    }


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
    kwargs: dict[str, Any] = {
        "model": settings.gemini_embedding_model,
        "contents": question,
    }
    if genai_types is not None:
        kwargs["config"] = genai_types.EmbedContentConfig(
            output_dimensionality=settings.gemini_embedding_dimensions
        )

    try:
        response = client.models.embed_content(**kwargs)
    except TypeError:
        kwargs.pop("config", None)
        response = client.models.embed_content(**kwargs)

    embedding = response.embeddings[0].values
    return list(embedding)


def embed_question(question: str) -> list[float]:
    if settings.embedding_provider == "openai":
        return _embed_with_openai(question)
    if settings.embedding_provider == "gemini":
        return _embed_with_gemini(question)
    raise RuntimeError(f"Unsupported embedding provider: {settings.embedding_provider}")


def _summary_text(value: Any, max_chars: int = 700) -> str:
    text = "" if value is None else str(value).strip()
    if len(text) <= max_chars:
        return text
    return f"{text[:max_chars].rstrip()}..."


def _youtube_search_cypher() -> str:
    ids = _identifiers()
    return f"""
    CALL db.index.vector.queryNodes($vector_index, $top_k, $query_embedding)
    YIELD node AS video, score

    WHERE video:{ids["video_label"]}

    OPTIONAL MATCH (channel:{ids["channel_label"]})-[:{ids["channel_to_video_rel"]}]->(video)
    OPTIONAL MATCH (video)-[:{ids["video_to_topic_rel"]}]->(topic:{ids["topic_label"]})

    RETURN
      video.{ids["video_id_property"]} AS video_id,
      video.{ids["video_title_property"]} AS title,
      video.{ids["video_url_property"]} AS url,
      video.{ids["video_published_at_property"]} AS published_at,
      channel.{ids["channel_title_property"]} AS channel,
      collect(DISTINCT topic.{ids["topic_name_property"]}) AS topics,
      video.{ids["video_document_text_property"]} AS document_text,
      score
    ORDER BY score DESC
    """


def _recent_videos_cypher() -> str:
    ids = _identifiers()
    return f"""
    MATCH (video:{ids["video_label"]})
    OPTIONAL MATCH (channel:{ids["channel_label"]})-[:{ids["channel_to_video_rel"]}]->(video)
    OPTIONAL MATCH (video)-[:{ids["video_to_topic_rel"]}]->(topic:{ids["topic_label"]})
    RETURN
      video.{ids["video_id_property"]} AS video_id,
      video.{ids["video_title_property"]} AS title,
      video.{ids["video_url_property"]} AS url,
      video.{ids["video_published_at_property"]} AS published_at,
      channel.{ids["channel_title_property"]} AS channel,
      collect(DISTINCT topic.{ids["topic_name_property"]}) AS topics,
      size(video.{ids["video_embedding_property"]}) AS embedding_dimensions,
      video.updated_at AS updated_at
    ORDER BY video.updated_at DESC, video.{ids["video_published_at_property"]} DESC
    LIMIT $limit
    """


def _video_context_cypher() -> str:
    ids = _identifiers()
    return f"""
    MATCH (video:{ids["video_label"]})
    WHERE toLower(toString(video.{ids["video_title_property"]})) CONTAINS toLower($title_phrase)

    OPTIONAL MATCH (channel:{ids["channel_label"]})-[:{ids["channel_to_video_rel"]}]->(video)
    OPTIONAL MATCH (video)-[:{ids["video_to_topic_rel"]}]->(topic:{ids["topic_label"]})

    RETURN
      video.{ids["video_id_property"]} AS video_id,
      video.{ids["video_title_property"]} AS title,
      video.{ids["video_url_property"]} AS url,
      video.{ids["video_published_at_property"]} AS published_at,
      channel.{ids["channel_title_property"]} AS channel,
      collect(DISTINCT topic.{ids["topic_name_property"]}) AS topics,
      video.{ids["video_document_text_property"]} AS document_text,
      size(video.{ids["video_embedding_property"]}) AS embedding_dimensions
    ORDER BY video.{ids["video_published_at_property"]} DESC
    LIMIT $limit
    """


def _video_by_id_cypher() -> str:
    ids = _identifiers()
    return f"""
    MATCH (video:{ids["video_label"]} {{{ids["video_id_property"]}: $video_id}})
    OPTIONAL MATCH (channel:{ids["channel_label"]})-[:{ids["channel_to_video_rel"]}]->(video)
    OPTIONAL MATCH (video)-[:{ids["video_to_topic_rel"]}]->(topic:{ids["topic_label"]})
    RETURN
      video.{ids["video_id_property"]} AS video_id,
      video.{ids["video_title_property"]} AS title,
      video.{ids["video_url_property"]} AS url,
      video.{ids["video_published_at_property"]} AS published_at,
      channel.{ids["channel_title_property"]} AS channel,
      collect(DISTINCT topic.{ids["topic_name_property"]}) AS topics,
      video.{ids["video_document_text_property"]} AS document_text,
      size(video.{ids["video_embedding_property"]}) AS embedding_dimensions
    LIMIT 1
    """


def _related_videos_cypher() -> str:
    ids = _identifiers()
    return f"""
    MATCH (source:{ids["video_label"]} {{{ids["video_id_property"]}: $video_id}})
    WHERE source.{ids["video_embedding_property"]} IS NOT NULL

    CALL db.index.vector.queryNodes(
      $vector_index,
      $candidate_limit,
      source.{ids["video_embedding_property"]}
    )
    YIELD node AS video, score

    WHERE video:{ids["video_label"]}
      AND video.{ids["video_id_property"]} <> source.{ids["video_id_property"]}

    OPTIONAL MATCH (source)-[:{ids["video_to_topic_rel"]}]->(shared:{ids["topic_label"]})
      <-[:{ids["video_to_topic_rel"]}]-(video)
    OPTIONAL MATCH (video)-[:{ids["video_to_topic_rel"]}]->(topic:{ids["topic_label"]})
    OPTIONAL MATCH (channel:{ids["channel_label"]})-[:{ids["channel_to_video_rel"]}]->(video)

    WITH
      video,
      score,
      channel,
      collect(DISTINCT shared.{ids["topic_name_property"]}) AS shared_topics,
      collect(DISTINCT topic.{ids["topic_name_property"]}) AS topics

    RETURN
      video.{ids["video_id_property"]} AS video_id,
      video.{ids["video_title_property"]} AS title,
      video.{ids["video_url_property"]} AS url,
      video.{ids["video_published_at_property"]} AS published_at,
      channel.{ids["channel_title_property"]} AS channel,
      topics,
      shared_topics,
      size(shared_topics) AS shared_topic_count,
      video.{ids["video_document_text_property"]} AS document_text,
      score
    ORDER BY shared_topic_count DESC, score DESC
    LIMIT $limit
    """


def _format_video_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    results = []
    for record in records:
        item = dict(record)
        if "document_text" in item:
            item["document_text_summary"] = _summary_text(item.pop("document_text"))
        results.append(item)
    return results


@mcp.tool()
def get_neo4j_schema_and_indexes() -> dict[str, Any]:
    """Inspect labels, relationships, sampled properties, vector indexes, and fulltext indexes."""
    with driver.session(database=settings.neo4j_database) as session:
        labels = [record["label"] for record in session.run("CALL db.labels() YIELD label RETURN label")]
        relationships = [
            record["relationshipType"]
            for record in session.run(
                "CALL db.relationshipTypes() YIELD relationshipType RETURN relationshipType"
            )
        ]
        node_properties = [
            dict(record)
            for record in session.run(
                """
                MATCH (node)
                WITH node LIMIT $sample_size
                UNWIND labels(node) AS label
                UNWIND keys(node) AS property
                RETURN label, collect(DISTINCT property) AS properties
                ORDER BY label
                """,
                sample_size=settings.schema_sample_size,
            )
        ]
        relationship_properties = [
            dict(record)
            for record in session.run(
                """
                MATCH ()-[rel]->()
                WITH rel LIMIT $sample_size
                UNWIND keys(rel) AS property
                RETURN type(rel) AS relationship_type, collect(DISTINCT property) AS properties
                ORDER BY relationship_type
                """,
                sample_size=settings.schema_sample_size,
            )
        ]
        indexes = [
            dict(record)
            for record in session.run(
                """
                SHOW INDEXES
                YIELD name, type, state, labelsOrTypes, properties
                WHERE type IN ["VECTOR", "FULLTEXT"]
                RETURN name, type, state, labelsOrTypes, properties
                ORDER BY type, name
                """
            )
        ]

    return {
        "database": settings.neo4j_database,
        "sample_size": settings.schema_sample_size,
        "labels": labels,
        "relationships": relationships,
        "node_properties": node_properties,
        "relationship_properties": relationship_properties,
        "indexes": indexes,
    }


def _search_youtube_videos_impl(question: str, top_k: int) -> dict[str, Any]:
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
        matches = _format_video_records([dict(record) for record in records])

    return {
        "question": question,
        "top_k": top_k,
        "embedding_provider": settings.embedding_provider,
        "embedding_model": (
            settings.gemini_embedding_model
            if settings.embedding_provider == "gemini"
            else settings.openai_embedding_model
        ),
        "vector_index": settings.vector_index,
        "matches": matches,
    }


@mcp.tool()
def search_youtube_videos(question: str, top_k: int = 5) -> dict[str, Any]:
    """Search YouTube Video nodes using vector search plus Channel/Topic graph context."""
    return _search_youtube_videos_impl(question=question, top_k=top_k)


@mcp.tool()
def search_youtube_kg(question: str, top_k: int = 5) -> dict[str, Any]:
    """Backward-compatible alias for search_youtube_videos."""
    return _search_youtube_videos_impl(question=question, top_k=top_k)


@mcp.tool()
def get_recent_youtube_videos(limit: int = 10) -> dict[str, Any]:
    """List recently updated YouTube videos from the tutorial graph."""
    if limit < 1 or limit > 50:
        raise ValueError("limit must be between 1 and 50.")

    with driver.session(database=settings.neo4j_database) as session:
        records = session.run(_recent_videos_cypher(), limit=limit)
        results = [dict(record) for record in records]

    return {
        "limit": limit,
        "results": results,
    }


@mcp.tool()
def get_video_context(title_phrase: str, limit: int = 5) -> dict[str, Any]:
    """Retrieve metadata, channel, topics, and embedded text for videos matching a title phrase."""
    if limit < 1 or limit > 20:
        raise ValueError("limit must be between 1 and 20.")

    with driver.session(database=settings.neo4j_database) as session:
        records = session.run(
            _video_context_cypher(),
            title_phrase=title_phrase,
            limit=limit,
        )
        results = _format_video_records([dict(record) for record in records])

    return {
        "title_phrase": title_phrase,
        "limit": limit,
        "results": results,
    }


@mcp.tool()
def get_related_videos(video_id: str, limit: int = 5) -> dict[str, Any]:
    """Recommend videos related to a source video using semantic search plus shared topics."""
    if limit < 1 or limit > 20:
        raise ValueError("limit must be between 1 and 20.")

    with driver.session(database=settings.neo4j_database) as session:
        source_record = session.run(_video_by_id_cypher(), video_id=video_id).single()
        if source_record is None:
            return {
                "video_id": video_id,
                "found": False,
                "message": "No source video found for the provided video_id.",
                "related_videos": [],
            }

        source_video = _format_video_records([dict(source_record)])[0]

        candidate_limit = max(limit * 5, 20)
        records = session.run(
            _related_videos_cypher(),
            video_id=video_id,
            vector_index=settings.vector_index,
            candidate_limit=candidate_limit,
            limit=limit,
        )
        related_videos = _format_video_records([dict(record) for record in records])

    return {
        "video_id": video_id,
        "found": True,
        "limit": limit,
        "vector_index": settings.vector_index,
        "source_video": source_video,
        "related_videos": related_videos,
    }


@mcp.tool()
def recommend_learning_path(question: str, top_k: int = 5) -> dict[str, Any]:
    """Find relevant videos and return structured context for an OpenClaw learning path."""
    results = _search_youtube_videos_impl(question=question, top_k=top_k)
    results["recommendation_instruction"] = (
        "Summarize these matches as a practical learning path. Use the highest-scoring videos "
        "first, group related topics when helpful, and include video titles and URLs as sources."
    )
    return results


@mcp.prompt()
def youtube_graphrag_cypher_prompt(question: str = "") -> str:
    """Guide an MCP client on safe Cypher usage for the YouTube GraphRAG schema."""
    question_text = question.strip() or "<user question>"
    ids = _identifiers()
    return f"""You are helping query the LBSocial YouTube GraphRAG Neo4j database.

User question:
{question_text}

Current graph schema:
- (:{ids["channel_label"]})-[:{ids["channel_to_video_rel"]}]->(:{ids["video_label"]})
- (:{ids["video_label"]})-[:{ids["video_to_topic_rel"]}]->(:{ids["topic_label"]})

Important properties:
- {ids["video_label"]}.{ids["video_id_property"]}
- {ids["video_label"]}.{ids["video_title_property"]}
- {ids["video_label"]}.{ids["video_url_property"]}
- {ids["video_label"]}.{ids["video_published_at_property"]}
- {ids["video_label"]}.{ids["video_document_text_property"]}
- {ids["video_label"]}.{ids["video_embedding_property"]}
- {ids["channel_label"]}.{ids["channel_title_property"]}
- {ids["topic_label"]}.{ids["topic_name_property"]}

Preferred tools:
- For ordinary recommendation questions, use search_youtube_videos or recommend_learning_path.
- For source-video follow-up questions, use get_related_videos.
- For connectivity checks, use get_recent_youtube_videos or get_neo4j_schema_and_indexes.
- Use run_readonly_cypher only for advanced read-only inspection or statistical analysis.

Cypher safety rules:
- Generate read-only Cypher only.
- Do not generate CREATE, MERGE, DELETE, DETACH, SET, REMOVE, DROP, LOAD CSV, ALTER, GRANT,
  DENY, REVOKE, START DATABASE, STOP DATABASE, or dbms admin calls.
- Do not expose credentials, environment variables, secrets, or internal file paths.
- Prefer returning video titles, URLs, channel names, topics, and counts that OpenClaw can
  summarize for the user.
"""


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
        r"\bALTER\b",
        r"\bGRANT\b",
        r"\bDENY\b",
        r"\bREVOKE\b",
        r"\bSTART\s+DATABASE\b",
        r"\bSTOP\s+DATABASE\b",
        r"\bCALL\s+dbms\.",
    ]
    return not any(re.search(pattern, cypher, re.IGNORECASE) for pattern in blocked)


@mcp.tool()
def run_readonly_cypher(cypher: str, limit: int = 20) -> dict[str, Any]:
    """Run a manually supplied read-only Cypher query after a conservative safety check."""
    if limit < 1 or limit > 100:
        raise ValueError("limit must be between 1 and 100.")

    if not _is_safe_read_query(cypher):
        return {
            "safe": False,
            "message": "Blocked because the Cypher query appears to contain write/admin operations.",
            "cypher": cypher,
        }

    safe_query = cypher.strip().rstrip(";")
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
