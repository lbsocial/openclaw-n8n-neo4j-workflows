"""Local MCP client smoke test for the YouTube GraphRAG server.

Run from this folder:
    uv run python local_client_test.py --question "OpenClaw n8n Neo4j GraphRAG"
"""

from __future__ import annotations

import argparse
import asyncio
import json
from typing import Any

from fastmcp import Client


def _parse_result(result: Any) -> Any:
    if not result.content:
        return None
    text = getattr(result.content[0], "text", "")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def _print_json(title: str, value: Any) -> None:
    print(f"\n== {title} ==")
    print(json.dumps(value, ensure_ascii=False, indent=2, default=str))


async def run(question: str, top_k: int) -> None:
    async with Client("server.py") as client:
        tools = await client.list_tools()
        _print_json("tools", [tool.name for tool in tools])

        schema_result = await client.call_tool_mcp("get_neo4j_schema_and_indexes", {})
        schema = _parse_result(schema_result)
        _print_json(
            "schema summary",
            {
                "is_error": schema_result.isError,
                "database": schema.get("database") if isinstance(schema, dict) else None,
                "labels": schema.get("labels") if isinstance(schema, dict) else None,
                "relationships": schema.get("relationships") if isinstance(schema, dict) else None,
                "indexes": schema.get("indexes") if isinstance(schema, dict) else None,
            },
        )

        recent_result = await client.call_tool_mcp("get_recent_youtube_videos", {"limit": 3})
        recent = _parse_result(recent_result)
        _print_json("recent videos", recent)

        search_result = await client.call_tool_mcp(
            "search_youtube_videos",
            {"question": question, "top_k": top_k},
        )
        search = _parse_result(search_result)
        _print_json("semantic search", search)

        path_result = await client.call_tool_mcp(
            "recommend_learning_path",
            {"question": question, "top_k": top_k},
        )
        path = _parse_result(path_result)
        _print_json("learning path input", path)

        count_result = await client.call_tool_mcp(
            "run_readonly_cypher",
            {"cypher": "MATCH (v:Video) RETURN count(v) AS video_count", "limit": 1},
        )
        count = _parse_result(count_result)
        _print_json("readonly count", count)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--question",
        default="OpenClaw n8n Neo4j MCP GraphRAG",
        help="Question to send to the semantic search and learning-path tools.",
    )
    parser.add_argument("--top-k", type=int, default=3)
    args = parser.parse_args()

    asyncio.run(run(question=args.question, top_k=args.top_k))


if __name__ == "__main__":
    main()
