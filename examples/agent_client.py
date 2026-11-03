"""Minimal OpenAI-compatible Agent call through the local gateway."""

import httpx


response = httpx.post(
    "http://127.0.0.1:8000/v1/chat/completions",
    json={
        "messages": [
            {"role": "system", "content": "Summarize the tool result briefly."},
            {"role": "user", "content": "What does the page say?"},
            {"role": "tool", "content": "The page describes a new software release."},
        ],
        "stream": False,
    },
    timeout=90,
)
response.raise_for_status()
print(response.json()["choices"][0]["message"]["content"])
