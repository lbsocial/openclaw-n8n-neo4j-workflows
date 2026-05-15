"""Ask the local YouTube GraphRAG MCP server a question.

Run from this folder:
    uv run python local_ask.py
"""

from __future__ import annotations

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


def _print_matches(payload: dict[str, Any]) -> None:
    matches = payload.get("matches", [])
    if not matches:
        print("No matches returned.")
        return

    for index, item in enumerate(matches, start=1):
        print(f"\n{index}. {item.get('title')}")
        print(f"   URL: {item.get('url')}")
        print(f"   Score: {item.get('score')}")
        topics = item.get("topics") or []
        if topics:
            print(f"   Topics: {', '.join(topics)}")
        summary = item.get("document_text_summary")
        if summary:
            print(f"   Summary: {summary[:350].strip()}...")


async def ask_loop() -> None:
    async with Client("server.py") as client:
        tools = await client.list_tools()
        print("Connected to MCP server.")
        print("Tools:", ", ".join(tool.name for tool in tools))
        print("Type a question, or type q to quit.\n")

        while True:
            question = input("Question> ").strip()
            if question.lower() in {"q", "quit", "exit"}:
                break
            if not question:
                continue

            search_result = await client.call_tool_mcp(
                "search_youtube_videos",
                {"question": question, "top_k": 5},
            )
            if search_result.isError:
                print(_parse_result(search_result))
                continue

            search_payload = _parse_result(search_result)
            print("\nSearch results:")
            _print_matches(search_payload)

            path_result = await client.call_tool_mcp(
                "recommend_learning_path",
                {"question": question, "top_k": 5},
            )
            path_payload = _parse_result(path_result)
            instruction = (
                path_payload.get("recommendation_instruction")
                if isinstance(path_payload, dict)
                else None
            )
            if instruction:
                print("\nLearning path instruction:")
                print(instruction)
            print()


def main() -> None:
    asyncio.run(ask_loop())


if __name__ == "__main__":
    main()
