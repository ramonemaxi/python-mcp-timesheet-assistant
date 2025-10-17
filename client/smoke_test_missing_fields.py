import asyncio
import sys
from typing import Any, Dict
from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp.client.session import ClientSession


def extract_payload(result) -> Any:
    try:
        content_list = getattr(result, "content", [])
        for c in content_list:
            ctype = getattr(c, "type", None)
            if ctype == "json":
                data = getattr(c, "data", None)
                if isinstance(data, dict) and "result" in data:
                    return data["result"]
                return data
            if ctype == "text":
                return getattr(c, "text", None)
    except Exception:
        pass
    return None


async def main():
    python_bin = sys.executable
    server_module = "server.server"
    async with stdio_client(StdioServerParameters(command=python_bin, args=["-m", server_module])) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            current_user_id = "ester"

            # Get a project id for ester
            r = await session.call_tool("list_projects", arguments={"current_user_id": current_user_id})
            p = extract_payload(r)
            rows = (p or {}).get("rows", []) if isinstance(p, dict) else []
            if not rows:
                print("SKIP: No projects found for user 'ester' (nothing to test)")
                return
            project_id = int(rows[0]["id"])

            # Count entries before
            r = await session.call_tool(
                "list_time_entries",
                arguments={"current_user_id": current_user_id, "project_id": project_id},
            )
            before_payload = extract_payload(r)
            before_count = int((before_payload or {}).get("count", 0))
            print("before_count:", before_count)

            # 1) Try to call without description (expect schema or validation error)
            try:
                await session.call_tool(
                    "add_time_entry",
                    arguments={
                        "current_user_id": current_user_id,
                        "project_id": project_id,
                        "work_date": "2025-09-16",
                        "hours": 2.0,
                        # 'description' omitted intentionally
                    },
                )
                print("ERROR: add_time_entry without description unexpectedly succeeded")
            except Exception as e:
                print("OK: missing description rejected:", str(e)[:200])

            # 2) Try with empty description (expect server validation error)
            try:
                await session.call_tool(
                    "add_time_entry",
                    arguments={
                        "current_user_id": current_user_id,
                        "project_id": project_id,
                        "work_date": "2025-09-16",
                        "hours": 2.0,
                        "description": "",
                    },
                )
                print("ERROR: add_time_entry with empty description unexpectedly succeeded")
            except Exception as e:
                print("OK: empty description rejected:", str(e)[:200])

            # Count entries after to ensure no new rows were added
            r = await session.call_tool(
                "list_time_entries",
                arguments={"current_user_id": current_user_id, "project_id": project_id},
            )
            after_payload = extract_payload(r)
            after_count = int((after_payload or {}).get("count", 0))
            print("after_count:", after_count)
            if after_count == before_count:
                print("OK: No entries added when description was missing/empty")
            else:
                print("ERROR: Entry count changed (", before_count, "->", after_count, ")")


if __name__ == "__main__":
    asyncio.run(main())
