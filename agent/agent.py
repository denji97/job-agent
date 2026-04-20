from typing import Any, Callable, Dict, List, Optional, Tuple

from anthropic import Anthropic

from mcp_client.mcp_client import MCPClient


class Agent:
    def __init__(
        self,
        clients: List[MCPClient],
        system_prompt: str,
        model: str = "claude-sonnet-4-6",
        max_tokens: int = 8192,
    ):
        """Agent class to handle tool calling and the agentic loop

        Args:
            clients (List[MCPClient]): List of all 1:1 MCP client instances connected to MCP servers
            system_prompt (str): The system prompt for the agent
            model (str, optional): Anthropic model to use for the agent. Defaults to "claude-sonnet-4-6".
            max_tokens (int, optional): Max number of tokens. Defaults to 8192.
        """
        self.clients = clients
        self.system_prompt = system_prompt
        self.model = model
        self.tool_client_map, self.tool_list = self._setup_tools()
        self.anthropic = Anthropic()
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
                        "name": tool.name,
                        "description": tool.description,
                        "input_schema": tool.inputSchema,
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

        emit("Denke nach…")
        # initial query to the LLM
        response = self.anthropic.messages.create(
            model=self.model,
            system=self.system_prompt,
            tools=self.tool_list,
            max_tokens=self._max_tokens,
            messages=messages,
        )

        # if the LLM decides to use a tool, we go into the agentic loop
        while response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    emit(f"Rufe {block.name} auf…")
                    # the chosen tool using the respective client get's called
                    tool_client = self.tool_client_map[block.name]
                    result = await tool_client.call_tool(block.name, block.input)
                    # tool results are appended
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result,
                        }
                    )

            messages += [
                {"role": "assistant", "content": response.content},
                {"role": "user", "content": tool_results},
            ]
            emit("Denke nach…")
            # the tool results are fed back to the LLM which generates a new response
            response = self.anthropic.messages.create(
                model=self.model,
                system=self.system_prompt,
                tools=self.tool_list,
                max_tokens=self._max_tokens,
                messages=messages,
            )

        # return the message updated message history and the last text response
        return messages, next(
            (b.text for b in response.content if b.type == "text"), "DONE"
        )
