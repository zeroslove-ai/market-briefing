import json

import delivery_adapters


class _Response:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return json.dumps(self.payload).encode()


def test_telegram_adapter_posts_each_message(monkeypatch):
    calls = []

    def fake_urlopen(request, timeout):
        calls.append((request, timeout))
        return _Response({"ok": True, "result": {"message_id": len(calls)}})

    monkeypatch.setattr(delivery_adapters.urllib.request, "urlopen", fake_urlopen)
    result = delivery_adapters.send_telegram(
        ["one", "two"], bot_token="TOKEN", chat_id="-123", thread_id="7"
    )
    assert len(result) == 2
    assert len(calls) == 2
    sent = json.loads(calls[0][0].data)
    assert sent["message_thread_id"] == 7
    assert sent["chat_id"] == "-123"


def test_gmail_smtp_builds_multipart_message(monkeypatch):
    sent = {}

    class FakeSMTP:
        def __init__(self, host, port, timeout):
            sent["connect"] = (host, port, timeout)

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def login(self, user, password):
            sent["login"] = (user, password)

        def send_message(self, message):
            sent["message"] = message

    monkeypatch.setattr(delivery_adapters.smtplib, "SMTP_SSL", FakeSMTP)
    delivery_adapters.send_gmail_smtp(
        subject="subject",
        plain="plain",
        html="<b>html</b>",
        smtp_user="me@example.com",
        app_password="secret",
        recipients=["to@example.com"],
    )
    assert sent["login"] == ("me@example.com", "secret")
    assert sent["message"]["To"] == "to@example.com"
    assert sent["message"].is_multipart()
