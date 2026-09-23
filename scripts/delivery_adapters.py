"""Direct delivery adapters for channels owned by the EC2 runtime.

Email is intentionally NOT sent here. Gmail delivery is owned by the connected
Gmail MCP/ChatGPT Work lane so no Gmail password/OAuth token is stored on EC2.
"""

from __future__ import annotations

import json
import urllib.request


def send_telegram(messages: list[str], *, bot_token: str, chat_id: str, thread_id: str | None = None, timeout: int = 20) -> list[dict]:
    if not bot_token or not chat_id:
        raise ValueError("Telegram bot_token/chat_id required")
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    responses = []
    for message in messages:
        payload = {
            "chat_id": chat_id,
            "text": message,
            "disable_web_page_preview": True,
        }
        if thread_id:
            payload["message_thread_id"] = int(thread_id)
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            document = json.loads(response.read())
        if not document.get("ok"):
            raise RuntimeError(f"Telegram API failed: {document}")
        responses.append(document.get("result", {}))
    return responses
