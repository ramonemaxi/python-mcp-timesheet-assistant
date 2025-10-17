import asyncio
import sys
from typing import Any, Dict
from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp.client.session import ClientSession


def extract_payload(result) -> Any:
    # Try to extract first JSON payload from MCP response
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
                txt = getattr(c, "text", None)
                # Try to parse JSON if it looks like JSON
                if isinstance(txt, str) and txt.strip().startswith("{"):
                    import json
                    try:
                        return json.loads(txt)
                    except Exception:
                        return txt
                return txt
    except Exception:
        pass
    return None


async def main():
    python_bin = sys.executable
    server_module = "server.server"
    async with stdio_client(StdioServerParameters(command=python_bin, args=["-m", server_module])) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            # Verify tools
            res = await session.list_tools()
            tools = getattr(res, "tools", res)
            names = []
            for t in tools:
                name = getattr(t, "name", None)
                if not name and hasattr(t, "model_dump"):
                    try:
                        name = t.model_dump().get("name")
                    except Exception:
                        name = None
                names.append(name or "<noname>")
            print("TOOLS:", names)

            # Use a demo user
            current_user_id = "ester"

            # List projects for ester
            r = await session.call_tool("list_projects", arguments={"current_user_id": current_user_id})
            p = extract_payload(r)
            print("list_projects:", p)
            projects = (p or {}).get("rows", []) if isinstance(p, dict) else []
            if not projects:
                print("No projects for user", current_user_id)
                return
            project_id = projects[0]["id"]

            # Add a time entry
            add_args: Dict[str, Any] = {
                "current_user_id": current_user_id,
                "project_id": int(project_id),
                "work_date": "2025-09-16",
                "hours": 1.5,
                "description": "smoke test"
            }
            r = await session.call_tool("add_time_entry", arguments=add_args)
            p = extract_payload(r)
            print("add_time_entry:", p)
            entry = (p or {}).get("entry") if isinstance(p, dict) else None
            if not entry:
                print("Failed to create time entry")
                return
            entry_id = entry.get("id")

            # List entries for that project
            r = await session.call_tool(
                "list_time_entries",
                arguments={
                    "current_user_id": current_user_id,
                    "project_id": int(project_id),
                    "date_from": "2025-09-01",
                    "date_to": "2025-09-30",
                },
            )
            print("list_time_entries:")
            print(extract_payload(r))

            # Update the entry's hours
            r = await session.call_tool(
                "update_time_entry",
                arguments={
                    "current_user_id": current_user_id,
                    "entry_id": int(entry_id),
                    "hours": 2.0,
                },
            )
            print("update_time_entry:")
            print(extract_payload(r))

            # Delete the entry
            r = await session.call_tool(
                "delete_time_entry",
                arguments={
                    "current_user_id": current_user_id,
                    "entry_id": int(entry_id),
                },
            )
            print("delete_time_entry:")
            print(extract_payload(r))


if __name__ == "__main__":
    asyncio.run(main())
