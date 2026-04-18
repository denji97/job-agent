import asyncio
from typing import Optional
from contextlib import AsyncExitStack

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv() 


class MCPClient:
    def __init__(self, server_params:StdioServerParameters):
        self.server_params = server_params
        self.session = None
        self.tools = []
        self.exit_stack = AsyncExitStack()

    async def connect(self):
        stdio_transport = await self.exit_stack.enter_async_context(stdio_client(self.server_params))
        self.stdio, self.write = stdio_transport
        self.session = await self.exit_stack.enter_async_context(ClientSession(self.stdio, self.write))
        await self.session.initialize()
        response = await self.session.list_tools()
        self.tools = response.tools

    async def call_tool(self, name:str, arguments:dict):
        result = await self.session.call_tool(name, arguments)
        return result.content[0].text

    async def disconnect(self):
        await self.exit_stack.aclose()



# if __name__ == '__main__':
#     import os 
#     async def main():
#         params = StdioServerParameters(
#             command="python",
#             args=[os.getcwd()+"/mcp_servers"+"/server_job_listings.py"]
#         )
#         mcp_client = MCPClient(server_params=params)
#         await mcp_client.connect()
#         for t in mcp_client.tools:
#             print(f"  - {t.name}: {t.description}")
#         result_tool_call = await mcp_client.call_tool('get_job_ids', {'job_title': 'AI-Engineer', 'city': 'Köln', 'radius': '50'})
#         print(result_tool_call)
#         await mcp_client.disconnect()


#     asyncio.run(main())
