"""Interactive local MCP tool menu for the YouTube GraphRAG server.

Run from this folder:
    uv run python local_tool_menu.py
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from fastmcp import Client


TOOLS: list[dict[str, Any]] = [
    {
        "name": "get_neo4j_schema_and_indexes",
        "label": "Inspect Neo4j schema and indexes",
        "args": [],
    },
    {
        "name": "search_youtube_videos",
        "label": "Semantic video search",
        "args": [
            ("question", "Question", "OpenClaw n8n Neo4j GraphRAG"),
            ("top_k", "Top K", "5"),
        ],
    },
    {
        "name": "search_youtube_kg",
        "label": "Semantic video search alias",
        "args": [
            ("question", "Question", "Gemini embeddings YouTube knowledge graph"),
            ("top_k", "Top K", "5"),
        ],
    },
    {
        "name": "get_recent_youtube_videos",
        "label": "Recent videos",
        "args": [("limit", "Limit", "5")],
    },
    {
        "name": "get_video_context",
        "label": "Video context by title phrase",
        "args": [
            ("title_phrase", "Title phrase", "OpenClaw"),
            ("limit", "Limit", "5"),
        ],
    },
    {
        "name": "get_related_videos",
        "label": "Related videos by video_id",
        "args": [
            ("video_id", "Video ID", "AN2WL_jBoY8"),
            ("limit", "Limit", "5"),
        ],
    },
    {
        "name": "recommend_learning_path",
        "label": "Learning path retrieval",
        "args": [
            (
                "question",
                "Question",
                "I want to learn OpenClaw with n8n, Neo4j, MCP, and GraphRAG.",
            ),
            ("top_k", "Top K", "5"),
        ],
    },
    {
        "name": "run_readonly_cypher",
        "label": "Run safe read-only Cypher",
        "args": [
            (
                "cypher",
                "Cypher",
                "MATCH (t:Topic)<-[:HAS_TOPIC]-(v:Video) "
                "RETURN t.name AS topic, count(v) AS videos ORDER BY videos DESC",
            ),
            ("limit", "Limit", "20"),
        ],
    },
]


def _parse_result(result: Any) -> Any:
    if not result.content:
        return None
    text = getattr(result.content[0], "text", "")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def _coerce_value(name: str, value: str) -> Any:
    if name in {"limit", "top_k"}:
        return int(value)
    return value


def _print_menu() -> None:
    print("\nAvailable tools:")
    for index, tool in enumerate(TOOLS, start=1):
        print(f"  {index}. {tool['name']} - {tool['label']}")
    print("  q. Quit")


async def run_menu() -> None:
    async with Client("server.py") as client:
        listed_tools = await client.list_tools()
        print("Connected to MCP server.")
        print("Server tools:", ", ".join(tool.name for tool in listed_tools))

        while True:
            _print_menu()
            choice = input("\nChoose tool> ").strip().lower()
            if choice in {"q", "quit", "exit"}:
                break
            if not choice.isdigit() or not (1 <= int(choice) <= len(TOOLS)):
                print("Please choose a valid number.")
                continue

            spec = TOOLS[int(choice) - 1]
            args: dict[str, Any] = {}
            for name, label, default in spec["args"]:
                raw = input(f"{label} [{default}]> ").strip() or default
                try:
                    args[name] = _coerce_value(name, raw)
                except ValueError:
                    print(f"{label} must be a number.")
                    break
            else:
                print(f"\nCalling {spec['name']} with {args}...")
                result = await client.call_tool_mcp(spec["name"], args)
                payload = _parse_result(result)
                print("\nResult:")
                print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
                print(f"\nMCP error: {result.isError}")


def main() -> None:
    asyncio.run(run_menu())


if __name__ == "__main__":
    main()
