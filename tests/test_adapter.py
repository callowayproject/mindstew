"""The OpenAI-compatible adapter, exercised over real HTTP against a localhost stub; the CLI `provider test`."""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import TYPE_CHECKING

import pytest
from click.testing import CliRunner
from pydantic import BaseModel

from mindstew import adapter
from mindstew.adapter import InvalidModelOutputError, ProviderAuthError, ProviderUnreachableError
from mindstew.cli import cli
from mindstew.providers import Header, Provider, Route, add_provider

if TYPE_CHECKING:
    from collections.abc import Iterator


class Answer(BaseModel):
    """Structured output used by the tests."""

    title: str
    score: int


class Stub:
    """A local OpenAI-compatible server: records requests, replies with ``content`` or an error status."""

    def __init__(self) -> None:
        self.requests: list[dict] = []
        self.content = '{"title": "hi", "score": 3}'
        self.status = 200
        self.expected_key = "sk-good"  # pragma: allowlist secret
        stub = self

        class Handler(BaseHTTPRequestHandler):
            def _serve(self) -> None:
                length = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(length)) if length else None
                stub.requests.append({"path": self.path, "headers": dict(self.headers), "body": body})
                if self.headers.get("Authorization") != f"Bearer {stub.expected_key}":
                    payload: dict[str, object]
                    status, payload = 401, {"error": "bad key"}
                elif self.path.endswith("/models"):
                    status, payload = stub.status, {"data": []}
                else:
                    status = stub.status
                    payload = {"choices": [{"message": {"content": stub.content}}]}
                data = json.dumps(payload).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            do_GET = do_POST = _serve  # ruff: ignore[mixed-case-variable-in-class-scope]

            def log_message(self, *args: object) -> None:
                pass

        self.server = HTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_port}/v1"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()


@pytest.fixture
def stub() -> Iterator[Stub]:
    """Run a stub provider server for one test."""
    s = Stub()
    yield s
    s.server.shutdown()
    s.server.server_close()


def _route(url: str, headers: list[Header] | None = None) -> Route:
    provider = Provider("local", "Local", "openai-compatible", url, headers or [])
    add_provider(provider, api_key="sk-good")  # pragma: allowlist secret
    return Route("chat", provider, "gpt-x")


def test_complete_returns_validated_object_and_sends_schema_and_auth(stub: Stub) -> None:
    """Adapter behaviour."""
    route = _route(stub.url, headers=[Header("X-Org", "acme")])
    result = adapter.complete(route, [{"role": "user", "content": "hello"}], Answer)
    assert result == Answer(title="hi", score=3)
    req = stub.requests[0]
    assert req["path"] == "/v1/chat/completions"
    assert req["headers"]["Authorization"] == "Bearer sk-good"
    assert req["headers"]["X-Org"] == "acme"
    assert req["body"]["model"] == "gpt-x"
    assert req["body"]["messages"] == [{"role": "user", "content": "hello"}]
    assert req["body"]["response_format"]["type"] == "json_schema"
    assert req["body"]["response_format"]["json_schema"]["schema"]["properties"].keys() == {"title", "score"}


def test_secret_header_comes_from_keyring(stub: Stub) -> None:
    """Adapter behaviour."""
    provider = Provider("local", "Local", "openai-compatible", stub.url, [Header("X-Tok", secret=True)])
    add_provider(provider, api_key="sk-good", header_secrets={"X-Tok": "s3cret"})  # pragma: allowlist secret
    adapter.complete(Route("chat", provider, "m"), [], Answer)
    assert stub.requests[0]["headers"]["X-Tok"] == "s3cret"  # pragma: allowlist secret


@pytest.mark.parametrize("content", ["not json", '{"title": "x"}', '{"title": "x", "score": "many"}'])
def test_invalid_model_output_raises_typed_error(stub: Stub, content: str) -> None:
    """Adapter behaviour."""
    stub.content = content
    with pytest.raises(InvalidModelOutputError):
        adapter.complete(_route(stub.url), [], Answer)


def test_complete_auth_failure(stub: Stub) -> None:
    """Adapter behaviour."""
    stub.expected_key = "other"  # pragma: allowlist secret
    with pytest.raises(ProviderAuthError):
        adapter.complete(_route(stub.url), [], Answer)


def test_complete_unreachable() -> None:
    """Adapter behaviour."""
    with pytest.raises(ProviderUnreachableError):
        adapter.complete(_route("http://127.0.0.1:1/v1"), [], Answer)


def test_ping_ok_and_failures(stub: Stub) -> None:
    """Adapter behaviour."""
    route = _route(stub.url)
    adapter.ping(route)
    assert stub.requests[0]["path"] == "/v1/models"
    stub.expected_key = "other"  # pragma: allowlist secret
    with pytest.raises(ProviderAuthError):
        adapter.ping(route)
    with pytest.raises(ProviderUnreachableError):
        adapter.ping(_route("http://127.0.0.1:1/v1"))


def test_cli_provider_test_exit_codes(stub: Stub) -> None:
    """Adapter behaviour."""
    add_provider(
        Provider("local", "Local", "openai-compatible", stub.url),
        api_key="sk-good",  # pragma: allowlist secret
    )  # pragma: allowlist secret
    run = CliRunner().invoke
    ok = run(cli, ["provider", "test", "local"])
    assert ok.exit_code == 0
    assert "reachable" in ok.output

    stub.expected_key = "other"  # pragma: allowlist secret
    auth = run(cli, ["provider", "test", "local"])
    assert auth.exit_code == 2
    assert "auth-failed" in auth.output

    add_provider(Provider("dead", "Dead", "openai-compatible", "http://127.0.0.1:1/v1"))
    dead = run(cli, ["provider", "test", "dead"])
    assert dead.exit_code == 3
    assert "unreachable" in dead.output

    assert run(cli, ["provider", "test", "nope"]).exit_code == 1


def test_fake_adapter_returns_canned_responses_and_logs_calls(fake_adapter) -> None:
    """Adapter behaviour."""
    route = Route("chat", Provider("p", "P", "openai-compatible", "http://x"), "m")
    fake_adapter.respond(Answer(title="a", score=1))
    msgs = [{"role": "user", "content": "q"}]
    assert adapter.complete(route, msgs, Answer) == Answer(title="a", score=1)
    assert fake_adapter.calls == [(route, msgs, Answer)]
    fake_adapter.respond(InvalidModelOutputError("bad"))
    with pytest.raises(InvalidModelOutputError):
        adapter.complete(route, msgs, Answer)
    with pytest.raises(AssertionError):  # nothing canned left
        adapter.complete(route, msgs, Answer)
