import asyncio
from contextlib import AsyncExitStack

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class MCPClient:
    def __init__(self, server_params: StdioServerParameters):
        """A 1:1 MCP client class which connects to one MCP server

        Args:
            server_params (StdioServerParameters): Stdio Server parameters
        """
        self.server_params = server_params
        self.session = None
        self.tools = []
        self.exit_stack = AsyncExitStack()

    async def __aenter__(self) -> "MCPClient":
        """Clean connection. Spawns the MCP server subprocess over stdio,
        opens an MCP `ClientSession` on top of it, performs the initialize
        handshake and caches the server's tool list on `self.tools`.

        All acquired resources (stdio transport, session) are registered
        with an internal AsyncExitStack so they are torn down in reverse
        order on `__aexit__`, even if initialization raises.

        Returns:
            MCPClient: This instance, ready to use inside the `async with`
                block (tools populated, session live).
        """
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
        """Clean disconnection. Closes the ClientSession and the underlying
        stdio transport by unwinding the internal AsyncExitStack in reverse
        order of entry, terminating the MCP server subprocess.

        Args:
            exc_type: Exception class raised inside the `async with` block,
                or None if it exited normally.
            exc: The exception instance, or None.
            tb: The traceback, or None.

        Returns:
            bool: True if the exception was suppressed by one of the
                stacked context managers, False otherwise.
        """
        return await self.exit_stack.__aexit__(exc_type, exc, tb)

    async def call_tool(self, name: str, arguments: dict) -> str:
        """Calls the specific tool of the MCP server.

        Args:
            name (str): Tool name
            arguments (dict): Input arguments

        Returns:
            str: Returns the tool result as a string
        """
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
