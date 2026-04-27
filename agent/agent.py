import json
import os
from typing import Any, Callable, Dict, List, Optional, Tuple

from openai import AsyncOpenAI

from mcp_client.mcp_client import MCPClient

DEFAULT_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1")
DEFAULT_MODEL = os.environ.get("OLLAMA_MODEL", "gemma4:e4b")


class Agent:
    def __init__(
        self,
        clients: List[MCPClient],
        system_prompt: str,
        model: str = DEFAULT_MODEL,
        base_url: str = DEFAULT_BASE_URL,
        max_tokens: int = 8192,
    ):
        """Agent class to handle tool calling and the agentic loop

        Args:
            clients (List[MCPClient]): List of all 1:1 MCP client instances connected to MCP servers
            system_prompt (str): The system prompt for the agent
            model (str, optional): Anthropic model to use for the agent. Defaults to "gemma4:e4b".
            base_url (str, optional): URL for the LLM API. Defaults to "http://localhost:11434/v1".
            max_tokens (int, optional): Max number of tokens. Defaults to 8192.
        """
        self.clients = clients
        self.system_prompt = system_prompt
        self.model = model
        self.tool_client_map, self.tool_list = self._setup_tools()
        self.openai = AsyncOpenAI(
            base_url=base_url, api_key="ollama"
        )  # the api_key is not used here
        self._max_tokens = max_tokens

    def _setup_tools(self) -> Tuple[Dict[str, MCPClient], List[Dict[str, str]]]:
        """Creates a mapping dictionary of all tools and their respective client instance.

        Returns:
            Tuple[Dict[str, MCPClient], List[Dict[str, str]]]: Dictionary mapping the tools to the respective client instance
                                                               and a list of all available tools in the anthropic expected format.
        """
        tool_client_map = {}
        tool_list = []
        for client in self.clients:
            for tool in client.tools:
                tool_client_map[tool.name] = client
                tool_list.append(
                    {
                        "type": "function",
                        "function": {
                            "name": tool.name,
                            "description": tool.description,
                            "parameters": tool.inputSchema,
                        },
                    }
                )
        return tool_client_map, tool_list

    async def run(
        self,
        messages: List[Dict[str, Any]],
        on_event: Optional[Callable[[str], None]] = None,
    ) -> Tuple[List[Dict[str, Any]], str]:
        """The agentic loop

        Args:
            messages (List[Dict[str, Any]]): Since the Anthropic API is stateless we need to keep track of the conversation history.
                                             The messages contain all the messages between the user and the system. Further, the last entry is the newest query to the LLM.
            on_event (Optional[Callable[[str], None]], optional): Callable in order to enrich the terminal output. Defaults to None.

        Returns:
            Tuple[List[Dict[str, Any]], str]: List of the message history and the newest repsonse from the LLM
        """

        def emit(msg: str) -> None:
            if on_event:
                on_event(msg)

        # Prepend system message (OpenAI uses a system message in the list)
        full_messages = [
            {"role": "system", "content": self.system_prompt},
            *messages,
        ]

        emit("Denke nach…")
        # initial query to the LLM
        response = await self.openai.chat.completions.create(
            model=self.model,
            tools=self.tool_list,
            max_tokens=self._max_tokens,
            messages=full_messages,
        )

        message = response.choices[0].message

        # if the LLM decides to use a tool, we go into the agentic loop
        while message.tool_calls:
            full_messages.append(message.model_dump())
            for tool_call in message.tool_calls:
                tool_name = tool_call.function.name

                tool_args = json.loads(tool_call.function.arguments or "{}")

                emit(f"Rufe {tool_name} auf…")
                tool_client = self.tool_client_map[tool_name]
                result = await tool_client.call_tool(tool_name, tool_args)

                full_messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": result
                        if isinstance(result, str)
                        else json.dumps(result),
                    }
                )
            # tool_results = []
            # for block in response.content:
            #     if block.type == "tool_use":
            #         emit(f"Rufe {block.name} auf…")
            #         # the chosen tool using the respective client get's called
            #         tool_client = self.tool_client_map[block.name]
            #         result = await tool_client.call_tool(block.name, block.input)
            #         # tool results are appended
            #         tool_results.append(
            #             {
            #                 "type": "tool_result",
            #                 "tool_use_id": block.id,
            #                 "content": result,
            #             }
            #         )

            # messages += [
            #     {"role": "assistant", "content": response.content},
            #     {"role": "user", "content": tool_results},
            # ]
            emit("Denke nach…")
            # the tool results are fed back to the LLM which generates a new response
            response = await self.openai.chat.completions.create(
                model=self.model,
                tools=self.tool_list,
                max_tokens=self._max_tokens,
                messages=full_messages,
            )
            message = response.choices[0].message
            print(message)
        # return the message updated message history and the last text response
        return messages, message.content or "DONE"
