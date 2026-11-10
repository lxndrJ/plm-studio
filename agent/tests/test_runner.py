import json

import httpx

from plm_agent.runner import PlmAgent
from plm_agent.toolgen import ToolCatalog, generate

OPENAPI = {
    "openapi": "3.1.0",
    "info": {"title": "t", "version": "1"},
    "paths": {
        "/api/v1/parts": {
            "get": {
                "summary": "List parts",
                "parameters": [
                    {
                        "name": "query",
                        "in": "query",
                        "required": False,
                        "schema": {"type": "string"},
                    }
                ],
                "responses": {"200": {"description": "ok"}},
            },
            "post": {
                "summary": "Create part",
                "parameters": [
                    {
                        "name": "direct",
                        "in": "query",
                        "required": False,
                        "schema": {"type": "boolean"},
                    }
                ],
                "requestBody": {
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string"},
                                    "class_code": {"type": "string"},
                                    "reason": {"type": "string"},
                                },
                                "required": ["name", "class_code"],
                            }
                        }
                    }
                },
                "responses": {
                    "201": {"description": "created"},
                    "202": {"description": "proposed"},
                },
            },
        },
    },
}


def _llm_response(content=None, tool_calls=None):
    message = {"role": "assistant", "content": content}
    if tool_calls:
        message["tool_calls"] = tool_calls
    return {"choices": [{"message": message}]}


def _call(call_id, name, arguments):
    return {
        "id": call_id,
        "type": "function",
        "function": {"name": name, "arguments": json.dumps(arguments)},
    }


def _make_agent(state, transport):
    catalog = generate(OPENAPI)
    return PlmAgent(
        plm_base_url="http://plm.test",
        llm_base_url="http://llm.test/v1",
        api_key="llm-key",
        model="plm-chat",
        email="agent@example.com",
        password="pw",
        catalog=catalog,
        system_prompt="sys",
        transport=transport,
        sleep=lambda _: None,
    )


