"""
Shared Groq LLM client + agentic tool-use loop.
All agents import this module to call Groq with tool support.
"""

import json
import sys
import os
from typing import List, Dict, Any, Callable

from groq import Groq

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
from config import GROQ_API_KEY, GROQ_MODEL

# Singleton client
_client = None

def get_client() -> Groq:
    global _client
    if _client is None:
        _client = Groq(api_key=GROQ_API_KEY)
    return _client


def run_agent(
    system_prompt: str,
    user_query: str,
    tools: List[Dict],
    tool_functions: Dict[str, Callable],
    model: str = GROQ_MODEL,
    max_iterations: int = 5,
) -> str:
    """
    Core agentic loop:
    1. Send query + tools to Groq
    2. If Groq calls a tool → execute it → send result back
    3. Repeat until Groq returns a plain text response (no more tool calls)
    """
    client = get_client()
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_query},
    ]

    for iteration in range(max_iterations):
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=tools,
            tool_choice="auto",
            max_tokens=1024,
        )

        msg = response.choices[0].message

        # If no tool calls, we have a final answer
        if not msg.tool_calls:
            return msg.content or "I could not generate a response."

        # Add assistant message (with tool_calls) to history
        messages.append({
            "role": "assistant",
            "content": msg.content or "",
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    }
                }
                for tc in msg.tool_calls
            ]
        })

        # Execute each tool call and append results
        for tool_call in msg.tool_calls:
            fn_name = tool_call.function.name
            try:
                fn_args = json.loads(tool_call.function.arguments)
            except json.JSONDecodeError:
                fn_args = {}

            if fn_name in tool_functions:
                try:
                    result = tool_functions[fn_name](**fn_args)
                    result_str = json.dumps(result, default=str)
                except Exception as e:
                    result_str = json.dumps({"error": str(e)})
            else:
                result_str = json.dumps({"error": f"Unknown tool: {fn_name}"})

            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": result_str,
            })

    return "Max iterations reached. Please try a more specific question."
