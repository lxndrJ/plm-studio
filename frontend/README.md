# Frontend (SvelteKit)

Set up in M2:

    npm create svelte@latest .
    npm install
    npm run dev

Planned routes: /parts, /bom, /documents, /changes, /reports, /admin.

Generate the API client from OpenAPI (single source of truth):

    npx openapi-typescript http://localhost:8000/openapi.json -o src/lib/api/schema.d.ts

Next task: login (JWT from backend/app/core/security.py) and the parts
list with search against GET /api/v1/parts.
