import asyncio
import os
import sys
from contextlib import AsyncExitStack

from dotenv import load_dotenv
from mcp import StdioServerParameters
from prompt_toolkit import PromptSession
from rich.console import Console

from agent.agent import Agent
from mcp_client.mcp_client import MCPClient
from system_prompt import SYSTEM_PROMPT

load_dotenv()


async def main():
    async with AsyncExitStack() as stack:
        mcp_clients = [
            await stack.enter_async_context(
                MCPClient(
                    server_params=StdioServerParameters(
                        command=sys.executable,
                        args=[os.getcwd() + "/mcp_servers" + "/server_job_listings.py"],
                    )
                )
            ),
            await stack.enter_async_context(
                MCPClient(
                    server_params=StdioServerParameters(
                        command="npx",
                        args=["-y", "@notionhq/notion-mcp-server"],
                        env={
                            "NOTION_TOKEN": os.environ["NOTION_TOKEN"],
                            "PATH": os.environ["PATH"],
                        },
                    )
                )
            ),
        ]

        agent = Agent(clients=mcp_clients, system_prompt=SYSTEM_PROMPT)
        messages = []
        session = PromptSession(multiline=True)
        console = Console()
        try:
            while True:
                query = (
                    await session.prompt_async("<You> (Alt+Enter/Esc+Enter to send):\n")
                ).strip()
                if not query:
                    continue
                if query.lower() == "quit":
                    break

                console.print("[dim]✓ gesendet[/dim]")
                messages.append({"role": "user", "content": query})
                with console.status("[cyan]Denke nach…[/cyan]", spinner="dots") as status:
                    def on_event(msg: str) -> None:
                        status.update(f"[cyan]{msg}[/cyan]")

                    messages, output_msg = await agent.run(
                        messages=messages, on_event=on_event
                    )
                messages.append({"role": "assistant", "content": output_msg})
                console.print(f"[bold green]<Job-Agent>[/bold green]\n{output_msg}")
        except (KeyboardInterrupt, EOFError):
            print("\nExiting...")


if __name__ == "__main__":
    asyncio.run(main())
