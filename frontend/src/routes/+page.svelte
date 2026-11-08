<script lang="ts">
  // Phase-1-Skelett: Dashboard-Platzhalter. Ausgebaut in M2-M6
  // (/parts, /bom, /documents, /changes, /reports, /admin).
  import { health } from "$lib/api/client";
  let status: string | null = $state(null);
  $effect(() => {
    health().then((h) => (status = `${h.status} / db:${h.database}`)).catch(() => (status = "API nicht erreichbar"));
  });
</script>

<main>
  <h1>PLM-Studio</h1>
  <p>Eigenbau-PLM mit KI-Prompt-Layer — Phase 1 (Backend live, Frontend-Skelett).</p>
  <p>API-Status: {status ?? "lädt …"}</p>
  <ul>
    <li><a href="/docs">OpenAPI / Swagger</a></li>
    <li>Login: <code>POST /api/v1/auth/login</code></li>
  </ul>
</main>
