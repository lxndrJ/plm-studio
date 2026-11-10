"""M10: agent service - SSE chat endpoint + conversation persistence via the
PLM backend (mocked with httpx.MockTransport)."""

import json

import httpx
from fastapi.testclient import TestClient

from plm_agent.server import create_app
from tests.test_runner import _call, _llm_response, _make_agent


def _handler(state):
    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        state["requests"].append((request.method, url, request.content))
        if url.endswith("/api/v1/auth/login"):
            return httpx.Response(200, json={"access_token": "tok"})
        if url.endswith("/chat/completions"):
            state["llm_calls"] = state.get("llm_calls", 0) + 1
            if state["llm_calls"] == 1:
                return httpx.Response(
                    200,
                    json=_llm_response(tool_calls=[_call("c1", "get_parts", {"query": "TEST"})]),
                )
            return httpx.Response(200, json=_llm_response(content="Fertig: 0 Treffer."))
        if url.startswith("http://plm.test/api/v1/parts") and request.method == "GET":
            return httpx.Response(200, json=[])
        if "/api/v1/agent/conversations" in url:
            if request.method == "POST" and url.rstrip("/").endswith("conversations"):
                conv = {
                    "id": "conv-1",
                    "title": json.loads(request.content)["title"],
                    "created_by": "agent-user",
                    "created_at": "2026-11-09T00:00:00",
                    "messages": state.get("messages", []),
                }
                state["conversation"] = conv
                return httpx.Response(201, json=conv)
            if request.method == "POST" and url.endswith("/messages"):
                body = json.loads(request.content)
                state.setdefault("messages", []).append(body)
                state["conversation"]["messages"] = state["messages"]
                return httpx.Response(
                    201,
                    json={
                        "id": f"m{len(state['messages'])}",
                        "role": body["role"],
                        "content": body["content"],
                        "created_at": "2026-11-09T00:00:00",
                    },
                )
            if request.method == "GET" and url.rstrip("/").endswith("conversations"):
                return httpx.Response(200, json=[state.get("conversation", {"id": "conv-1"})])
            if request.method == "GET":
                if url.endswith("conv-1"):
                    return httpx.Response(200, json=state["conversation"])
                return httpx.Response(
                    404, json={"detail": "not found", "code": "conversation_not_found"}
                )
        return httpx.Response(404, json={"detail": "unhandled", "url": url})

    return handler


def _parse_sse(text: str) -> list[dict]:
    return [json.loads(line[6:]) for line in text.splitlines() if line.startswith("data: ")]


def test_chat_streams_sse_and_persists_messages():
    state = {"requests": []}
    agent = _make_agent(state, httpx.MockTransport(_handler(state)))
    client = TestClient(create_app(agent=agent))

    r = client.post("/chat", json={"message": "Suche TEST-Teile"})
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("text/event-stream")
    events = _parse_sse(r.text)
    types = [e["type"] for e in events]
    assert types[0] == "conversation"
    assert events[0]["conversation_id"] == "conv-1"
    assert "tool_call" in types
    tool_event = next(e for e in events if e["type"] == "tool_call")
    assert tool_event["name"] == "get_parts"
    assert tool_event["result"]["status"] == 200
    done = next(e for e in events if e["type"] == "done")
    assert done["content"] == "Fertig: 0 Treffer."
    assert types[-1] == "end"

    # persistence: user message, tool message, assistant answer
    roles = [m["role"] for m in state["messages"]]
    assert roles == ["user", "tool", "assistant"]
    assert state["messages"][0]["content"] == {"text": "Suche TEST-Teile"}
    assert state["messages"][2]["content"] == {"text": "Fertig: 0 Treffer."}
    # agent logged in exactly once and used the bearer token for PLM calls
    logins = [r for r in state["requests"] if r[1].endswith("/api/v1/auth/login")]
    assert len(logins) == 1


def test_chat_with_existing_conversation_continues_history():
    state = {
        "requests": [],
        "messages": [{"role": "user", "content": {"text": "alt"}}],
        "conversation": {
            "id": "conv-1",
            "title": "t",
            "created_by": "agent-user",
            "created_at": "2026-11-09T00:00:00",
            "messages": [{"role": "user", "content": {"text": "alt"}}],
        },
    }
    agent = _make_agent(state, httpx.MockTransport(_handler(state)))
    client = TestClient(create_app(agent=agent))
    r = client.post("/chat", json={"message": "neu", "conversation_id": "conv-1"})
    assert r.status_code == 200
    events = _parse_sse(r.text)
    assert events[0]["conversation_id"] == "conv-1"
    # no new conversation was created
    assert not any(
        r[0] == "POST" and r[1].rstrip("/").endswith("/api/v1/agent/conversations")
        for r in state["requests"]
    )
    # history was sent to the LLM (system + old user + new user message)
    llm_bodies = [json.loads(r[2]) for r in state["requests"] if r[1].endswith("/chat/completions")]
    roles = [m["role"] for m in llm_bodies[0]["messages"]]
    assert roles == ["system", "user", "user"]


