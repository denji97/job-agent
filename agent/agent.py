from typing import Any, Dict, List, Tuple

from anthropic import Anthropic

from mcp_client.mcp_client import MCPClient


class Agent:
    def __init__(
        self,
        clients: List[MCPClient],
        system_prompt: str,
        model: str = "claude-sonnet-4-6",
    ):
        self.clients = clients
        self.system_prompt = system_prompt
        self.model = model
        self.tool_client_map, self.tool_list = self._setup_tools()
        self.anthropic = Anthropic()
        self._max_tokens = 5000

    def _setup_tools(self) -> Tuple[Dict[str, MCPClient], List[Dict[str, str]]]:
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
        self, messages: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], str]:
        response = self.anthropic.messages.create(
            model=self.model,
            system=self.system_prompt,
            tools=self.tool_list,
            max_tokens=self._max_tokens,
            messages=messages,
        )

        while response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    tool_client = self.tool_client_map[block.name]
                    result = await tool_client.call_tool(block.name, block.input)
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
            response = self.anthropic.messages.create(
                model=self.model,
                system=self.system_prompt,
                tools=self.tool_list,
                max_tokens=self._max_tokens,
                messages=messages,
            )

        return messages, next(
            (b.text for b in response.content if b.type == "text"), "DONE"
        )
