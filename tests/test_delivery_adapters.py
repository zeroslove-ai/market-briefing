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
