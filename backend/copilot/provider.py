"""LLM Provider abstraction and Copilot Tool-Calling adapter for Nodexa.

Reuses the core LLMProvider architecture in backend.agent.provider while providing
structured tool-calling integration for Ask Sentinel Copilot. Supports Gemini,
OpenAI, and HTTP-compatible models with resilient deterministic fallback.
"""
import json
import os
import re
from typing import Any, Dict, List, Optional, Tuple
import httpx

from backend.agent.provider import (
    LLMProvider,
    DeterministicMockLLMProvider,
    HTTPLLMProvider,
    get_llm_provider as get_core_llm_provider,
)
from backend.logging import logger


class CopilotLLMProvider:
    """Manages LLM interaction for the Copilot tool-calling and grounded synthesis layer."""

    @staticmethod
    def get_provider_status() -> Dict[str, Any]:
        """Returns the active provider name and whether a real remote LLM is configured."""
        provider_name = os.getenv("LLM_PROVIDER", "mock").lower()
        api_key = os.getenv("LLM_API_KEY", "")
        model = os.getenv("LLM_MODEL", "gpt-4o-mini" if provider_name == "openai" else "gemini-1.5-flash")
        has_credentials = bool(api_key.strip())
        is_real = provider_name in ("gemini", "openai", "http", "anthropic") and has_credentials

        return {
            "provider_name": provider_name,
            "has_credentials": has_credentials,
            "is_real_llm_configured": is_real,
            "model": model,
        }

    @staticmethod
    def plan_tools_with_llm(
        question: str,
        tool_definitions: List[Dict[str, Any]],
        context: Optional[Dict[str, Any]] = None,
    ) -> Tuple[List[Dict[str, Any]], str, bool]:
        """Invokes the configured LLM with tool definitions to select necessary read-only tools.
        
        Returns:
            tools_to_call: List of {"tool_name": str, "arguments": dict}
            reasoning: str explaining the tool selection
            is_real_llm: bool indicating if a real remote LLM successfully produced the plan
        """
        status = CopilotLLMProvider.get_provider_status()
        if not status["is_real_llm_configured"]:
            return [], "", False

        api_key = os.getenv("LLM_API_KEY", "")
        base_url = os.getenv("LLM_BASE_URL", "")
        provider = status["provider_name"]
        model = status["model"]

        if not base_url:
            if provider == "gemini":
                base_url = "https://generativelanguage.googleapis.com/v1beta/openai"
            else:
                base_url = "https://api.openai.com/v1"

        system_instruction = (
            "You are Nodexa Finance Copilot.\n"
            "You answer questions about financial datasets using the supplied read-only tools.\n"
            "You MUST select the minimum set of tools required to answer the user's question.\n"
            "Never select mutation or write tools.\n"
            "Return a JSON object with 'tool_calls': [ {'tool_name': '...', 'arguments': {...}} ] and 'reasoning': '...'."
        )

        user_content = f"User Question: {question}"
        if context:
            user_content += f"\nContext: {json.dumps(context)}"

        payload = {
            "model": model,
            "temperature": 0.0,
            "messages": [
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": user_content},
            ],
            "tools": tool_definitions,
            "tool_choice": "auto",
        }

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        try:
            with httpx.Client(timeout=10.0) as client:
                res = client.post(f"{base_url}/chat/completions", json=payload, headers=headers)
                res.raise_for_status()
                data = res.json()
                msg = data["choices"][0]["message"]
                
                tool_calls = []
                if "tool_calls" in msg and msg["tool_calls"]:
                    for tc in msg["tool_calls"]:
                        fn = tc.get("function", {})
                        t_name = fn.get("name", "")
                        args_str = fn.get("arguments", "{}")
                        try:
                            args_dict = json.loads(args_str) if isinstance(args_str, str) else args_str
                        except Exception:
                            args_dict = {}
                        if t_name:
                            tool_calls.append({"tool_name": t_name, "arguments": args_dict})

                reasoning = msg.get("content") or "Selected tools via LLM tool-calling."
                if tool_calls:
                    return tool_calls, reasoning, True
        except Exception as e:
            logger.warning(
                operation="COPILOT_LLM_TOOL_PLAN_ERROR",
                message=f"Remote LLM tool calling failed ({str(e)}), falling back to deterministic semantic selector.",
            )

        return [], "", False

    @staticmethod
    def synthesize_with_llm(
        question: str,
        tool_results: Dict[str, Any],
        tools_used: List[str],
    ) -> Tuple[Optional[str], bool]:
        """Asks the real remote LLM to synthesize the final answer strictly grounded in tool results."""
        status = CopilotLLMProvider.get_provider_status()
        if not status["is_real_llm_configured"]:
            return None, False

        api_key = os.getenv("LLM_API_KEY", "")
        base_url = os.getenv("LLM_BASE_URL", "")
        provider = status["provider_name"]
        model = status["model"]

        if not base_url:
            if provider == "gemini":
                base_url = "https://generativelanguage.googleapis.com/v1beta/openai"
            else:
                base_url = "https://api.openai.com/v1"

        system_instruction = (
            "You are Nodexa Finance Copilot.\n"
            "Synthesize a clear, concise natural language answer to the user's question using ONLY the provided tool results.\n"
            "You MUST NOT invent numbers or calculate unprovided financial metrics.\n"
            "Address only what the user asked. Do NOT mention unrelated exceptions or open exposure unless the user specifically asked for them.\n"
            "Always cite financial amounts with currency symbols where appropriate."
        )

        user_content = (
            f"Question: {question}\n\n"
            f"Authoritative Tool Results:\n{json.dumps(tool_results, indent=2)}\n\n"
            f"Tools Used: {', '.join(tools_used)}"
        )

        payload = {
            "model": model,
            "temperature": 0.0,
            "messages": [
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": user_content},
            ],
        }

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        try:
            with httpx.Client(timeout=12.0) as client:
                res = client.post(f"{base_url}/chat/completions", json=payload, headers=headers)
                res.raise_for_status()
                data = res.json()
                content = data["choices"][0]["message"]["content"]
                if content and content.strip():
                    return content.strip(), True
        except Exception as e:
            logger.warning(
                operation="COPILOT_LLM_SYNTHESIS_ERROR",
                message=f"Remote LLM synthesis failed ({str(e)}), falling back to grounded deterministic synthesizer.",
            )

        return None, False
