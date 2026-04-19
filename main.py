import asyncio
import os
import sys

from dotenv import load_dotenv
from mcp import StdioServerParameters

from agent.agent import Agent
from mcp_client.mcp_client import MCPClient

load_dotenv()


async def main():
    mcp_clients = [
        MCPClient(
            server_params=StdioServerParameters(
                command=sys.executable,
                args=[os.getcwd() + "/mcp_servers" + "/server_job_listings.py"],
            )
        )
    ]
    try:
        for mcp_client in mcp_clients:
            await mcp_client.connect()

        agent = Agent(clients=mcp_clients, system_prompt="")
        messages = []
        while True:
            query = input("<You>:\n")
            if query.lower() == "quit":
                break

            messages.append({"role": "user", "content": query})
            messages, output_msg = await agent.run(messages=messages)
            messages.append({"role": "assistant", "content": output_msg})
            print(f"<Job-Agent>\n{output_msg}")
    except KeyboardInterrupt:
        print("\nExiting...")
    finally:
        for mcp_client in mcp_clients:
            await mcp_client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
