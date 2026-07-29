import httpx

from app.services import ollama_client


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def _status_error(status_code: int) -> httpx.HTTPStatusError:
    request = httpx.Request("POST", "http://ollama/api/generate")
    response = httpx.Response(status_code, request=request)
    return httpx.HTTPStatusError(str(status_code), request=request, response=response)


class _FailingStatusResponse:
    def __init__(self, status_code: int):
        self._status_code = status_code

    def raise_for_status(self):
        raise _status_error(self._status_code)


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


def test_generate_json_retries_once_on_connect_error(monkeypatch):
    # A connection-level failure (container not up yet, brief network blip)
    # is exactly the transient case a single retry is meant to paper over.
    calls = []

    def fake_post(*args, **kwargs):
        calls.append(1)
        if len(calls) == 1:
            raise httpx.ConnectError("connection refused")
        return _FakeResponse({"response": '{"summary": "ok"}'})

    monkeypatch.setattr(httpx, "post", fake_post)
    assert ollama_client.generate_json("prompt") == {"summary": "ok"}
    assert len(calls) == 2


def test_generate_json_does_not_retry_on_read_timeout(monkeypatch):
    # A read-timeout means the model was actively generating, just slow --
    # retrying would only double the wait for an identical failure.
    calls = []

    def fake_post(*args, **kwargs):
        calls.append(1)
        raise httpx.ReadTimeout("model took too long")

    monkeypatch.setattr(httpx, "post", fake_post)
    assert ollama_client.generate_json("prompt") is None
    assert len(calls) == 1


def test_generate_json_retries_once_on_5xx_status(monkeypatch):
    # A 5xx from Ollama itself (e.g. momentarily overloaded) is plausibly
    # transient, same reasoning as a connect-level failure.
    calls = []

    def fake_post(*args, **kwargs):
        calls.append(1)
        if len(calls) == 1:
            return _FailingStatusResponse(503)
        return _FakeResponse({"response": '{"summary": "ok"}'})

    monkeypatch.setattr(httpx, "post", fake_post)
    assert ollama_client.generate_json("prompt") == {"summary": "ok"}
    assert len(calls) == 2


def test_generate_json_does_not_retry_on_4xx_status(monkeypatch):
    # A 4xx (e.g. model not pulled) is a permanent condition -- retrying
    # would just fail identically again.
    calls = []

    def fake_post(*args, **kwargs):
        calls.append(1)
        return _FailingStatusResponse(404)

    monkeypatch.setattr(httpx, "post", fake_post)
    assert ollama_client.generate_json("prompt") is None
    assert len(calls) == 1
