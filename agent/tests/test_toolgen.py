import json

from plm_agent.toolgen import generate

SAMPLE = {
    "openapi": "3.1.0",
    "info": {"title": "PLM-Studio API", "version": "0.1.0"},
    "paths": {
        "/api/v1/parts": {
            "get": {
                "operationId": "list_parts",
                "summary": "List parts",
                "parameters": [
                    {
                        "name": "query",
                        "in": "query",
                        "required": False,
                        "schema": {"type": "string"},
                    },
                ],
                "responses": {"200": {"description": "ok"}},
            },
            "post": {
                "operationId": "create_part",
                "summary": "Create part",
                "parameters": [
                    {
                        "name": "direct",
                        "in": "query",
                        "required": False,
                        "schema": {"type": "boolean"},
                    },
                ],
                "requestBody": {
                    "required": True,
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
                    },
                },
                "responses": {
                    "201": {"description": "created"},
                    "202": {"description": "proposed"},
                },
            },
        },
        "/api/v1/parts/{part_number}": {
            "get": {
                "operationId": "get_part",
                "parameters": [
                    {
                        "name": "part_number",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string"},
                    },
                ],
                "responses": {"200": {"description": "ok"}},
            },
        },
        "/api/v1/auth/login": {
            "post": {"operationId": "login", "responses": {"200": {"description": "ok"}}}
        },
        "/api/v1/confirmations/{confirmation_id}/approve": {
            "post": {
                "operationId": "approve",
                "parameters": [
                    {
                        "name": "confirmation_id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string"},
                    }
                ],
                "responses": {"200": {"description": "ok"}},
            }
        },
        "/api/v1/admin/audit-log": {
            "get": {"operationId": "audit", "responses": {"200": {"description": "ok"}}}
        },
        "/openapi.json": {
            "get": {"operationId": "openapi", "responses": {"200": {"description": "ok"}}}
        },
    },
}


def test_read_endpoints_included():
    cat = generate(SAMPLE)
    names = {t["function"]["name"] for t in cat.tools}
    assert "get_parts" in names
    assert "get_parts_part_number" in names


def test_internal_endpoints_excluded():
    cat = generate(SAMPLE)
    names = {t["function"]["name"] for t in cat.tools}
    assert not any("login" in n or "approve" in n or "openapi" in n or "audit" in n for n in names)


def test_write_excludes_direct_param():
    cat = generate(SAMPLE)
    tool = next(t for t in cat.tools if t["function"]["name"] == "post_parts")
    params = tool["function"]["parameters"]
    assert "direct" not in params["properties"]
    assert params["required"] == ["name", "class_code"]
    assert params["properties"]["name"]["type"] == "string"
    assert (
        "202" in tool["function"]["description"]
        or "proposed" in tool["function"]["description"].lower()
    )


def test_path_param_required_and_route_recorded():
    cat = generate(SAMPLE)
    tool = next(t for t in cat.tools if t["function"]["name"] == "get_parts_part_number")
    params = tool["function"]["parameters"]
    assert params["properties"]["part_number"]["type"] == "string"
    assert "part_number" in params["required"]
    assert cat.routes["get_parts_part_number"] == {
        "method": "GET",
        "path": "/api/v1/parts/{part_number}",
    }


def test_catalog_json_roundtrip():
    cat = generate(SAMPLE)
    cat2 = type(cat).from_dict(json.loads(json.dumps(cat.to_dict())))
    assert cat2.tools == cat.tools
    assert cat2.routes == cat.routes


def test_real_app_openapi_schema():
    from app.main import app

    cat = generate(app.openapi())
    names = {t["function"]["name"] for t in cat.tools}
    for expected in (
        "get_parts",
        "post_parts",
        "get_ecrs",
        "post_ecrs_number_transition",
        "post_ecos_number_affected_revisions",
        "post_reports_parts_part_number",
        "get_reports_report_id_download",
    ):
        assert expected in names, expected
    for tool in cat.tools:
        name = tool["function"]["name"]
        if name.startswith(("post_", "put_", "delete_")):
            assert "direct" not in tool["function"]["parameters"]["properties"], name
    assert not any("login" in n or "approve" in n or "reject" in n for n in names)


def test_header_parameters_are_not_tool_arguments():
    openapi = {
        "openapi": "3.1.0",
        "info": {"title": "t", "version": "1"},
        "paths": {
            "/api/v1/parts": {
                "get": {
                    "parameters": [
                        {"name": "Authorization", "in": "header", "schema": {"type": "string"}},
                        {"name": "query", "in": "query", "schema": {"type": "string"}},
                    ],
                    "responses": {"200": {"description": "ok"}},
                }
            }
        },
    }
    cat = generate(openapi)
    props = cat.tools[0]["function"]["parameters"]["properties"]
    assert "Authorization" not in props
    assert "query" in props
