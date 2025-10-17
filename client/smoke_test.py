import asyncio
import sys
from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp.client.session import ClientSession


async def main():
    python_bin = sys.executable
    server_module = "server.server"
    async with stdio_client(StdioServerParameters(command=python_bin, args=["-m", server_module])) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            res = await session.list_tools()
            tool_list = getattr(res, "tools", res)
            # Intentar extraer nombre de forma robusta
            names = []
            for t in tool_list:
                name = getattr(t, "name", None)
                if not name and hasattr(t, "model_dump"):
                    try:
                        name = t.model_dump().get("name")
                    except Exception:
                        name = None
                if not name:
                    try:
                        name = t.get("name")  # si fuera dict
                    except Exception:
                        name = None
                names.append(str(name or "<sin-nombre>"))
            print("MCP tools:", ", ".join(names))
            # Debug opcional: imprimir estructura completa del primero
            if tool_list:
                first = tool_list[0]
                if hasattr(first, "model_dump"):
                    print("First tool dump:", first.model_dump())
                else:
                    print("First tool repr:", repr(first))


if __name__ == "__main__":
    asyncio.run(main())
