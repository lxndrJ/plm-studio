<script lang="ts">
  // Phase 1 skeleton: dashboard placeholder. Filled out in M2-M6
  // (/parts, /bom, /documents, /changes, /reports, /admin).
  import { onMount } from "svelte";
  import { health } from "$lib/api/client";

  let status: string | null = null;

  onMount(() => {
    health()
      .then((h) => (status = `${h.status} / db:${h.database}`))
      .catch(() => (status = "API not reachable"));
  });
</script>

<main>
  <h1>PLM Studio</h1>
  <p>In-house PLM with AI prompt layer — Phase 1 (backend live, frontend skeleton).</p>
  <p>API status: {status ?? "loading ..."}</p>
  <ul>
    <li><a href="/docs">OpenAPI / Swagger</a></li>
    <li>Login: <code>POST /api/v1/auth/login</code></li>
  </ul>
</main>
