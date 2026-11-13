<script lang="ts">
  import { onMount, onDestroy } from "svelte";
  import { auth } from "$lib/auth";
  import { api, agentApi, previewsApi, type ServiceLogs } from "$lib/api/client";

  type ServiceKey = "api" | "agent" | "previews";
  const services: { key: ServiceKey; label: string; fetch: () => Promise<ServiceLogs>; note?: string }[] = [
    { key: "api", label: "API (backend)", fetch: () => api.adminLogs(lines, level), note: "nur für Admins" },
    { key: "agent", label: "Agent-Service", fetch: () => agentApi.logs(lines, level), note: "ggf. AGENT_SERVICE_TOKEN nötig" },
    { key: "previews", label: "Preview-Worker", fetch: () => previewsApi.logs(lines, level) },
  ];

  let active: ServiceKey = "agent";
  let data: Partial<Record<ServiceKey, ServiceLogs | string>> = {};
  let lines = 200;
  let level = "INFO";
  let autoRefresh = true;
  let timer: ReturnType<typeof setInterval>;

  async function load(key: ServiceKey): Promise<void> {
    let value: ServiceLogs | string;
    try {
      value = await services.find((s) => s.key === key)!.fetch();
    } catch (e: any) {
      if (e?.status === 401) {
        value =
          key === "api"
            ? "401 — Session abgelaufen oder ungültig — bitte neu anmelden"
            : key === "agent"
              ? "401 — X-Agent-Token nötig (der UI-Proxy injiziert ihn aus AGENT_SERVICE_TOKEN)"
              : "401 — nicht autorisiert";
      } else if (e?.status === 403) {
        value = "403 — nur für Admins";
      } else {
        value = `Fehler: ${e?.message}`;
      }
    }
    data = { ...data, [key]: value };
  }

  async function loadAll(): Promise<void> {
    await Promise.all(services.map((s) => load(s.key)));
  }

  $: cur = data[active];

  function levelClass(l: string): string {
    if (l === "ERROR" || l === "CRITICAL") return "log-err";
    if (l === "WARNING") return "log-warn";
    return "log-info";
  }

  function fmtTs(ts: string): string {
    try {
      return new Date(ts).toLocaleTimeString("de-DE");
    } catch {
      return ts;
    }
  }

  onMount(() => {
    loadAll();
    timer = setInterval(() => autoRefresh && loadAll(), 5000);
  });
  onDestroy(() => clearInterval(timer));
</script>

<div class="page-head">
  <div>
    <h1>Logs</h1>
    <div class="tag">Ringbuffer der Dienste (In-Memory, letzte {lines} Zeilen) — newest first</div>
  </div>
  <div class="row">
    <select class="select" bind:value={lines} on:change={loadAll}>
      <option value={100}>100</option>
      <option value={200}>200</option>
      <option value={500}>500</option>
    </select>
    <select class="select" bind:value={level} on:change={loadAll}>
      {#each ["DEBUG", "INFO", "WARNING", "ERROR"] as l}<option value={l}>{l}</option>{/each}
    </select>
    <label class="small"><input type="checkbox" bind:checked={autoRefresh} /> auto-refresh 5s</label>
    <button class="btn btn-ghost btn-sm" on:click={loadAll}>↻</button>
  </div>
</div>

<div class="tabs">
  {#each services as s}
    <button class:active={active === s.key} on:click={() => (active = s.key)}>{s.label}</button>
  {/each}
</div>

{#if active === "api" && $auth.role !== "admin"}
  <div class="notice">API-Logs sind nur für Admins sichtbar (403).</div>
{/if}

<div class="card">
  {#if typeof cur === "string"}
    <div class="error">{cur}</div>
  {:else if cur}
    <div class="log-meta muted small">{cur.logs.length} Zeilen · Level ≥ {cur.level} · Service: {cur.service}</div>
    <div class="log-view">
      {#each cur.logs as l}
        <div class="log-line {levelClass(l.level)}">
          <span class="log-ts">{fmtTs(l.ts)}</span>
          <span class="log-level">{l.level}</span>
          <span class="log-logger">{l.logger}</span>
          <span class="log-msg">{l.message}</span>
        </div>
      {:else}
        <div class="empty">Keine Log-Zeilen für diesen Service/Filter.</div>
      {/each}
    </div>
  {:else}
    <div class="empty">Lade …</div>
  {/if}
</div>
