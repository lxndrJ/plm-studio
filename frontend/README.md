# Frontend (SvelteKit)

Wird in M2 aufgesetzt:

    npm create svelte@latest .
    npm install
    npm run dev

Geplante Routen: /parts, /bom, /documents, /changes, /reports, /admin.

API-Client aus OpenAPI generieren (single source of truth):

    npx openapi-typescript http://localhost:8000/openapi.json -o src/lib/api/schema.d.ts

Naechste Aufgabe: Login (JWT aus backend/app/core/security.py) und die
Parts-Liste mit Suchfeld gegen GET /api/v1/parts.
