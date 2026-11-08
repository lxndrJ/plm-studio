# Tool-Definitionen

Werden in Phase M7 automatisch aus dem OpenAPI-Schema der API generiert
(`/openapi.json`). Kein manuelles Duplizieren von Schemas.

Geplanter Generator: agent/tools/generate_tools.py - liest openapi.json,
mappt Endpunkte auf Function-Calling-Definitionen (JSON Schema), filtert
auf Lese-Endpunkte + Proposed-Write-Endpunkte.
