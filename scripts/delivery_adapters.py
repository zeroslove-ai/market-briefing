"""Delivery adapters. Secrets are accepted only from environment/config arguments."""

from __future__ import annotations

import json
import smtplib
import urllib.request
from email.message import EmailMessage


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


def send_gmail_smtp(
    *,
    subject: str,
    plain: str,
    html: str,
    smtp_user: str,
    app_password: str,
    recipients: list[str],
    sender: str | None = None,
    host: str = "smtp.gmail.com",
    port: int = 465,
) -> None:
    if not smtp_user or not app_password or not recipients:
        raise ValueError("Gmail SMTP user/app password/recipients required")
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = sender or smtp_user
    message["To"] = ", ".join(recipients)
    message.set_content(plain)
    message.add_alternative(html, subtype="html")
    with smtplib.SMTP_SSL(host, port, timeout=30) as smtp:
        smtp.login(smtp_user, app_password)
        smtp.send_message(message)