def test_agent_flow_login_toolcall_202_never_self_approves():
    state = {"requests": [], "llm_calls": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        state["requests"].append(
            (request.method, url, request.headers.get("authorization"), request.content)
        )
        if url.endswith("/api/v1/auth/login"):
            return httpx.Response(200, json={"access_token": "tok", "refresh_token": "r"})
        if url.endswith("/chat/completions"):
            state["llm_calls"] += 1
            if state["llm_calls"] == 1:
                return httpx.Response(
                    200,
                    json=_llm_response(tool_calls=[_call("c1", "get_parts", {"query": "TEST"})]),
                )
            if state["llm_calls"] == 2:
                return httpx.Response(
                    200,
                    json=_llm_response(
                        tool_calls=[
                            _call(
                                "c2",
                                "post_parts",
                                {"name": "Neues Teil", "class_code": "TEST", "reason": "Demo"},
                            )
                        ]
                    ),
                )
            return httpx.Response(
                200,
                json=_llm_response(
                    content="Fertig: 1 Treffer, Anlage als Vorschlag (conf-1) offen."
                ),
            )
        if url.endswith("/api/v1/parts") and request.method == "GET":
            return httpx.Response(
                200,
                json=[{"part_number": "P-000001", "name": "TEST Hemd 0001", "part_type": "part"}],
            )
        if url.endswith("/api/v1/parts") and request.method == "POST":
            return httpx.Response(
                202,
                json={
                    "confirmation_id": "conf-1",
                    "status": "proposed",
                    "summary": "create part 'Neues Teil'",
                },
            )
        return httpx.Response(404, json={"detail": "unhandled", "url": url})

    agent = _make_agent(state, httpx.MockTransport(handler))
    result = agent.run("Suche TEST-Teile und lege 'Neues Teil' an")

    assert result.startswith("Fertig:")
    logins = [r for r in state["requests"] if r[1].endswith("/api/v1/auth/login")]
    assert len(logins) == 1
    plm_calls = [r for r in state["requests"] if "plm.test" in r[1]]
    assert all(r[2] == "Bearer tok" for r in plm_calls if not r[1].endswith("/auth/login"))

    post = next(r for r in state["requests"] if r[1].endswith("/api/v1/parts") and r[0] == "POST")
    assert json.loads(post[3]) == {"name": "Neues Teil", "class_code": "TEST", "reason": "Demo"}
    assert "direct" not in post[1]

    assert not any(
        "/confirmations/" in r[1] and ("approve" in r[1] or "reject" in r[1])
        for r in state["requests"]
    )

    llm_bodies = [json.loads(r[3]) for r in state["requests"] if r[1].endswith("/chat/completions")]
    tool_msgs = [m for b in llm_bodies for m in b["messages"] if m["role"] == "tool"]
    proposed = [m for m in tool_msgs if "conf-1" in m["content"]]
    assert proposed, "the 202 proposal must be reported back to the LLM"
    assert (
        "never approve" in proposed[0]["content"].lower()
        or "not committed" in proposed[0]["content"].lower()
    )


def test_retry_on_5xx_then_success():
    state = {"requests": [], "llm_calls": 0, "part_attempts": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        state["requests"].append((request.method, url))
        if url.endswith("/api/v1/auth/login"):
            return httpx.Response(200, json={"access_token": "tok"})
        if url.endswith("/chat/completions"):
            state["llm_calls"] += 1
            if state["llm_calls"] == 1:
                return httpx.Response(
                    200, json=_llm_response(tool_calls=[_call("c1", "get_parts", {})])
                )
            return httpx.Response(200, json=_llm_response(content="ok nach retry"))
        if url.endswith("/api/v1/parts") and request.method == "GET":
            state["part_attempts"] += 1
            if state["part_attempts"] < 3:
                return httpx.Response(500, json={"detail": "boom"})
            return httpx.Response(200, json=[])
        return httpx.Response(404, json={"detail": "unhandled"})

    agent = _make_agent(state, httpx.MockTransport(handler))
    assert agent.run("liste teile") == "ok nach retry"
    assert state["part_attempts"] == 3


def test_409_is_passed_through_to_llm():
    state = {"requests": [], "llm_calls": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        state["requests"].append(
            (request.method, url, request.headers.get("authorization"), request.content)
        )
        if url.endswith("/api/v1/auth/login"):
            return httpx.Response(200, json={"access_token": "tok"})
        if url.endswith("/chat/completions"):
            state["llm_calls"] += 1
            if state["llm_calls"] == 1:
                return httpx.Response(
                    200,
                    json=_llm_response(
                        tool_calls=[
                            _call("c1", "post_parts", {"name": "Dup", "class_code": "MECH"})
                        ]
                    ),
                )
            return httpx.Response(200, json=_llm_response(content="409 gesehen, ich frage nach"))
        if url.endswith("/api/v1/parts") and request.method == "POST":
            return httpx.Response(
                409,
                json={
                    "detail": "duplicate",
                    "code": "duplicate_part",
                    "details": {"candidates": [{"part_number": "P-000001"}]},
                },
            )
        return httpx.Response(404, json={"detail": "unhandled"})

    agent = _make_agent(state, httpx.MockTransport(handler))
    assert agent.run("leg Dup an") == "409 gesehen, ich frage nach"
    llm_bodies = [json.loads(r[3]) for r in state["requests"] if r[1].endswith("/chat/completions")]
    tool_msgs = [m for b in llm_bodies for m in b["messages"] if m["role"] == "tool"]
    assert any("duplicate_part" in m["content"] and "P-000001" in m["content"] for m in tool_msgs)


def test_llm_url_normalization_supports_direct_provider():
    """OPENAI_BASE_URL may be a LiteLLM proxy or a direct provider (e.g. Mistral);
    the runner must normalize to <base>/v1/chat/completions exactly once."""

    def make(llm_base: str) -> PlmAgent:
        return PlmAgent(
            plm_base_url="http://plm.test",
            llm_base_url=llm_base,
            api_key="key",
            model="mistral-large-latest",
            email="a@b.c",
            password="pw",
            catalog=ToolCatalog([], {}),
            system_prompt="s",
        )

    assert make("https://api.mistral.ai/v1").llm_url == "https://api.mistral.ai/v1/chat/completions"
    assert make("https://api.mistral.ai").llm_url == "https://api.mistral.ai/v1/chat/completions"
    assert make("http://localhost:4000/v1").llm_url == "http://localhost:4000/v1/chat/completions"


def test_llm_request_uses_bearer_api_key_and_chat_completions():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["auth"] = request.headers.get("authorization")
        return httpx.Response(200, json=_llm_response(content="ok"))

    agent = PlmAgent(
        plm_base_url="http://plm.test",
        llm_base_url="https://api.mistral.ai/v1",
        api_key="mstrl-test-only",
        model="mistral-large-latest",
        email="a@b.c",
        password="pw",
        catalog=ToolCatalog([], {}),
        system_prompt="s",
        transport=httpx.MockTransport(handler),
    )
    agent._llm([{"role": "user", "content": "hi"}])
    assert captured["url"] == "https://api.mistral.ai/v1/chat/completions"
    assert captured["auth"] == "Bearer mstrl-test-only"


def test_llm_omits_tools_key_when_catalog_empty():
    """Providers like Mistral reject "tools": [] with 400 — omit the key entirely."""
    state = {"requests": []}

    def handler(request: httpx.Request) -> httpx.Response:
        state["requests"].append((request.method, str(request.url), request.content))
        if str(request.url).endswith("/chat/completions"):
            return httpx.Response(200, json=_llm_response(content="ok"))
        return httpx.Response(404, json={})

    agent = PlmAgent(
        plm_base_url="http://plm.test",
        llm_base_url="http://llm.test/v1",
        api_key="k",
        model="m",
        email="a@b.c",
        password="pw",
        catalog=ToolCatalog([], {}),
        system_prompt="s",
        transport=httpx.MockTransport(handler),
    )
    agent._llm([{"role": "user", "content": "hi"}])
    body = json.loads(state["requests"][0][2])
    assert "tools" not in body
    assert body["messages"][0]["content"] == "hi"


def test_llm_error_message_includes_provider_body():
    import pytest

    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url).endswith("/chat/completions"):
            return httpx.Response(400, json={"message": "Invalid model name: foo-bar"})
        return httpx.Response(404, json={})

    agent = PlmAgent(
        plm_base_url="http://plm.test",
        llm_base_url="https://api.mistral.ai/v1",
        api_key="k",
        model="foo-bar",
        email="a@b.c",
        password="pw",
        catalog=ToolCatalog([], {}),
        system_prompt="s",
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(httpx.HTTPStatusError) as exc:
        agent._llm([{"role": "user", "content": "hi"}])
    assert "400" in str(exc.value)
    assert "Invalid model name: foo-bar" in str(exc.value)
