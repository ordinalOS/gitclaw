#!/usr/bin/env python3
"""
Common utilities for all agents.

Provides:
- LLM API interaction with error handling
- Environment variable access with validation
- Response parsing and validation
"""

import os
import json
import sys
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
from datetime import datetime


def get_env(key: str, default: str = None) -> str:
    """
    Get environment variable with fallback and validation.
    
    Args:
        key: Environment variable name
        default: Default value if not found
        
    Returns:
        Environment variable value or default
        
    Raises:
        ValueError: If required var (no default) is missing
    """
    value = os.environ.get(key, default)
    if value is None:
        raise ValueError(f"Required environment variable not set: {key}")
    if isinstance(value, str) and not value.strip():
        raise ValueError(f"Environment variable is empty: {key}")
    return value


def call_llm(prompt: str, model: str = None, temperature: float = 0.7, max_tokens: int = 2000) -> str:
    """
    Call the LLM API with comprehensive error handling.
    
    Args:
        prompt: The prompt to send to the LLM
        model: Model name (defaults to CLAUDE_MODEL env var)
        temperature: Temperature for response generation (0.0-1.0)
        max_tokens: Maximum tokens in response
        
    Returns:
        LLM response text
        
    Raises:
        RuntimeError: If API call fails, times out, or returns invalid response
        ValueError: If prompt is empty or settings are invalid
    """
    if not prompt or not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("Prompt cannot be empty")
    
    if temperature < 0.0 or temperature > 1.0:
        raise ValueError(f"Temperature must be 0.0-1.0, got {temperature}")
    
    if max_tokens < 1:
        raise ValueError(f"max_tokens must be >= 1, got {max_tokens}")
    
    try:
        model = model or get_env("CLAUDE_MODEL", "claude-3-5-sonnet-20241022")
        api_key = get_env("ANTHROPIC_API_KEY")
    except ValueError as e:
        raise RuntimeError(f"Configuration error: {e}")
    
    if not api_key.strip():
        raise RuntimeError("ANTHROPIC_API_KEY is empty")
    
    try:
        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        
        body = json.dumps({
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [{"role": "user", "content": prompt}],
        }).encode("utf-8")
        
        req = Request(url, data=body, headers=headers, method="POST")
        
        try:
            with urlopen(req, timeout=30) as response:
                response_data = json.loads(response.read().decode("utf-8"))
        except HTTPError as e:
            error_body = e.read().decode("utf-8")
            try:
                error_detail = json.loads(error_body).get("error", {}).get("message", error_body)
            except json.JSONDecodeError:
                error_detail = error_body
            raise RuntimeError(f"API returned {e.code}: {error_detail}")
        except URLError as e:
            raise RuntimeError(f"Network error calling LLM API: {e.reason}")
        except TimeoutError:
            raise RuntimeError("LLM API call timed out after 30 seconds")
        
        # Validate response structure
        if "content" not in response_data or not response_data["content"]:
            raise RuntimeError("API returned empty content")
        
        if "text" not in response_data["content"][0]:
            raise RuntimeError(f"Unexpected API response format: {list(response_data.get('content', [{}])[0].keys())}")
        
        result = response_data["content"][0]["text"]
        if not result or not isinstance(result, str):
            raise RuntimeError("API returned non-string or empty text")
        
        return result.strip()
        
    except RuntimeError:
        raise
    except Exception as e:
        raise RuntimeError(f"Unexpected error calling LLM API: {type(e).__name__}: {e}")


def parse_json_response(response: str, agent_name: str = "Unknown") -> dict:
    """
    Parse and validate JSON from LLM response with error handling.
    
    Args:
        response: LLM response text (should be JSON)
        agent_name: Agent name for error messages
        
    Returns:
        Parsed JSON dict
        
    Raises:
        ValueError: If response is not valid JSON
    """
    if not response:
        raise ValueError(f"[{agent_name}] Cannot parse empty response")
    
    try:
        data = json.loads(response)
        if not isinstance(data, dict):
            raise ValueError(f"[{agent_name}] Expected JSON object, got {type(data).__name__}")
        return data
    except json.JSONDecodeError as e:
        raise ValueError(f"[{agent_name}] Invalid JSON: {e.msg} at line {e.lineno}")


def log_error(agent_name: str, error: Exception, context: str = "") -> None:
    """
    Log error to stderr with timestamp and context.
    
    Args:
        agent_name: Name of the agent experiencing error
        error: The exception that occurred
        context: Additional context string
    """
    timestamp = datetime.utcnow().isoformat()
    message = f"[{timestamp}] {agent_name} ERROR: {error}"
    if context:
        message += f" (context: {context})"
    print(message, file=sys.stderr)


def safe_get(data: dict, *keys, default=None):
    """
    Safely traverse nested dict with multiple keys.
    
    Args:
        data: Dictionary to traverse
        *keys: Keys to access in sequence
        default: Default value if any key is missing
        
    Returns:
        Value at nested key path or default
    """
    current = data
    for key in keys:
        if isinstance(current, dict):
            current = current.get(key)
            if current is None:
                return default
        else:
            return default
    return current


def format_timestamp(dt: datetime = None) -> str:
    """
    Format datetime as ISO 8601 string.
    
    Args:
        dt: Datetime object (defaults to now)
        
    Returns:
        ISO 8601 formatted string
    """
    if dt is None:
        dt = datetime.utcnow()
    return dt.isoformat() + "Z"
