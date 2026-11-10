"""Agent service (M10): HTTP chat API with SSE streaming.

POST /chat {message, conversation_id?} -> text/event-stream:
  {"type": "conversation", "conversation_id": ...}
  {"type": "tool_call", "call_id", "name", "arguments", "result"}   (result may be a 202 proposal)
  {"type": "delta", "content": ...}  /  {"type": "done", "content": ...}  /  {"type": "end"}
GET /conversations, GET /conversations/{id} -> proxied from the PLM backend.

Conversations persist in the backend via /api/v1/agent/conversations* (migration
0005), owned by the agent service account. If AGENT_SERVICE_TOKEN is set,
clients must send it as X-Agent-Token header (the service is internal, not public).
"""

import json
import os
from collections.abc import Callable
from pathlib import Path
from typing import Annotated

import httpx
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from plm_agent.runner import PlmAgent
from plm_agent.toolgen import ToolCatalog, generate

AGENT_ROOT = Path(__file__).resolve().parent.parent


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    conversation_id: str | None = None


def load_catalog(plm_base_url: str, transport: httpx.MockTransport | None = None) -> ToolCatalog:
    path = AGENT_ROOT / "tools" / "tools.json"
    if path.exists():
        return ToolCatalog.from_dict(json.loads(path.read_text(encoding="utf-8")))
    client = (
        httpx.Client(transport=transport, timeout=15.0) if transport else httpx.Client(timeout=15.0)
    )
    r = client.get(plm_base_url.rstrip("/") + "/openapi.json")
    r.raise_for_status()
    return generate(r.json())


def build_agent(transport: httpx.MockTransport | None = None) -> PlmAgent:
    plm_url = os.environ.get("PLM_API_URL", "http://localhost:8000")
    try:
        catalog = load_catalog(plm_url, transport=transport)
    except (httpx.HTTPError, OSError, ValueError):
        # API not reachable yet: start without tools; drop a tools.json into
        # agent/tools/ (python -m plm_agent.toolgen --openapi ...) to enable them
        catalog = ToolCatalog([], {})
    return PlmAgent(
        plm_base_url=plm_url,
        llm_base_url=os.environ.get("OPENAI_BASE_URL", "http://localhost:4000/v1"),
        api_key=os.environ.get("OPENAI_API_KEY", ""),
        model=os.environ.get("LLM_MODEL", "plm-chat"),
        email=os.environ.get("PLM_AGENT_EMAIL", ""),
        password=os.environ.get("PLM_AGENT_PASSWORD", ""),
        catalog=catalog,
        system_prompt=(AGENT_ROOT / "prompts" / "system-prompt.md").read_text(encoding="utf-8"),
        transport=transport,
    )


def _sse(event: dict) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


def _to_llm_message(m: dict) -> dict:
    content = m.get("content") or {}
    if m["role"] in ("user", "assistant", "system"):
        text = content.get("text", "") if isinstance(content, dict) else str(content)
        return {"role": m["role"], "content": text}
    return {
        "role": "tool",
        "tool_call_id": content.get("tool_call_id", ""),
        "content": content.get("content", ""),
    }


def create_app(
    agent: PlmAgent | None = None,
    agent_factory: Callable[[], PlmAgent] | None = None,
) -> FastAPI:
    app = FastAPI(title="PLM Agent Service", version="0.2.0")
    state: dict = {"agent": agent}
    service_token = os.environ.get("AGENT_SERVICE_TOKEN", "")

    def get_agent() -> PlmAgent:
        if state["agent"] is None:
            state["agent"] = (agent_factory or build_agent)()
        if state["agent"]._token is None:
            state["agent"].login()
        return state["agent"]

    def check_token(x_agent_token: str | None) -> None:
        if service_token and x_agent_token != service_token:
            raise HTTPException(status_code=401, detail="invalid agent service token")

    def _add_message(a: PlmAgent, conversation_id: str, role: str, content: dict) -> None:
        a.api_request(
            "POST",
            f"/api/v1/agent/conversations/{conversation_id}/messages",
            body={"role": role, "content": content},
        )

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/conversations")
    def conversations(x_agent_token: Annotated[str | None, Header()] = None):
        check_token(x_agent_token)
        return get_agent().api_request("GET", "/api/v1/agent/conversations").json()

    @app.get("/conversations/{conversation_id}")
    def conversation(conversation_id: str, x_agent_token: Annotated[str | None, Header()] = None):
        check_token(x_agent_token)
        r = get_agent().api_request("GET", f"/api/v1/agent/conversations/{conversation_id}")
        if r.status_code == 404:
            raise HTTPException(status_code=404, detail="conversation not found")
        r.raise_for_status()
        return r.json()

    @app.post("/chat")
    def chat(body: ChatRequest, x_agent_token: Annotated[str | None, Header()] = None):
        check_token(x_agent_token)
        a = get_agent()
        if body.conversation_id:
            r = a.api_request("GET", f"/api/v1/agent/conversations/{body.conversation_id}")
            if r.status_code == 404:
                raise HTTPException(status_code=404, detail="conversation not found")
            r.raise_for_status()
            conv = r.json()
        else:
            r = a.api_request(
                "POST", "/api/v1/agent/conversations", body={"title": body.message[:80]}
            )
            r.raise_for_status()
            conv = r.json()
        conversation_id = conv["id"]
        history = [_to_llm_message(m) for m in conv.get("messages", [])]

        def stream():
            yield _sse({"type": "conversation", "conversation_id": conversation_id})
            _add_message(a, conversation_id, "user", {"text": body.message})
            done = None
            for event in a.run_events(body.message, history=history):
                if event["type"] == "tool_call":
                    _add_message(
                        a,
                        conversation_id,
                        "tool",
                        {
                            "tool_call_id": event["call_id"],
                            "name": event["name"],
                            "content": json.dumps(event["result"]),
                        },
                    )
                if event["type"] == "done":
                    done = event
                yield _sse(event)
            if done is not None:
                _add_message(a, conversation_id, "assistant", {"text": done["content"]})
            yield _sse({"type": "end"})

        return StreamingResponse(stream(), media_type="text/event-stream")

    return app


app = create_app()
