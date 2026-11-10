"""Tool generator (M7): maps the PLM API's OpenAPI schema (/openapi.json) to
function-calling tool definitions. Read endpoints are included as-is; write
endpoints are included as proposed writes only (the `direct` query parameter
is stripped, so the agent can never commit directly). Auth, confirmation
approve/reject and admin endpoints are excluded (least privilege, guardrails).
"""

import argparse
import json
import re
from pathlib import Path

API_PREFIX = "/api/v1"
EXCLUDED_PREFIXES = ("/api/v1/auth", "/api/v1/admin", "/api/v1/agent")
EXCLUDED_SUFFIXES = ("/approve", "/reject")
WRITE_METHODS = ("POST", "PUT", "PATCH", "DELETE")


def _tool_name(method: str, path: str) -> str:
    p = path.removeprefix(API_PREFIX)
    p = re.sub(r"[{}]", "", p)
    p = re.sub(r"[^a-zA-Z0-9]+", "_", p).strip("_")
    return f"{method.lower()}_{p}" if p else method.lower()


def _parameters_schema(method: str, op: dict) -> dict:
    properties: dict = {}
    required: list[str] = []
    for prm in op.get("parameters", []):
        if prm.get("in") == "header":
            continue  # never expose headers (authorization) as tool arguments
        properties[prm["name"]] = prm.get("schema", {})
        if prm.get("required"):
            required.append(prm["name"])
    body = op.get("requestBody", {}).get("content", {}).get("application/json", {}).get("schema")
    if body:
        properties.update(body.get("properties", {}))
        required.extend(body.get("required", []))
    if method.upper() in WRITE_METHODS:
        properties.pop("direct", None)
        required = [r for r in required if r != "direct"]
    return {"type": "object", "properties": properties, "required": required}


class ToolCatalog:
    def __init__(self, tools: list[dict], routes: dict):
        self.tools = tools
        self.routes = routes

    def to_dict(self) -> dict:
        return {"tools": self.tools, "routes": self.routes}

    @classmethod
    def from_dict(cls, data: dict) -> "ToolCatalog":
        return cls(tools=data["tools"], routes=data["routes"])


def generate(openapi: dict, *, api_prefix: str = API_PREFIX) -> ToolCatalog:
    tools: list[dict] = []
    routes: dict = {}
    for path, ops in openapi.get("paths", {}).items():
        if not path.startswith(api_prefix):
            continue
        if path.startswith(EXCLUDED_PREFIXES) or path.endswith(EXCLUDED_SUFFIXES):
            continue
        for method, op in ops.items():
            if method.upper() not in ("GET", "POST", "PUT", "PATCH", "DELETE"):
                continue
            name = _tool_name(method, path)
            description = op.get("summary") or op.get("description") or f"{method} {path}"
            if method.upper() in WRITE_METHODS:
                description += (
                    " (proposed write: returns 202 + confirmation_id, not committed;"
                    " never approve the confirmation yourself)"
                )
            tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": name,
                        "description": description[:1024],
                        "parameters": _parameters_schema(method, op),
                    },
                }
            )
            routes[name] = {"method": method.upper(), "path": path}
    return ToolCatalog(tools, routes)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate LLM tool definitions from the PLM API OpenAPI schema."
    )
    parser.add_argument(
        "--openapi", required=True, help="URL (http://.../openapi.json) or local file path"
    )
    parser.add_argument(
        "--out", default=str(Path(__file__).resolve().parent.parent / "tools" / "tools.json")
    )
    args = parser.parse_args(argv)

    if args.openapi.startswith("http://") or args.openapi.startswith("https://"):
        import httpx

        schema = httpx.get(args.openapi, timeout=30).json()
    else:
        schema = json.loads(Path(args.openapi).read_text(encoding="utf-8"))

    catalog = generate(schema)
    Path(args.out).write_text(json.dumps(catalog.to_dict(), indent=2), encoding="utf-8")
    print(f"wrote {len(catalog.tools)} tools to {args.out}")
    return 0
