"""Agent runner (M7): ReAct-style loop against LiteLLM (OpenAI-compatible
chat completions) with tools generated from the PLM API's /openapi.json.

Guardrails enforced here (in addition to the backend): the agent logs in with
its own user, never uses direct=true (stripped from tool schemas), never
calls the confirmation approve/reject endpoints (a 202 proposal is reported
back to the LLM so it asks the human), and retries 429/5xx with exponential
backoff max 3 attempts (api-contract rule 6).
"""

import json
import time

import httpx

WRITE_METHODS = ("POST", "PUT", "PATCH")


class PlmAgent:
    def __init__(
        self,
        *,
        plm_base_url: str,
        llm_base_url: str,
        api_key: str,
        model: str,
        email: str,
        password: str,
        catalog,
        system_prompt: str,
        max_steps: int = 8,
        transport: httpx.MockTransport | None = None,
        sleep=time.sleep,
    ):
        self.plm_base_url = plm_base_url.rstrip("/")
        llm = llm_base_url.rstrip("/")
        if not llm.endswith("/v1"):
            llm += "/v1"
        self.llm_url = llm + "/chat/completions"
        self.api_key = api_key
        self.model = model
        self.email = email
        self.password = password
        self.catalog = catalog
        self.system_prompt = system_prompt
        self.max_steps = max_steps
        self._sleep = sleep
        self._http = (
            httpx.Client(transport=transport, timeout=30.0)
            if transport
            else httpx.Client(timeout=30.0)
        )
        self._token: str | None = None

    def login(self) -> None:
        r = self._http.post(
            f"{self.plm_base_url}/api/v1/auth/login",
            json={"email": self.email, "password": self.password},
        )
        r.raise_for_status()
        self._token = r.json()["access_token"]

    def _plm_request(self, method: str, path: str, *, params=None, body=None) -> httpx.Response:
        last = None
        for attempt in range(3):
            r = self._http.request(
                method,
                self.plm_base_url + path,
                params=params,
                json=body,
                headers={"Authorization": f"Bearer {self._token}"},
            )
            if r.status_code == 429 or r.status_code >= 500:
                last = r
                if attempt < 2:
                    self._sleep(2**attempt)
                continue
            return r
        return last

    def _llm(self, messages: list[dict]) -> dict:
        r = self._http.post(
            self.llm_url,
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={"model": self.model, "messages": messages, "tools": self.catalog.tools},
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]

    def _execute_tool(self, call: dict) -> dict:
        name = call["function"]["name"]
        args = json.loads(call["function"].get("arguments") or "{}")
        route = self.catalog.routes[name]
        method, path = route["method"], route["path"]
        params: dict = {}
        body = None
        for key in list(args):
            token = "{" + key + "}"
            if token in path:
                path = path.replace(token, str(args.pop(key)))
        if method in WRITE_METHODS:
            body = args
        else:
            params = args
        r = self._plm_request(method, path, params=params or None, body=body)
        try:
            payload = r.json()
        except ValueError:
            payload = r.text
        if r.status_code == 202 and isinstance(payload, dict) and "confirmation_id" in payload:
            return {
                "status": 202,
                "proposed": True,
                "confirmation_id": payload["confirmation_id"],
                "summary": payload.get("summary"),
                "note": "proposed write, not committed; the user must approve via POST /api/v1/confirmations/{id}/approve - never approve yourself",
            }
        return {"status": r.status_code, "body": payload}

    def api_request(self, method: str, path: str, *, params=None, body=None) -> httpx.Response:
        """Public wrapper around the authenticated PLM request with backoff
        (used by the agent service for conversation persistence)."""
        if self._token is None:
            self.login()
        return self._plm_request(method, path, params=params, body=body)

    def run_events(self, user_prompt: str, history: list[dict] | None = None):
        """Streaming variant of run(): yields event dicts.

        Events: {"type": "tool_call", name, arguments, result} per tool call,
        {"type": "delta", "content"} for the final answer, and finally
        {"type": "done", "content", "messages"} with the full message list
        (for persistence). `history` is a list of prior LLM messages."""
        if self._token is None:
            self.login()
        messages = [{"role": "system", "content": self.system_prompt}]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": user_prompt})
        for _ in range(self.max_steps):
            message = self._llm(messages)
            messages.append(message)
            calls = message.get("tool_calls") or []
            if not calls:
                content = message.get("content") or ""
                yield {"type": "delta", "content": content}
                yield {"type": "done", "content": content, "messages": messages}
                return
            for call in calls:
                result = self._execute_tool(call)
                yield {
                    "type": "tool_call",
                    "call_id": call["id"],
                    "name": call["function"]["name"],
                    "arguments": call["function"].get("arguments"),
                    "result": result,
                }
                messages.append(
                    {"role": "tool", "tool_call_id": call["id"], "content": json.dumps(result)}
                )
        content = "max_steps reached without a final answer"
        yield {"type": "delta", "content": content}
        yield {"type": "done", "content": content, "messages": messages}

    def run(self, user_prompt: str) -> str:
        for event in self.run_events(user_prompt):
            if event["type"] == "done":
                return event["content"]
        return ""
