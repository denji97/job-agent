import asyncio
from contextlib import AsyncExitStack

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class MCPClient:
    def __init__(self, server_params: StdioServerParameters):
        self.server_params = server_params
        self.session = None
        self.tools = []
        self.exit_stack = AsyncExitStack()

    async def __aenter__(self):
        await self.exit_stack.__aenter__()
        stdio_transport = await self.exit_stack.enter_async_context(
            stdio_client(self.server_params)
        )
        self.stdio, self.write = stdio_transport
        self.session = await self.exit_stack.enter_async_context(
            ClientSession(self.stdio, self.write)
        )
        await self.session.initialize()
        response = await self.session.list_tools()
        self.tools = response.tools
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return await self.exit_stack.__aexit__(exc_type, exc, tb)

    async def call_tool(self, name: str, arguments: dict):
        result = await self.session.call_tool(name, arguments)
        return result.content[0].text


if __name__ == "__main__":
    import os
    import sys

    async def main():
        params = StdioServerParameters(
            command=sys.executable,
            args=[os.getcwd() + "/mcp_servers" + "/server_job_listings.py"],
        )
        async with MCPClient(server_params=params) as mcp_client:
            for t in mcp_client.tools:
                print(t)
                print(type(t))
                break

    asyncio.run(main())
