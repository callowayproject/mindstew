"""Provider-agnostic model calls over one OpenAI-compatible HTTP implementation.

Covers OpenAI, Ollama, LM Studio and OpenRouter: ``base_url`` + optional Bearer key + extra headers. Callers use
``adapter.complete(...)`` / ``adapter.ping(...)`` via the module so tests can swap in the fake adapter.
"""

from typing import TYPE_CHECKING

import httpx
from pydantic import BaseModel, ValidationError

from mindstew.providers import get_secret

if TYPE_CHECKING:
    from mindstew.providers import Route

TIMEOUT = 60.0


class ProviderError(Exception):
    """Base for all adapter failures."""


class ProviderUnreachableError(ProviderError):
    """The endpoint could not be reached (connection refused, DNS, timeout)."""


class ProviderAuthError(ProviderError):
    """The endpoint rejected the credentials (HTTP 401/403)."""


class InvalidModelOutputError(ProviderError):
    """The model's reply was not valid JSON for the requested schema."""


def _headers(route: Route) -> dict[str, str]:
    """Build request headers: Bearer key from the keyring plus the provider's extra (possibly secret) headers."""
    p = route.provider
    headers = {}
    if key := get_secret(p.id, "api_key"):
        headers["Authorization"] = f"Bearer {key}"
    for h in p.headers:
        value = get_secret(p.id, f"header/{h.name}") if h.secret else h.value
        if value is not None:
            headers[h.name] = value
    return headers


def _request(route: Route, method: str, path: str, **kw: object) -> httpx.Response:
    """Send a request to the provider, mapping transport and auth failures to typed errors."""
    url = route.provider.base_url.rstrip("/") + path
    try:
        resp = httpx.request(method, url, headers=_headers(route), timeout=TIMEOUT, **kw)
    except httpx.TransportError as e:
        raise ProviderUnreachableError(f"{url}: {e}") from e
    if resp.status_code in (401, 403):
        raise ProviderAuthError(f"{route.provider.id}: HTTP {resp.status_code}")
    if resp.is_error:
        raise ProviderError(f"{route.provider.id}: HTTP {resp.status_code}: {resp.text[:200]}")
    return resp


def ping(route: Route) -> None:
    """Check the endpoint is reachable and accepts the credentials (``GET /models``).

    Args:
        route: The route whose provider to check.

    Raises:
        ProviderUnreachableError: if it cannot be reached.
        ProviderAuthError: if auth is rejected.
        ProviderError: for any other error status.
    """
    _request(route, "GET", "/models")


def complete[T: BaseModel](route: Route, messages: list[dict[str, str]], output_type: type[T]) -> T:
    """Run a chat completion constrained to ``output_type``'s JSON schema and return the validated object.

    Args:
        route: The route (provider and model) to call.
        messages: Chat messages, OpenAI format.
        output_type: Pydantic model the reply must conform to.

    Returns:
        The validated ``output_type`` instance.

    Raises:
        InvalidModelOutputError: if the reply is not valid JSON for ``output_type``.
        ProviderUnreachableError, ProviderAuthError, ProviderError: as for ``ping``.
    """
    body = {
        "model": route.model,
        "messages": messages,
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": output_type.__name__, "schema": output_type.model_json_schema(), "strict": True},
        },
    }
    resp = _request(route, "POST", "/chat/completions", json=body)
    try:
        content = resp.json()["choices"][0]["message"]["content"]
        return output_type.model_validate_json(content)
    except (ValidationError, ValueError, LookupError, TypeError) as e:
        raise InvalidModelOutputError(f"{route.provider.id}/{route.model}: {e}") from e
