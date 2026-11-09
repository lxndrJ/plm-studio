# Tool definitions

Generated automatically (M7) from the API's OpenAPI schema (`/openapi.json`) —
no manual duplication of schemas.

    python -m plm_agent.toolgen --openapi http://localhost:8000/openapi.json   # writes tools/tools.json

The generator maps endpoints to function-calling definitions (JSON Schema) and
filters to read endpoints + proposed-write endpoints: the `direct` query
parameter is stripped from write tools, and auth / confirmation approve+reject /
admin endpoints are excluded (least privilege, guardrails).
