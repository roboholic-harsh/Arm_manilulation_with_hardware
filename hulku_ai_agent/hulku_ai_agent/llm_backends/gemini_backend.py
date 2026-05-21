"""Gemini LLM backend with native function calling support."""

import os
import json
from typing import List

from hulku_ai_agent.llm_backends.base_backend import BaseLLMBackend, LLMResponse, ToolCall


# Type mapping from JSON Schema to Gemini proto types
_TYPE_MAP = {
    "string": "STRING",
    "number": "NUMBER",
    "integer": "INTEGER",
    "boolean": "BOOLEAN",
    "array": "ARRAY",
    "object": "OBJECT",
}


class GeminiBackend(BaseLLMBackend):
    """
    Google Gemini backend using the google-genai SDK.
    
    Uses gemini-2.0-flash by default — it has the best free-tier quota 
    and full function calling support. Users with Google AI Pro plan
    can also use gemini-2.5-flash or gemini-2.5-pro.
    
    API key resolution order:
        1. GEMINI_API_KEY environment variable (default)
        2. Explicitly passed api_key parameter
    """

    # Intialize with the configuration from yaml and env file
    def __init__(self, model_name: str = "gemini-2.0-flash", api_key: str = None):
        self._model_name = model_name
        self._api_key = api_key or os.environ.get("GEMINI_API_KEY", "")

        if not self._api_key:
            raise ValueError(
                "Gemini API key not found. Set GEMINI_API_KEY env var "
                "or pass api_key parameter."
            )

        # pyrefly: ignore [missing-import]
        import google.generativeai as genai
        genai.configure(api_key=self._api_key)
        self._genai = genai

    def _json_schema_to_proto_schema(self, schema: dict):
        """Convert a JSON Schema dict into a genai.protos.Schema object."""
        """Example schema on time of writing (mar 2026) for referance 
            {
                "type": enum (Type),
                "format": string,
                "title": string,
                "description": string,
                "nullable": boolean,
                "default": value,
                "items": {
                    object (Schema)
                },
                "minItems": string,
                "maxItems": string,
                "enum": [
                    string
                ],
                "properties": {
                    string: {
                    object (Schema)
                    },
                    ...
                },
                "propertyOrdering": [
                    string
                ],
                "required": [
                    string
                ],
                "minProperties": string,
                "maxProperties": string,
                "minimum": number,
                "maximum": number,
                "minLength": string,
                "maxLength": string,
                "pattern": string,
                "example": value,
                "anyOf": [
                    {
                    object (Schema)
                    }
                ],
                "additionalProperties": value,
                "ref": string,
                "defs": {
                    string: {
                    object (Schema)
                    },
                    ...
                }
            }
        """
        protos = self._genai.protos # shortens the name space path

        #### Not used schema_type ####
        # get the schema data type if exists otherwise fallback to object and capitalize it
        schema_type = schema.get("type", "object").upper()
        # Map JSON Schema type strings to proto Type enum
        # Gets actual reference like protos.Type.NUMBER for number (actually translation happen here)
        proto_type = getattr(protos.Type, _TYPE_MAP.get(schema.get("type", "object"), "OBJECT"))

        # initialize final keyword argument dictionary
        kwargs = {"type": proto_type}

        # if description in json format copy in the llm structure
        if "description" in schema:
            kwargs["description"] = schema["description"]

        # if the field is constrained it copies it so llm only generates allowed values
        if "enum" in schema:
            kwargs["enum"] = schema["enum"]

        # Handle properties (for object types)
        if "properties" in schema:
            props = {}
            for prop_name, prop_schema in schema["properties"].items():
                props[prop_name] = self._json_schema_to_proto_schema(prop_schema)
            kwargs["properties"] = props

        # Copies the list of fields that must be supplied so llm never skip it
        if "required" in schema:
            kwargs["required"] = schema["required"]

        # Handle array items
        if "items" in schema:
            kwargs["items"] = self._json_schema_to_proto_schema(schema["items"])

        # unpack the kwargs and create porotos final schema and return final object
        return protos.Schema(**kwargs)

    def _convert_tools(self, tools: list) -> list:
        """Convert our tool definitions to Gemini FunctionDeclaration format.""" 
        """
        Example Function declaration proto
        FunctionDeclaration(
            *,
            name: str,
            parameters: typing.Dict[str, typing.Any],
            description: typing.Optional[str] = None,
            response: typing.Optional[typing.Dict[str, typing.Any]] = None
        )
        for more: - (refer) https://docs.cloud.google.com/python/docs/reference/vertexai/latest/vertexai.generative_models.FunctionDeclaration?hl=en
        """
        protos = self._genai.protos
        # create an empty declaration variable
        declarations = []

        # Go through all tools
        for tool in tools:
            # get the params dict from the tool
            params = tool.get("parameters", {})
            # Convert JSON Schema to Gemini proto Schema
            proto_schema = self._json_schema_to_proto_schema(params)

            # Append the declaration
            declarations.append(
                protos.FunctionDeclaration(
                    name=tool["name"],
                    description=tool["description"],
                    parameters=proto_schema,
                )
            )
        # Here protos.Tool is a piece of code which lets the system interact with external systems
        # for more: - (refer) https://docs.cloud.google.com/python/docs/reference/aiplatform/latest/google.cloud.aiplatform_v1beta1.types.Tool?hl=en
        return [protos.Tool(function_declarations=declarations)]

    def chat(self, messages: list, tools: list) -> LLMResponse:
        # Separate system prompt from conversation
        system_instruction = None
        history = []
        latest_message = None

        for msg in messages:
            role = msg["role"]
            content = msg["content"]

            # Gemini required system prompts to be given at instantiation of the model
            if role == "system":
                system_instruction = content
            elif role == "user":
                latest_message = content
            elif role == "assistant":
                history.append({"role": "model", "parts": [content]})
            elif role == "tool_result":
                # Gemini expects function responses with this specific structure
                history.append({
                    "role": "function",
                    "parts": [self._genai.protos.Part(
                        function_response=self._genai.protos.FunctionResponse(
                            name=msg.get("tool_name", "unknown"),
                            response={"result": content}
                        )
                    )]
                })

        # All user messages except the last go into history
        user_msgs = [m for m in messages if m["role"] == "user"]
        if len(user_msgs) > 1:
            for um in user_msgs[:-1]:
                history.append({"role": "user", "parts": [um["content"]]})

        # convert the tools to the gemini format (protos)
        gemini_tools = self._convert_tools(tools) if tools else None

        # initialize model here only not before because system instruction and tools are required at instantiation
        # for more:- (refer) https://docs.cloud.google.com/python/docs/reference/vertexai/latest/vertexai.generative_models.GenerativeModel?hl=en
        model = self._genai.GenerativeModel(
            model_name=self._model_name,
            system_instruction=system_instruction,
            tools=gemini_tools,
        )

        # launches an active session seeded with the loaded historical messages
        chat = model.start_chat(history=history)
        # sends the latest message (user prompt)
        response = chat.send_message(latest_message)

        # Parse the response
        candidate = response.candidates[0]
        tool_calls = []
        text_parts = []

        for part in candidate.content.parts:
            if hasattr(part, 'function_call') and part.function_call and part.function_call.name:
                fc = part.function_call
                # Convert protobuf args to a clean Python dict
                args = {}
                if fc.args:
                    try:
                        # Use protobuf's json_format on the underlying proto message
                        from google.protobuf import json_format as proto_json
                        args = json.loads(proto_json.MessageToJson(fc._pb.args))
                    except Exception:
                        # Fallback: manually iterate the MapComposite
                        for k, v in fc.args.items():
                            args[k] = self._convert_proto_value(v)
                tool_calls.append(ToolCall(name=fc.name, args=args))
            elif hasattr(part, 'text') and part.text:
                text_parts.append(part.text)

        return LLMResponse(
            text="\n".join(text_parts) if text_parts else None,
            tool_calls=tool_calls,
        )

    # the decorator to make the method static which does not recieve any implicit first argument
    # defined as static because it is a pure utility function
    @staticmethod
    def _convert_proto_value(val):
        """Recursively convert a protobuf Value/MapComposite to native Python."""
        # if datatype is base then return as it is
        if isinstance(val, (str, int, float, bool)):
            return val
        # if datatype is list or tuple then convert each element to native python and return list
        if isinstance(val, (list, tuple)):
            return [GeminiBackend._convert_proto_value(v) for v in val]
        # if datatype is dict then convert each value to native python and return dict
        if isinstance(val, dict):
            return {k: GeminiBackend._convert_proto_value(v) for k, v in val.items()}
        # Try accessing as a proto Val object which is a wrapper which has number_value field containing the actual data
        if hasattr(val, 'number_value'):
            return val.number_value
        # same way wrapper for string_value
        if hasattr(val, 'string_value'):
            return val.string_value
        if hasattr(val, 'bool_value'):
            return val.bool_value
        # it is like a dict (behave like dict) but not the actual python dict 
        if hasattr(val, 'items'):
            return {k: GeminiBackend._convert_proto_value(v) for k, v in val.items()}
        # if unknown encountered just make it string and return it
        return str(val)
