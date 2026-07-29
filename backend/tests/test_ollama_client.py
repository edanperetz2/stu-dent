import httpx

from app.services import ollama_client


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def test_generate_json_returns_none_when_model_returns_non_dict_json(monkeypatch):
    # A real model can emit technically-valid JSON that isn't an object
    # (e.g. a bare list or string) even under format="json" -- callers only
    # ever call .get(...) on the result, so this must degrade to None
    # rather than let an AttributeError escape later.
    monkeypatch.setattr(
        httpx, "post", lambda *a, **k: _FakeResponse({"response": '["not", "a", "dict"]'})
    )
    assert ollama_client.generate_json("prompt") is None


def test_generate_json_returns_none_when_response_field_is_null(monkeypatch):
    monkeypatch.setattr(httpx, "post", lambda *a, **k: _FakeResponse({"response": None}))
    assert ollama_client.generate_json("prompt") is None


def test_generate_json_returns_dict_on_well_formed_response(monkeypatch):
    monkeypatch.setattr(
        httpx, "post", lambda *a, **k: _FakeResponse({"response": '{"summary": "ok"}'})
    )
    assert ollama_client.generate_json("prompt") == {"summary": "ok"}
