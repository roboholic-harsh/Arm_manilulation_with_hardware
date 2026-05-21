"""Mistral LLM backend with tool calling support."""

import os
import json
from typing import List

from hulku_ai_agent.llm_backends.base_backend import BaseLLMBackend, LLMResponse, ToolCall


class MistralBackend(BaseLLMBackend):
    """
    Mistral backend using the official Mistral Python SDK.
    
    API key resolution order:
        1. MISTRAL_API_KEY environment variable
        2. Explicitly passed api_key parameter
    """

    # Intialize with the configuration from yaml and env file
    def __init__(self, model_name: str = "mistral-large-latest", api_key: str = None):
        self._model_name = model_name
        self._api_key = api_key or os.environ.get("MISTRAL_API_KEY", "")

        if not self._api_key:
            raise ValueError(
                "Mistral API key not found. Set MISTRAL_API_KEY env var "
                "or pass api_key parameter."
            )

        # Try the new SDK import, fallback to the older mistralai.client if needed
        try:
            # pyrefly: ignore [missing-import]
            from mistralai import Mistral
        except ImportError:
            # pyrefly: ignore [missing-import]
            from mistralai.client import Mistral
            
        self._client = Mistral(api_key=self._api_key)

    # converting list of tool dict into Groq's tool dict format (Almost no change)
    def _convert_tools(self, tools: list) -> list:
        """Convert our tool definitions to Mistral-compatible format."""
        mistral_tools = []
        for tool in tools:
            mistral_tools.append({
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": tool["parameters"],
                }
            })
        return mistral_tools

    def chat(self, messages: list, tools: list) -> LLMResponse:
        # Convert messages to Mistral format
        # Initialize empty list for mistral.ai formatted messages
        mistral_messages = []
        for msg in messages:
            role = msg["role"]
            # If it is a tool result message then convert it into Mistral format
            if role == "tool_result":
                mistral_messages.append({
                    "role": "tool",
                    "content": msg["content"],
                    "tool_call_id": msg.get("tool_call_id", ""),
                    "name": msg.get("tool_name", ""),
                })
            # for other messages just copy the same
            else:
                out_msg = {
                    "role": role,
                    "content": msg["content"],
                }
                # Here we check tool_calls so that we can add tool call result if done by assistant in past
                if "tool_calls" in msg:
                    out_msg["tool_calls"] = msg["tool_calls"]
                
                mistral_messages.append(out_msg)

        # While the playground uses `client.beta.conversations.start`,
        # `client.chat.complete` is the robust standard for multi-turn 
        # ReAct agent loops passing history (including tool_results) natively.
        kwargs = {
            "model": self._model_name,
            "messages": mistral_messages,
            "temperature": 0.1,
        }

        # refer to groq_backend comment for same
        if tools:
            kwargs["tools"] = self._convert_tools(tools)
            kwargs["tool_choice"] = "auto"

        try:
            response = self._client.chat.complete(**kwargs)
        except Exception as e:
            return LLMResponse(text=f"Error calling Mistral API: {str(e)}")

        choice = response.choices[0]
        message = choice.message

        tool_calls = []
        if message.tool_calls:
            for tc in message.tool_calls:
                # Mistral tool call arguments might be passed as a string or dict 
                # depending on SDK version
                if isinstance(tc.function.arguments, str):
                    # if older sdk then it comes as json string load it and run it
                    args = json.loads(tc.function.arguments) if tc.function.arguments else {}
                else:
                    # if newer SDK then might come as python dict directly then use it directly
                    args = tc.function.arguments or {}
                    
                tool_calls.append(ToolCall(
                    name=tc.function.name,
                    args=args,
                    id=tc.id or "",
                ))

        # returns the response in LLMResponse format
        return LLMResponse(
            text=message.content if message.content else None,
            tool_calls=tool_calls,
        )