def test_chat_unknown_conversation_is_404():
    state = {"requests": []}
    agent = _make_agent(state, httpx.MockTransport(_handler(state)))
    client = TestClient(create_app(agent=agent))
    r = client.post("/chat", json={"message": "x", "conversation_id": "nope"})
    assert r.status_code == 404


def test_conversations_proxy():
    state = {"requests": []}
    agent = _make_agent(state, httpx.MockTransport(_handler(state)))
    client = TestClient(create_app(agent=agent))
    r = client.get("/conversations")
    assert r.status_code == 200
    assert r.json()[0]["id"] == "conv-1"


def test_service_token_is_enforced(monkeypatch):
    monkeypatch.setenv("AGENT_SERVICE_TOKEN", "secret")
    state = {"requests": []}
    agent = _make_agent(state, httpx.MockTransport(_handler(state)))
    client = TestClient(create_app(agent=agent))
    assert client.get("/conversations").status_code == 401
    assert client.get("/conversations", headers={"X-Agent-Token": "wrong"}).status_code == 401
    assert client.get("/conversations", headers={"X-Agent-Token": "secret"}).status_code == 200


def test_run_events_streams_tool_call_then_done():
    state = {"requests": []}
    agent = _make_agent(state, httpx.MockTransport(_handler(state)))
    events = list(agent.run_events("Suche TEST-Teile"))
    types = [e["type"] for e in events]
    assert types == ["tool_call", "delta", "done"]
    assert events[-1]["messages"][-1]["role"] == "assistant"


def test_default_system_prompt_packaged():
    from plm_agent.server import default_system_prompt

    prompt = default_system_prompt()
    assert "PLM" in prompt and len(prompt) > 100


def test_chat_returns_502_not_500_when_agent_login_fails():
    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url).endswith("/api/v1/auth/login"):
            return httpx.Response(
                401, json={"detail": "invalid credentials", "code": "unauthorized"}
            )
        return httpx.Response(404, json={"detail": "unhandled"})

    from plm_agent.runner import PlmAgent
    from plm_agent.toolgen import ToolCatalog

    agent = PlmAgent(
        plm_base_url="http://plm.test",
        llm_base_url="http://llm.test/v1",
        api_key="k",
        model="m",
        email="agent@example.com",
        password="wrong",
        catalog=ToolCatalog([], {}),
        system_prompt="s",
        transport=httpx.MockTransport(handler),
        sleep=lambda _: None,
    )
    client = TestClient(create_app(agent=agent))
    r = client.post("/chat", json={"message": "hallo"})
    assert r.status_code == 502, r.text
    assert "login" in r.json()["detail"]


def test_chat_stream_yields_error_event_when_llm_fails():
    state = {"requests": []}

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url.endswith("/api/v1/auth/login"):
            return httpx.Response(200, json={"access_token": "tok"})
        if url.endswith("/chat/completions"):
            return httpx.Response(500, json={"error": "llm down"})
        if "/api/v1/agent/conversations" in url and request.method == "POST":
            return httpx.Response(
                201,
                json={
                    "id": "conv-1",
                    "title": "t",
                    "created_by": "u",
                    "created_at": "2026-11-09T00:00:00",
                    "messages": [],
                },
            )
        if "/messages" in url:
            return httpx.Response(
                201, json={"id": "m1", "role": "user", "content": {}, "created_at": "x"}
            )
        return httpx.Response(200, json={})

    agent = _make_agent(state, httpx.MockTransport(handler))
    client = TestClient(create_app(agent=agent))
    r = client.post("/chat", json={"message": "hallo"})
    assert r.status_code == 200  # stream started; error comes as SSE event
    events = _parse_sse(r.text)
    types = [e["type"] for e in events]
    assert "error" in types
    assert types[-1] == "end"
    assert "HTTPStatusError" in next(e for e in events if e["type"] == "error")["message"]
